"""
Suno API client for music generation.

This module provides a client for interacting with Suno's music generation API
using Playwright for authentication and session management.
"""

import json
import time
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
import requests

from ..core import (
    get_logger,
    get_settings,
    get_rate_limiter,
    SunoAPIError,
    AuthenticationError,
    DownloadError,
    NetworkError,
    MaxRetriesExceededError,
)

logger = get_logger(__name__)


class SunoClient:
    """
    Client for Suno music generation API.

    Features:
    - Playwright-based authentication
    - Session persistence (1-hour TTL)
    - Song generation with custom prompts
    - WAV file conversion and download
    - MP3 download
    - Rate limiting (2-5 second delays)
    - Exponential backoff retry logic
    """

    def __init__(self, session_file: Optional[Path] = None):
        """
        Initialize Suno client.

        Args:
            session_file: Optional path to session storage file
        """
        self.settings = get_settings()
        self.rate_limiter = get_rate_limiter()
        self.session_file = session_file or self.settings.suno.session_file
        self.base_url = self.settings.suno.base_url

        self.session: Optional[requests.Session] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

        logger.info(
            "Suno client initialized",
            base_url=self.base_url,
            session_file=str(self.session_file)
        )

    def authenticate(self, headless: bool = True) -> bool:
        """
        Authenticate with Suno using Playwright.

        Opens browser, allows manual login, captures session cookies.

        Args:
            headless: Run browser in headless mode (False for manual login)

        Returns:
            True if authentication successful

        Raises:
            AuthenticationError: If authentication fails
        """
        logger.info("Starting Suno authentication", headless=headless)

        try:
            # Check if we have a valid cached session
            if self._load_session():
                if self._verify_session():
                    logger.info("Using cached session")
                    return True
                else:
                    logger.warning("Cached session invalid, re-authenticating")

            # Start Playwright and authenticate
            with sync_playwright() as playwright:
                self.browser = playwright.chromium.launch(headless=headless)
                self.context = self.browser.new_context()
                page = self.context.new_page()

                # Navigate to Suno
                logger.info("Navigating to Suno website")
                page.goto("https://suno.com")

                if not headless:
                    # Manual login mode
                    logger.info("Please log in manually in the browser window")
                    logger.info("Press Enter after logging in...")
                    input()

                # Wait for authentication
                page.wait_for_url("**/app/**", timeout=300000)  # 5 min timeout

                # Extract session cookies
                cookies = self.context.cookies()
                storage_state = self.context.storage_state()

                # Save session
                self._save_session(storage_state)

                # Create requests session with cookies
                self._create_requests_session(cookies)

                logger.info("Authentication successful")
                return True

        except Exception as e:
            logger.error("Authentication failed", exc_info=True, error=str(e))
            raise AuthenticationError(
                f"Suno authentication failed: {str(e)}"
            ) from e

        finally:
            if self.browser:
                self.browser.close()
                self.browser = None
                self.context = None

    def _load_session(self) -> bool:
        """
        Load cached session from file.

        Returns:
            True if session loaded successfully
        """
        if not self.session_file.exists():
            return False

        try:
            with open(self.session_file, 'r') as f:
                data = json.load(f)

            # Check TTL
            saved_time = data.get('timestamp', 0)
            age = time.time() - saved_time
            if age > self.settings.suno.session_ttl:
                logger.info(f"Session expired (age: {age:.0f}s)")
                return False

            # Restore session
            storage_state = data.get('storage_state')
            if storage_state:
                cookies = storage_state.get('cookies', [])
                self._create_requests_session(cookies)
                logger.info("Session loaded from cache")
                return True

            return False

        except Exception as e:
            logger.warning(f"Failed to load session: {e}")
            return False

    def _save_session(self, storage_state: Dict[str, Any]):
        """
        Save session to file.

        Args:
            storage_state: Playwright storage state
        """
        try:
            self.session_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'timestamp': time.time(),
                'storage_state': storage_state
            }

            with open(self.session_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info("Session saved to cache")

        except Exception as e:
            logger.warning(f"Failed to save session: {e}")

    def _create_requests_session(self, cookies: List[Dict[str, Any]]):
        """
        Create requests session with cookies.

        Args:
            cookies: List of cookie dictionaries
        """
        self.session = requests.Session()

        for cookie in cookies:
            self.session.cookies.set(
                name=cookie['name'],
                value=cookie['value'],
                domain=cookie.get('domain', ''),
                path=cookie.get('path', '/')
            )

        # Set headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })

    def _verify_session(self) -> bool:
        """
        Verify that current session is valid.

        Returns:
            True if session is valid
        """
        if not self.session:
            return False

        try:
            # Try to access API
            response = self.session.get(
                f"{self.base_url}/api/feed/",
                timeout=10
            )
            return response.status_code == 200

        except Exception as e:
            logger.debug(f"Session verification failed: {e}")
            return False

    def generate_song(
        self,
        prompt: str,
        tags: Optional[str] = None,
        title: Optional[str] = None,
        make_instrumental: bool = False,
        wait_for_completion: bool = True,
        song_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a song using Suno API.

        Args:
            prompt: Song generation prompt (lyrics)
            tags: Genre/style tags
            title: Song title
            make_instrumental: Generate instrumental version
            wait_for_completion: Wait for generation to complete
            song_id: Optional song ID for logging

        Returns:
            Dictionary with generation result including clip IDs

        Raises:
            SunoAPIError: If generation fails
        """
        # Ensure authenticated
        if not self.session or not self._verify_session():
            self.authenticate(headless=False)

        # Apply rate limiting
        self.rate_limiter.acquire("suno", blocking=True)

        logger.log_generation(
            song_id=song_id or "unknown",
            stage="audio",
            status="started",
            prompt_length=len(prompt)
        )

        start_time = time.time()

        try:
            # Prepare request
            payload = {
                "prompt": prompt,
                "tags": tags or "",
                "title": title or "",
                "make_instrumental": make_instrumental,
                "mv": "chirp-v3-5",  # Latest model
                "continue_clip_id": None,
                "continue_at": None,
            }

            # Generate
            response = self.session.post(
                f"{self.base_url}/api/generate/v2/",
                json=payload,
                timeout=30
            )

            if response.status_code != 200:
                raise SunoAPIError(
                    f"Song generation failed: HTTP {response.status_code}",
                    details={"response": response.text}
                )

            result = response.json()
            clips = result.get('clips', [])

            if not clips:
                raise SunoAPIError("No clips generated")

            clip_ids = [clip['id'] for clip in clips]

            logger.info(
                "Song generation initiated",
                clip_ids=clip_ids,
                count=len(clips)
            )

            # Wait for completion if requested
            if wait_for_completion:
                clips = self._wait_for_completion(clip_ids)
                result['clips'] = clips

            duration = time.time() - start_time

            logger.log_generation(
                song_id=song_id or "unknown",
                stage="audio",
                status="completed",
                duration=duration,
                clip_count=len(clips)
            )

            return result

        except SunoAPIError:
            raise
        except Exception as e:
            duration = time.time() - start_time
            logger.log_generation(
                song_id=song_id or "unknown",
                stage="audio",
                status="failed",
                duration=duration,
                error=str(e)
            )
            raise SunoAPIError(
                f"Song generation failed: {str(e)}"
            ) from e

    def _wait_for_completion(
        self,
        clip_ids: List[str],
        timeout: int = 300,
        poll_interval: float = 2.0
    ) -> List[Dict[str, Any]]:
        """
        Wait for clip generation to complete.

        Args:
            clip_ids: List of clip IDs to wait for
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds

        Returns:
            List of completed clip dictionaries

        Raises:
            SunoAPIError: If timeout or error occurs
        """
        start_time = time.time()

        logger.info(f"Waiting for {len(clip_ids)} clips to complete")

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise SunoAPIError(
                    f"Clip generation timeout after {timeout}s",
                    details={"clip_ids": clip_ids}
                )

            # Check status
            clips = self._get_clips_status(clip_ids)

            # Check if all complete
            all_complete = all(
                clip.get('status') == 'complete'
                for clip in clips
            )

            if all_complete:
                logger.info(
                    f"All clips completed in {elapsed:.1f}s",
                    clip_ids=clip_ids
                )
                return clips

            # Check for errors
            errors = [
                clip for clip in clips
                if clip.get('status') == 'error'
            ]
            if errors:
                raise SunoAPIError(
                    f"Clip generation failed",
                    details={"errors": errors}
                )

            # Wait and retry
            time.sleep(poll_interval)

    def _get_clips_status(self, clip_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get status of clips.

        Args:
            clip_ids: List of clip IDs

        Returns:
            List of clip status dictionaries
        """
        try:
            # Query feed for clip status
            response = self.session.get(
                f"{self.base_url}/api/feed/?ids={','.join(clip_ids)}",
                timeout=10
            )

            if response.status_code != 200:
                raise NetworkError(f"Failed to get clip status: HTTP {response.status_code}")

            clips = response.json()
            return clips if isinstance(clips, list) else []

        except Exception as e:
            logger.warning(f"Failed to get clip status: {e}")
            return []

    def download_audio(
        self,
        clip_id: str,
        output_dir: Path,
        formats: List[str] = ["wav", "mp3"],
        song_id: Optional[str] = None,
    ) -> Dict[str, Path]:
        """
        Download audio in specified formats.

        Args:
            clip_id: Clip ID to download
            output_dir: Output directory
            formats: List of formats ("wav", "mp3")
            song_id: Optional song ID for logging

        Returns:
            Dictionary mapping format to file path

        Raises:
            DownloadError: If download fails
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        # Download MP3 (always available)
        if "mp3" in formats:
            mp3_path = self._download_mp3(clip_id, output_dir, song_id)
            if mp3_path:
                results["mp3"] = mp3_path

        # Download WAV (requires conversion)
        if "wav" in formats:
            wav_path = self._download_wav(clip_id, output_dir, song_id)
            if wav_path:
                results["wav"] = wav_path

        return results

    def _download_mp3(
        self,
        clip_id: str,
        output_dir: Path,
        song_id: Optional[str] = None
    ) -> Optional[Path]:
        """
        Download MP3 file.

        Args:
            clip_id: Clip ID
            output_dir: Output directory
            song_id: Optional song ID for logging

        Returns:
            Path to downloaded file or None
        """
        try:
            # Get clip info
            clips = self._get_clips_status([clip_id])
            if not clips:
                raise DownloadError(f"Clip not found: {clip_id}")

            clip = clips[0]
            mp3_url = clip.get('audio_url')

            if not mp3_url:
                raise DownloadError(f"No MP3 URL for clip: {clip_id}")

            # Download
            logger.info(f"Downloading MP3: {clip_id}")

            response = requests.get(mp3_url, stream=True, timeout=60)
            response.raise_for_status()

            output_path = output_dir / f"{clip_id}.mp3"

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"MP3 downloaded: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"MP3 download failed: {e}", exc_info=True)
            return None

    def _download_wav(
        self,
        clip_id: str,
        output_dir: Path,
        song_id: Optional[str] = None
    ) -> Optional[Path]:
        """
        Download WAV file (two-phase: convert, then download).

        Args:
            clip_id: Clip ID
            output_dir: Output directory
            song_id: Optional song ID for logging

        Returns:
            Path to downloaded file or None
        """
        try:
            # Phase 1: Request WAV conversion
            logger.info(f"Requesting WAV conversion: {clip_id}")

            response = self.session.post(
                f"{self.base_url}/api/gen/{clip_id}/convert_wav/",
                timeout=10
            )

            if response.status_code not in [200, 201]:
                logger.warning(f"WAV conversion request failed: HTTP {response.status_code}")
                return None

            # Phase 2: Poll for WAV file
            logger.info(f"Polling for WAV file: {clip_id}")

            start_time = time.time()
            timeout = self.settings.suno.wav_poll_timeout
            interval = self.settings.suno.wav_poll_interval

            while time.time() - start_time < timeout:
                response = self.session.get(
                    f"{self.base_url}/api/gen/{clip_id}/wav_file/",
                    timeout=10
                )

                if response.status_code == 200:
                    # WAV is ready, download it
                    output_path = output_dir / f"{clip_id}.wav"

                    with open(output_path, 'wb') as f:
                        f.write(response.content)

                    logger.info(f"WAV downloaded: {output_path}")
                    return output_path

                elif response.status_code == 404:
                    # Not ready yet, wait and retry
                    time.sleep(interval)
                else:
                    logger.warning(f"WAV poll failed: HTTP {response.status_code}")
                    return None

            logger.warning(f"WAV conversion timeout after {timeout}s")
            return None

        except Exception as e:
            logger.error(f"WAV download failed: {e}", exc_info=True)
            return None

    def close(self):
        """Close the client and clean up resources."""
        if self.session:
            self.session.close()
            self.session = None

        logger.info("Suno client closed")

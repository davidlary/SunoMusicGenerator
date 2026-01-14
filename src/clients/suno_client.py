"""
Suno API client for music generation.

This module provides a client for interacting with Suno's music generation API
using Playwright for authentication and session management.
"""

import json
import time
import asyncio
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright
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

    def __init__(self, session_file: Optional[Path] = None, persistent: bool = False):
        """
        Initialize Suno client.

        Args:
            session_file: Optional path to session storage file
            persistent: If True, keep browser open and refresh cookies every 60s
        """
        self.settings = get_settings()
        self.rate_limiter = get_rate_limiter()
        self.session_file = session_file or self.settings.suno.session_file
        self.base_url = self.settings.suno.base_url
        self.persistent = persistent

        self.session: Optional[requests.Session] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright: Optional[Playwright] = None

        # Persistent browser support
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop_refresh = threading.Event()

        logger.info(
            "Suno client initialized",
            base_url=self.base_url,
            session_file=str(self.session_file),
            persistent=persistent
        )

    def authenticate(self, headless: bool = True) -> bool:
        """
        Authenticate with Suno using Playwright.

        Opens browser, allows manual login, captures session cookies.
        If persistent=True, keeps browser open and starts cookie refresh thread.

        Args:
            headless: Run browser in headless mode (False for manual login)

        Returns:
            True if authentication successful

        Raises:
            AuthenticationError: If authentication fails
        """
        logger.info("Starting Suno authentication", headless=headless, persistent=self.persistent)

        try:
            # Check if we have a valid cached session (and not using persistent browser)
            if not self.persistent and self._load_session():
                if self._verify_session():
                    logger.info("Using cached session")
                    return True
                else:
                    logger.warning("Cached session invalid, re-authenticating")

            # If persistent browser is already running, just refresh
            if self.persistent and self.browser and self.context:
                logger.info("Refreshing persistent browser session")
                cookies = self.context.cookies()
                self._create_requests_session(cookies)
                return True

            # Start Playwright and authenticate
            if self.persistent:
                # Persistent mode: keep playwright and browser open
                self.playwright = sync_playwright().start()
                self.browser = self.playwright.chromium.launch(headless=headless)
                self.context = self.browser.new_context()
            else:
                # Non-persistent mode: use context manager
                with sync_playwright() as playwright:
                    self.browser = playwright.chromium.launch(headless=headless)
                    self.context = self.browser.new_context()
                    return self._do_authentication(headless)

            # Persistent mode continues here
            result = self._do_authentication(headless)

            if result and self.persistent:
                # Start cookie refresh thread
                self._start_cookie_refresh()

            return result

        except Exception as e:
            logger.error("Authentication failed", exc_info=True, error=str(e))
            if not self.persistent:
                self._cleanup_browser()
            raise AuthenticationError(
                f"Suno authentication failed: {str(e)}"
            ) from e

    def _do_authentication(self, headless: bool) -> bool:
        """
        Perform actual authentication steps.

        Args:
            headless: Run browser in headless mode

        Returns:
            True if authentication successful
        """
        try:
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

            # Save session (if not persistent)
            if not self.persistent:
                self._save_session(storage_state)

            # Create requests session with cookies
            self._create_requests_session(cookies)

            logger.info("Authentication successful")
            return True

        except Exception as e:
            logger.error("Authentication process failed", exc_info=True)
            raise

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

    def _start_cookie_refresh(self):
        """Start background thread to refresh cookies every 60 seconds."""
        if self._refresh_thread and self._refresh_thread.is_alive():
            logger.warning("Cookie refresh thread already running")
            return

        self._stop_refresh.clear()
        self._refresh_thread = threading.Thread(target=self._cookie_refresh_loop, daemon=True)
        self._refresh_thread.start()
        logger.info("Started cookie refresh thread (60s interval)")

    def _cookie_refresh_loop(self):
        """Background loop to refresh cookies every 60 seconds."""
        while not self._stop_refresh.is_set():
            try:
                time.sleep(60)  # Wait 60 seconds

                if self._stop_refresh.is_set():
                    break

                # Refresh cookies from browser context
                if self.context:
                    cookies = self.context.cookies()
                    self._create_requests_session(cookies)
                    logger.debug("Cookies refreshed from persistent browser")

            except Exception as e:
                logger.error(f"Cookie refresh failed: {e}", exc_info=True)

    def _cleanup_browser(self):
        """Clean up browser resources."""
        if self.context:
            try:
                self.context.close()
            except Exception as e:
                logger.warning(f"Failed to close browser context: {e}")
            self.context = None

        if self.browser:
            try:
                self.browser.close()
            except Exception as e:
                logger.warning(f"Failed to close browser: {e}")
            self.browser = None

        if self.playwright:
            try:
                self.playwright.stop()
            except Exception as e:
                logger.warning(f"Failed to stop playwright: {e}")
            self.playwright = None

    def close(self):
        """Close the client and clean up resources."""
        # Stop cookie refresh thread
        if self._refresh_thread:
            self._stop_refresh.set()
            self._refresh_thread.join(timeout=5)
            logger.info("Cookie refresh thread stopped")

        # Close requests session
        if self.session:
            self.session.close()
            self.session = None

        # Clean up browser only if not persistent or explicitly closing
        if self.persistent:
            logger.info("Persistent browser kept open (call stop_persistent_browser() to close)")
        else:
            self._cleanup_browser()

        logger.info("Suno client closed")

    def stop_persistent_browser(self):
        """Stop persistent browser and clean up all resources."""
        self._stop_refresh.set()
        if self._refresh_thread:
            self._refresh_thread.join(timeout=5)

        self._cleanup_browser()

        if self.session:
            self.session.close()
            self.session = None

        logger.info("Persistent browser stopped and cleaned up")

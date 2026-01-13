"""
Song generation pipeline.

Orchestrates Suno client and state tracking for audio generation.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List

from ..core import get_logger, get_settings, SongGenerationError
from ..clients import SunoClient
from ..state import StateTracker, MetadataManager

logger = get_logger(__name__)


class SongGenerator:
    """
    Pipeline for generating songs (audio).

    Integrates Suno API client with state tracking and file management.
    """

    def __init__(
        self,
        suno_client: Optional[SunoClient] = None,
        state_tracker: Optional[StateTracker] = None
    ):
        """
        Initialize song generator.

        Args:
            suno_client: Optional Suno client instance
            state_tracker: Optional state tracker instance
        """
        self.settings = get_settings()
        self.suno_client = suno_client or SunoClient()
        self.state_tracker = state_tracker or StateTracker()

        logger.info("Song generator initialized")

    def generate(
        self,
        song_id: str,
        lyrics: str,
        title: str,
        tags: Optional[str] = None,
        download_formats: List[str] = ["wav", "mp3"],
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate song audio.

        Args:
            song_id: Song identifier
            lyrics: Song lyrics
            title: Song title
            tags: Genre/style tags
            download_formats: Formats to download ("wav", "mp3")
            force_regenerate: Force regeneration even if audio exists

        Returns:
            Dictionary with audio data and metadata

        Raises:
            SongGenerationError: If generation fails
        """
        try:
            # Check if already exists
            if not force_regenerate:
                existing = self.state_tracker.get_active_audio_directory(song_id)
                if existing and Path(existing).exists():
                    logger.info(f"Audio already exists for {song_id}")
                    return {"directory": existing, "regenerated": False}

            # Generate song
            logger.info(f"Generating audio for {song_id}")

            result = self.suno_client.generate_song(
                prompt=lyrics,
                tags=tags or "educational",
                title=title,
                make_instrumental=False,
                wait_for_completion=True,
                song_id=song_id
            )

            clips = result.get("clips", [])
            clip_ids = [clip["id"] for clip in clips]

            # Download audio files
            audio_dir = self.settings.paths.get_audio_dir(song_id)
            audio_dir.mkdir(parents=True, exist_ok=True)

            downloaded_files = {}
            for clip_id in clip_ids:
                files = self.suno_client.download_audio(
                    clip_id=clip_id,
                    output_dir=audio_dir,
                    formats=download_formats,
                    song_id=song_id
                )
                downloaded_files[clip_id] = files

            # Save to state
            self.state_tracker.add_audio_version(
                song_id=song_id,
                audio_dir=audio_dir,
                clip_ids=clip_ids,
                metadata={
                    "title": title,
                    "tags": tags,
                    "formats": download_formats,
                    "files": {
                        clip_id: {fmt: str(path) for fmt, path in files.items()}
                        for clip_id, files in downloaded_files.items()
                    }
                }
            )

            logger.info(f"Audio generated: {audio_dir}")

            return {
                "directory": str(audio_dir),
                "clip_ids": clip_ids,
                "files": downloaded_files,
                "regenerated": True
            }

        except Exception as e:
            logger.error(f"Song generation failed: {e}", exc_info=True)
            raise SongGenerationError(
                f"Failed to generate audio for {song_id}: {str(e)}"
            ) from e

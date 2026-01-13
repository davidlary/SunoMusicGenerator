"""
Cover art generation pipeline.

Orchestrates Gemini client and state tracking for cover art generation.
"""

from pathlib import Path
from typing import Optional, Dict, Any

from ..core import get_logger, get_settings, CoverGenerationError
from ..clients import GeminiClient
from ..state import StateTracker, MetadataManager

logger = get_logger(__name__)


class CoverGenerator:
    """
    Pipeline for generating cover art.

    Integrates Gemini API client with state tracking and file management.
    """

    def __init__(
        self,
        gemini_client: Optional[GeminiClient] = None,
        state_tracker: Optional[StateTracker] = None
    ):
        """
        Initialize cover generator.

        Args:
            gemini_client: Optional Gemini client instance
            state_tracker: Optional state tracker instance
        """
        self.settings = get_settings()
        self.gemini_client = gemini_client or GeminiClient()
        self.state_tracker = state_tracker or StateTracker()

        logger.info("Cover generator initialized")

    def generate(
        self,
        song_id: str,
        lyrics: str,
        prompt_template_path: Path,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate cover art for a song.

        Args:
            song_id: Song identifier
            lyrics: Song lyrics
            prompt_template_path: Path to cover generation prompt
            force_regenerate: Force regeneration even if cover exists

        Returns:
            Dictionary with cover art data and metadata

        Raises:
            CoverGenerationError: If generation fails
        """
        try:
            # Check if already exists
            if not force_regenerate:
                existing = self.state_tracker.get_active_cover(song_id)
                if existing and Path(existing).exists():
                    logger.info(f"Cover art already exists for {song_id}")
                    return {"path": existing, "regenerated": False}

            # Load prompt template
            logger.info(f"Generating cover art for {song_id}")
            with open(prompt_template_path, 'r') as f:
                prompt_template = f.read()

            # Generate cover art
            image_bytes = self.gemini_client.generate_cover_art(
                lyrics_text=lyrics,
                prompt_template=prompt_template,
                song_id=song_id
            )

            # Save cover art
            cover_dir = self.settings.paths.get_cover_dir(song_id)
            cover_dir.mkdir(parents=True, exist_ok=True)

            cover_path = cover_dir / f"{song_id}.jpg"

            with open(cover_path, 'wb') as f:
                f.write(image_bytes)

            # Save to state
            self.state_tracker.add_cover_version(
                song_id=song_id,
                cover_path=cover_path,
                prompt=str(prompt_template_path),
                model=self.settings.gemini.cover_model,
                metadata={
                    "size": len(image_bytes),
                    "format": "JPEG"
                }
            )

            logger.info(f"Cover art generated: {cover_path}")

            return {
                "path": str(cover_path),
                "size": len(image_bytes),
                "regenerated": True
            }

        except Exception as e:
            logger.error(f"Cover generation failed: {e}", exc_info=True)
            raise CoverGenerationError(
                f"Failed to generate cover for {song_id}: {str(e)}"
            ) from e

"""
Lyrics generation pipeline.

Orchestrates Gemini client and state tracking for lyrics generation.
"""

from pathlib import Path
from typing import Optional, Dict, Any

from ..core import get_logger, get_settings, LyricsGenerationError
from ..clients import GeminiClient
from ..state import StateTracker, MetadataManager

logger = get_logger(__name__)


class LyricsGenerator:
    """
    Pipeline for generating song lyrics.

    Integrates Gemini API client with state tracking and file management.
    """

    def __init__(
        self,
        gemini_client: Optional[GeminiClient] = None,
        state_tracker: Optional[StateTracker] = None
    ):
        """
        Initialize lyrics generator.

        Args:
            gemini_client: Optional Gemini client instance
            state_tracker: Optional state tracker instance
        """
        self.settings = get_settings()
        self.gemini_client = gemini_client or GeminiClient()
        self.state_tracker = state_tracker or StateTracker()

        logger.info("Lyrics generator initialized")

    def generate(
        self,
        song_id: str,
        narrative_text: str,
        prompt_template_path: Path,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate lyrics for a song.

        Args:
            song_id: Song identifier
            narrative_text: Source scientific narrative
            prompt_template_path: Path to Eureka Protocol prompt
            force_regenerate: Force regeneration even if lyrics exist

        Returns:
            Dictionary with lyrics data and metadata

        Raises:
            LyricsGenerationError: If generation fails
        """
        try:
            # Check if already exists
            if not force_regenerate:
                existing = self.state_tracker.get_active_lyrics(song_id)
                if existing and Path(existing).exists():
                    logger.info(f"Lyrics already exist for {song_id}")
                    return {"path": existing, "regenerated": False}

            # Load prompt template
            logger.info(f"Generating lyrics for {song_id}")
            with open(prompt_template_path, 'r') as f:
                prompt_template = f.read()

            # Generate lyrics
            result = self.gemini_client.generate_lyrics(
                narrative_text=narrative_text,
                prompt_template=prompt_template,
                song_id=song_id
            )

            # Save lyrics
            lyrics_dir = self.settings.paths.get_song_dir(song_id) / "Lyrics"
            lyrics_dir.mkdir(parents=True, exist_ok=True)

            lyrics_path = lyrics_dir / f"{song_id}.txt"

            with open(lyrics_path, 'w') as f:
                f.write(result["lyrics"])

            # Save to state
            self.state_tracker.add_lyrics_version(
                song_id=song_id,
                lyrics_path=lyrics_path,
                prompt=str(prompt_template_path),
                model=result["model"],
                metadata=result.get("metadata", {})
            )

            logger.info(f"Lyrics generated: {lyrics_path}")

            return {
                "path": str(lyrics_path),
                "lyrics": result["lyrics"],
                "model": result["model"],
                "regenerated": True
            }

        except Exception as e:
            logger.error(f"Lyrics generation failed: {e}", exc_info=True)
            raise LyricsGenerationError(
                f"Failed to generate lyrics for {song_id}: {str(e)}"
            ) from e

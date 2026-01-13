"""
Metadata management for generated content.

This module provides utilities for managing metadata associated
with lyrics, audio, and cover art.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from ..core import (
    get_logger,
    MetadataError,
)

logger = get_logger(__name__)


class MetadataManager:
    """
    Manages metadata for generated content.

    Features:
    - Store and retrieve metadata
    - Merge metadata from multiple sources
    - Validate metadata structure
    - Export metadata in various formats
    """

    @staticmethod
    def create_lyrics_metadata(
        song_id: str,
        prompt: str,
        model: str,
        generation_time: float,
        lyrics_length: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create metadata for lyrics generation.

        Args:
            song_id: Song identifier
            prompt: Generation prompt
            model: Model name
            generation_time: Generation duration in seconds
            lyrics_length: Character count of lyrics
            **kwargs: Additional metadata fields

        Returns:
            Metadata dictionary
        """
        metadata = {
            "song_id": song_id,
            "type": "lyrics",
            "generated_at": datetime.now().isoformat(),
            "prompt": prompt,
            "model": model,
            "generation_time": generation_time,
            "lyrics_length": lyrics_length,
            **kwargs
        }

        logger.debug(f"Created lyrics metadata for {song_id}")
        return metadata

    @staticmethod
    def create_audio_metadata(
        song_id: str,
        clip_ids: list,
        generation_time: float,
        duration: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create metadata for audio generation.

        Args:
            song_id: Song identifier
            clip_ids: List of Suno clip IDs
            generation_time: Generation duration in seconds
            duration: Audio duration in seconds
            **kwargs: Additional metadata fields

        Returns:
            Metadata dictionary
        """
        metadata = {
            "song_id": song_id,
            "type": "audio",
            "generated_at": datetime.now().isoformat(),
            "clip_ids": clip_ids,
            "generation_time": generation_time,
            **kwargs
        }

        if duration is not None:
            metadata["duration"] = duration

        logger.debug(f"Created audio metadata for {song_id}")
        return metadata

    @staticmethod
    def create_cover_metadata(
        song_id: str,
        prompt: str,
        model: str,
        generation_time: float,
        image_size: int,
        resolution: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create metadata for cover art generation.

        Args:
            song_id: Song identifier
            prompt: Generation prompt
            model: Model name
            generation_time: Generation duration in seconds
            image_size: File size in bytes
            resolution: Image resolution (e.g., "4096x4096")
            **kwargs: Additional metadata fields

        Returns:
            Metadata dictionary
        """
        metadata = {
            "song_id": song_id,
            "type": "cover",
            "generated_at": datetime.now().isoformat(),
            "prompt": prompt,
            "model": model,
            "generation_time": generation_time,
            "image_size": image_size,
            **kwargs
        }

        if resolution:
            metadata["resolution"] = resolution

        logger.debug(f"Created cover metadata for {song_id}")
        return metadata

    @staticmethod
    def save_metadata(metadata: Dict[str, Any], output_path: Path):
        """
        Save metadata to JSON file.

        Args:
            metadata: Metadata dictionary
            output_path: Output file path
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            logger.debug(f"Saved metadata to {output_path}")

        except Exception as e:
            logger.error(f"Failed to save metadata: {e}", exc_info=True)
            raise MetadataError(
                f"Failed to save metadata to {output_path}"
            ) from e

    @staticmethod
    def load_metadata(input_path: Path) -> Dict[str, Any]:
        """
        Load metadata from JSON file.

        Args:
            input_path: Input file path

        Returns:
            Metadata dictionary
        """
        try:
            with open(input_path, 'r') as f:
                metadata = json.load(f)

            logger.debug(f"Loaded metadata from {input_path}")
            return metadata

        except Exception as e:
            logger.error(f"Failed to load metadata: {e}", exc_info=True)
            raise MetadataError(
                f"Failed to load metadata from {input_path}"
            ) from e

    @staticmethod
    def merge_metadata(*metadata_dicts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge multiple metadata dictionaries.

        Later dictionaries override earlier ones for conflicting keys.

        Args:
            *metadata_dicts: Variable number of metadata dictionaries

        Returns:
            Merged metadata dictionary
        """
        merged = {}

        for metadata in metadata_dicts:
            merged.update(metadata)

        logger.debug(f"Merged {len(metadata_dicts)} metadata dictionaries")
        return merged

    @staticmethod
    def validate_metadata(
        metadata: Dict[str, Any],
        required_fields: list
    ) -> bool:
        """
        Validate metadata has required fields.

        Args:
            metadata: Metadata dictionary
            required_fields: List of required field names

        Returns:
            True if all required fields present

        Raises:
            MetadataError: If validation fails
        """
        missing = [
            field for field in required_fields
            if field not in metadata
        ]

        if missing:
            raise MetadataError(
                f"Missing required metadata fields: {', '.join(missing)}",
                details={"missing_fields": missing}
            )

        return True

    @staticmethod
    def add_tags(metadata: Dict[str, Any], tags: list) -> Dict[str, Any]:
        """
        Add tags to metadata.

        Args:
            metadata: Metadata dictionary
            tags: List of tags to add

        Returns:
            Updated metadata dictionary
        """
        if "tags" not in metadata:
            metadata["tags"] = []

        metadata["tags"].extend(tags)
        metadata["tags"] = list(set(metadata["tags"]))  # Deduplicate

        return metadata

    @staticmethod
    def get_summary(metadata: Dict[str, Any]) -> str:
        """
        Get human-readable summary of metadata.

        Args:
            metadata: Metadata dictionary

        Returns:
            Summary string
        """
        summary_parts = []

        # Type and ID
        if "type" in metadata:
            summary_parts.append(f"Type: {metadata['type']}")
        if "song_id" in metadata:
            summary_parts.append(f"Song: {metadata['song_id']}")

        # Generation info
        if "model" in metadata:
            summary_parts.append(f"Model: {metadata['model']}")
        if "generated_at" in metadata:
            summary_parts.append(f"Generated: {metadata['generated_at']}")
        if "generation_time" in metadata:
            summary_parts.append(
                f"Duration: {metadata['generation_time']:.2f}s"
            )

        # Type-specific fields
        if metadata.get("type") == "lyrics":
            if "lyrics_length" in metadata:
                summary_parts.append(
                    f"Length: {metadata['lyrics_length']} chars"
                )

        elif metadata.get("type") == "audio":
            if "clip_ids" in metadata:
                summary_parts.append(
                    f"Clips: {len(metadata['clip_ids'])}"
                )
            if "duration" in metadata:
                summary_parts.append(
                    f"Duration: {metadata['duration']:.1f}s"
                )

        elif metadata.get("type") == "cover":
            if "resolution" in metadata:
                summary_parts.append(f"Resolution: {metadata['resolution']}")
            if "image_size" in metadata:
                size_mb = metadata['image_size'] / (1024 * 1024)
                summary_parts.append(f"Size: {size_mb:.2f} MB")

        return " | ".join(summary_parts)

"""
Unit tests for MetadataManager.

Tests cover metadata creation, storage, validation, and utility functions.
"""

import pytest
import json
import tempfile
from pathlib import Path

from src.state.metadata_manager import MetadataManager
from src.core import MetadataError


class TestMetadataCreation:
    """Test metadata creation functions."""

    def test_create_lyrics_metadata(self):
        """Test creating lyrics metadata."""
        metadata = MetadataManager.create_lyrics_metadata(
            song_id="1.16.1",
            prompt="Test prompt",
            model="gemini-2.0",
            generation_time=5.3,
            lyrics_length=500,
            custom_field="value"
        )

        assert metadata["song_id"] == "1.16.1"
        assert metadata["type"] == "lyrics"
        assert metadata["model"] == "gemini-2.0"
        assert metadata["generation_time"] == 5.3
        assert metadata["lyrics_length"] == 500
        assert metadata["custom_field"] == "value"
        assert "generated_at" in metadata

    def test_create_audio_metadata(self):
        """Test creating audio metadata."""
        metadata = MetadataManager.create_audio_metadata(
            song_id="1.16.1",
            clip_ids=["clip-1", "clip-2"],
            generation_time=120.5,
            duration=180.0
        )

        assert metadata["song_id"] == "1.16.1"
        assert metadata["type"] == "audio"
        assert len(metadata["clip_ids"]) == 2
        assert metadata["generation_time"] == 120.5
        assert metadata["duration"] == 180.0

    def test_create_cover_metadata(self):
        """Test creating cover art metadata."""
        metadata = MetadataManager.create_cover_metadata(
            song_id="1.16.1",
            prompt="Renaissance art",
            model="gemini-3-pro-image",
            generation_time=8.2,
            image_size=5242880,  # 5 MB
            resolution="4096x4096"
        )

        assert metadata["song_id"] == "1.16.1"
        assert metadata["type"] == "cover"
        assert metadata["model"] == "gemini-3-pro-image"
        assert metadata["image_size"] == 5242880
        assert metadata["resolution"] == "4096x4096"


class TestMetadataPersistence:
    """Test metadata saving and loading."""

    def test_save_and_load_metadata(self):
        """Test saving and loading metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "metadata.json"

            original_metadata = {
                "song_id": "1.16.1",
                "type": "lyrics",
                "test": "value"
            }

            # Save
            MetadataManager.save_metadata(original_metadata, output_path)

            assert output_path.exists()

            # Load
            loaded_metadata = MetadataManager.load_metadata(output_path)

            assert loaded_metadata["song_id"] == "1.16.1"
            assert loaded_metadata["type"] == "lyrics"
            assert loaded_metadata["test"] == "value"

    def test_save_metadata_creates_directories(self):
        """Test that save_metadata creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dir" / "metadata.json"

            metadata = {"test": "value"}

            MetadataManager.save_metadata(metadata, output_path)

            assert output_path.exists()
            assert output_path.parent.exists()

    def test_load_nonexistent_metadata_raises_error(self):
        """Test loading nonexistent metadata raises error."""
        with pytest.raises(MetadataError):
            MetadataManager.load_metadata(Path("/nonexistent/metadata.json"))


class TestMetadataMerging:
    """Test metadata merging."""

    def test_merge_metadata(self):
        """Test merging multiple metadata dictionaries."""
        meta1 = {"a": 1, "b": 2}
        meta2 = {"b": 3, "c": 4}
        meta3 = {"c": 5, "d": 6}

        merged = MetadataManager.merge_metadata(meta1, meta2, meta3)

        # Later values should override earlier ones
        assert merged["a"] == 1
        assert merged["b"] == 3  # from meta2
        assert merged["c"] == 5  # from meta3
        assert merged["d"] == 6

    def test_merge_empty_metadata(self):
        """Test merging with empty dictionaries."""
        result = MetadataManager.merge_metadata({}, {"a": 1}, {})

        assert result == {"a": 1}


class TestMetadataValidation:
    """Test metadata validation."""

    def test_validate_metadata_success(self):
        """Test validation succeeds with all required fields."""
        metadata = {
            "song_id": "1.16.1",
            "type": "lyrics",
            "model": "gemini-2.0"
        }

        required_fields = ["song_id", "type", "model"]

        assert MetadataManager.validate_metadata(metadata, required_fields) is True

    def test_validate_metadata_missing_fields(self):
        """Test validation fails with missing fields."""
        metadata = {
            "song_id": "1.16.1"
        }

        required_fields = ["song_id", "type", "model"]

        with pytest.raises(MetadataError) as exc_info:
            MetadataManager.validate_metadata(metadata, required_fields)

        assert "missing" in str(exc_info.value).lower()

    def test_validate_metadata_no_required_fields(self):
        """Test validation succeeds with no required fields."""
        metadata = {"a": 1}

        assert MetadataManager.validate_metadata(metadata, []) is True


class TestMetadataTags:
    """Test tag management."""

    def test_add_tags(self):
        """Test adding tags to metadata."""
        metadata = {"song_id": "1.16.1"}

        metadata = MetadataManager.add_tags(metadata, ["rock", "upbeat"])

        assert "tags" in metadata
        assert "rock" in metadata["tags"]
        assert "upbeat" in metadata["tags"]

    def test_add_tags_to_existing(self):
        """Test adding tags to existing tags."""
        metadata = {"tags": ["rock"]}

        metadata = MetadataManager.add_tags(metadata, ["upbeat", "energetic"])

        assert len(metadata["tags"]) == 3
        assert "rock" in metadata["tags"]
        assert "upbeat" in metadata["tags"]

    def test_add_tags_deduplicates(self):
        """Test that adding duplicate tags deduplicates."""
        metadata = {"tags": ["rock"]}

        metadata = MetadataManager.add_tags(metadata, ["rock", "upbeat"])

        # Should only have 2 unique tags
        assert len(metadata["tags"]) == 2
        assert metadata["tags"].count("rock") == 1


class TestMetadataSummary:
    """Test metadata summary generation."""

    def test_get_summary_lyrics(self):
        """Test summary for lyrics metadata."""
        metadata = {
            "type": "lyrics",
            "song_id": "1.16.1",
            "model": "gemini-2.0",
            "generated_at": "2026-01-13T12:00:00",
            "generation_time": 5.3,
            "lyrics_length": 500
        }

        summary = MetadataManager.get_summary(metadata)

        assert "lyrics" in summary.lower()
        assert "1.16.1" in summary
        assert "gemini-2.0" in summary
        assert "500 chars" in summary

    def test_get_summary_audio(self):
        """Test summary for audio metadata."""
        metadata = {
            "type": "audio",
            "song_id": "1.16.2",
            "generated_at": "2026-01-13T12:00:00",
            "generation_time": 120.0,
            "clip_ids": ["clip-1", "clip-2"],
            "duration": 180.5
        }

        summary = MetadataManager.get_summary(metadata)

        assert "audio" in summary.lower()
        assert "1.16.2" in summary
        assert "2" in summary  # Clip count
        assert "180.5" in summary  # Duration

    def test_get_summary_cover(self):
        """Test summary for cover art metadata."""
        metadata = {
            "type": "cover",
            "song_id": "1.16.3",
            "model": "gemini-3-pro-image",
            "generated_at": "2026-01-13T12:00:00",
            "generation_time": 8.2,
            "resolution": "4096x4096",
            "image_size": 5242880  # 5 MB
        }

        summary = MetadataManager.get_summary(metadata)

        assert "cover" in summary.lower()
        assert "1.16.3" in summary
        assert "4096x4096" in summary
        assert "5.00 MB" in summary

    def test_get_summary_minimal_metadata(self):
        """Test summary with minimal metadata."""
        metadata = {"song_id": "1.16.1"}

        summary = MetadataManager.get_summary(metadata)

        assert "1.16.1" in summary


class TestMetadataIntegration:
    """Integration tests for metadata workflow."""

    def test_full_lyrics_workflow(self):
        """Test complete lyrics metadata workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create metadata
            metadata = MetadataManager.create_lyrics_metadata(
                song_id="1.16.1",
                prompt="Test prompt",
                model="gemini-2.0",
                generation_time=5.0,
                lyrics_length=400
            )

            # Add tags
            metadata = MetadataManager.add_tags(metadata, ["physics", "educational"])

            # Validate
            required = ["song_id", "type", "model"]
            assert MetadataManager.validate_metadata(metadata, required)

            # Save
            output_path = Path(tmpdir) / "lyrics_metadata.json"
            MetadataManager.save_metadata(metadata, output_path)

            # Load
            loaded = MetadataManager.load_metadata(output_path)

            # Verify
            assert loaded["song_id"] == "1.16.1"
            assert "physics" in loaded["tags"]

            # Summary
            summary = MetadataManager.get_summary(loaded)
            assert "1.16.1" in summary
            assert "lyrics" in summary.lower()

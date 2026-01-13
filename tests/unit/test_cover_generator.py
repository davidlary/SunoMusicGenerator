"""
Unit tests for CoverGenerator.

Tests cover cover art generation workflow, state integration, and error handling.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.pipeline.cover_generator import CoverGenerator
from src.core import CoverGenerationError


class TestCoverGeneratorInit:
    """Test CoverGenerator initialization."""

    def test_init_default_clients(self):
        """Test initialization with default clients."""
        with patch('src.pipeline.cover_generator.GeminiClient'), \
             patch('src.pipeline.cover_generator.StateTracker'):
            generator = CoverGenerator()

            assert generator.gemini_client is not None
            assert generator.state_tracker is not None
            assert generator.settings is not None

    def test_init_custom_clients(self):
        """Test initialization with custom clients."""
        mock_gemini = Mock()
        mock_state = Mock()

        generator = CoverGenerator(
            gemini_client=mock_gemini,
            state_tracker=mock_state
        )

        assert generator.gemini_client == mock_gemini
        assert generator.state_tracker == mock_state


class TestCoverGeneration:
    """Test cover art generation workflow."""

    def test_generate_new_cover(self):
        """Test generating new cover art."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup mocks
            mock_image_bytes = b"fake_image_data_12345"

            mock_gemini = Mock()
            mock_gemini.generate_cover_art.return_value = mock_image_bytes

            mock_state = Mock()
            mock_state.get_active_cover.return_value = None

            mock_settings = Mock()
            mock_settings.paths.get_cover_dir.return_value = Path(tmpdir) / "Cover"
            mock_settings.gemini.cover_model = "gemini-3-pro-image-preview"

            # Create generator
            generator = CoverGenerator(
                gemini_client=mock_gemini,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            # Create prompt template
            prompt_path = Path(tmpdir) / "cover_prompt.txt"
            prompt_path.write_text("Generate cover art for: {lyrics}")

            # Generate
            result = generator.generate(
                song_id="1.16.1",
                lyrics="Test lyrics content",
                prompt_template_path=prompt_path,
                force_regenerate=False
            )

            # Verify
            assert result["regenerated"] is True
            assert "path" in result
            assert result["size"] == len(mock_image_bytes)

            # Verify Gemini client called
            mock_gemini.generate_cover_art.assert_called_once()

            # Verify state tracker called
            mock_state.add_cover_version.assert_called_once()

            # Verify file was written
            cover_path = Path(result["path"])
            assert cover_path.exists()
            assert cover_path.read_bytes() == mock_image_bytes

    def test_generate_existing_cover_no_force(self):
        """Test that existing cover is returned without regeneration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            existing_path = Path(tmpdir) / "existing_cover.jpg"
            existing_path.write_bytes(b"existing_image")

            mock_state = Mock()
            mock_state.get_active_cover.return_value = str(existing_path)

            generator = CoverGenerator(state_tracker=mock_state)

            result = generator.generate(
                song_id="1.16.1",
                lyrics="Test",
                prompt_template_path=Path(tmpdir) / "prompt.txt",
                force_regenerate=False
            )

            assert result["regenerated"] is False
            assert result["path"] == str(existing_path)

    def test_generate_force_regenerate(self):
        """Test force regeneration of existing cover."""
        with tempfile.TemporaryDirectory() as tmpdir:
            existing_path = Path(tmpdir) / "old_cover.jpg"
            existing_path.write_bytes(b"old_image")

            new_image = b"new_image_data"

            mock_gemini = Mock()
            mock_gemini.generate_cover_art.return_value = new_image

            mock_state = Mock()
            mock_state.get_active_cover.return_value = str(existing_path)

            mock_settings = Mock()
            mock_settings.paths.get_cover_dir.return_value = Path(tmpdir) / "Cover"
            mock_settings.gemini.cover_model = "gemini-3-pro-image"

            generator = CoverGenerator(
                gemini_client=mock_gemini,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Test prompt")

            result = generator.generate(
                song_id="1.16.1",
                lyrics="New lyrics",
                prompt_template_path=prompt_path,
                force_regenerate=True
            )

            assert result["regenerated"] is True
            assert result["size"] == len(new_image)

            # Verify new image was saved
            new_path = Path(result["path"])
            assert new_path.read_bytes() == new_image

    def test_generate_creates_directories(self):
        """Test that generation creates necessary directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_gemini = Mock()
            mock_gemini.generate_cover_art.return_value = b"test_image"

            mock_state = Mock()
            mock_state.get_active_cover.return_value = None

            cover_dir = Path(tmpdir) / "nested" / "dir" / "Cover"
            mock_settings = Mock()
            mock_settings.paths.get_cover_dir.return_value = cover_dir
            mock_settings.gemini.cover_model = "gemini-3-pro-image"

            generator = CoverGenerator(
                gemini_client=mock_gemini,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Test")

            result = generator.generate(
                song_id="1.16.1",
                lyrics="Test",
                prompt_template_path=prompt_path
            )

            # Verify directory was created
            assert Path(result["path"]).parent.exists()

    def test_generate_saves_as_jpg(self):
        """Test that cover art is saved as JPG file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_gemini = Mock()
            mock_gemini.generate_cover_art.return_value = b"test"

            mock_state = Mock()
            mock_state.get_active_cover.return_value = None

            mock_settings = Mock()
            mock_settings.paths.get_cover_dir.return_value = Path(tmpdir)
            mock_settings.gemini.cover_model = "gemini-3-pro-image"

            generator = CoverGenerator(
                gemini_client=mock_gemini,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Test")

            result = generator.generate(
                song_id="1.16.1",
                lyrics="Test",
                prompt_template_path=prompt_path
            )

            # Verify JPG extension
            assert Path(result["path"]).suffix == ".jpg"


class TestCoverGenerationErrors:
    """Test error handling in cover generation."""

    def test_generate_missing_prompt_template(self):
        """Test error when prompt template doesn't exist."""
        generator = CoverGenerator()

        with pytest.raises(CoverGenerationError):
            generator.generate(
                song_id="1.16.1",
                lyrics="Test",
                prompt_template_path=Path("/nonexistent/prompt.txt")
            )

    def test_generate_gemini_api_error(self):
        """Test error when Gemini API fails."""
        mock_gemini = Mock()
        mock_gemini.generate_cover_art.side_effect = Exception("API error")

        mock_state = Mock()
        mock_state.get_active_cover.return_value = None

        generator = CoverGenerator(
            gemini_client=mock_gemini,
            state_tracker=mock_state
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Test")

            with pytest.raises(CoverGenerationError) as exc_info:
                generator.generate(
                    song_id="1.16.1",
                    lyrics="Test",
                    prompt_template_path=prompt_path
                )

            assert "Failed to generate cover" in str(exc_info.value)
            assert "1.16.1" in str(exc_info.value)

    def test_generate_state_save_error(self):
        """Test error when state saving fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_gemini = Mock()
            mock_gemini.generate_cover_art.return_value = b"test"

            mock_state = Mock()
            mock_state.get_active_cover.return_value = None
            mock_state.add_cover_version.side_effect = Exception("State error")

            mock_settings = Mock()
            mock_settings.paths.get_cover_dir.return_value = Path(tmpdir)
            mock_settings.gemini.cover_model = "gemini-3-pro-image"

            generator = CoverGenerator(
                gemini_client=mock_gemini,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Test")

            with pytest.raises(CoverGenerationError):
                generator.generate(
                    song_id="1.16.1",
                    lyrics="Test",
                    prompt_template_path=prompt_path
                )


class TestCoverGeneratorIntegration:
    """Integration tests for complete cover generation workflow."""

    def test_full_cover_workflow(self):
        """Test complete cover art generation workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create realistic image bytes
            image_bytes = b"\xff\xd8\xff\xe0" + b"0" * 5242876  # ~5MB JPEG

            # Create mock clients
            mock_gemini = Mock()
            mock_gemini.generate_cover_art.return_value = image_bytes

            mock_state = Mock()
            mock_state.get_active_cover.return_value = None

            cover_dir = Path(tmpdir) / "Cover"
            mock_settings = Mock()
            mock_settings.paths.get_cover_dir.return_value = cover_dir
            mock_settings.gemini.cover_model = "gemini-3-pro-image-preview"

            # Create generator
            generator = CoverGenerator(
                gemini_client=mock_gemini,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            # Create prompt
            prompt_path = Path(tmpdir) / "cover_prompt.txt"
            prompt_path.write_text(
                "Create 4K Renaissance-style cover art inspired by these lyrics:\n{lyrics}"
            )

            # Generate
            result = generator.generate(
                song_id="1.16.3",
                lyrics="Scientific verse about quantum mechanics\nEducational chorus",
                prompt_template_path=prompt_path,
                force_regenerate=False
            )

            # Verify result structure
            assert result["regenerated"] is True
            assert "path" in result
            assert result["size"] == len(image_bytes)

            # Verify cover file created
            cover_path = Path(result["path"])
            assert cover_path.exists()
            assert cover_path.suffix == ".jpg"
            assert cover_path.read_bytes() == image_bytes

            # Verify state tracker integration
            call_args = mock_state.add_cover_version.call_args
            assert call_args[1]["song_id"] == "1.16.3"
            assert "cover_path" in call_args[1]
            assert call_args[1]["model"] == "gemini-3-pro-image-preview"

            # Verify metadata
            metadata = call_args[1]["metadata"]
            assert metadata["size"] == len(image_bytes)
            assert metadata["format"] == "JPEG"

    def test_cover_workflow_with_long_lyrics(self):
        """Test cover generation with lengthy lyrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_gemini = Mock()
            mock_gemini.generate_cover_art.return_value = b"image"

            mock_state = Mock()
            mock_state.get_active_cover.return_value = None

            mock_settings = Mock()
            mock_settings.paths.get_cover_dir.return_value = Path(tmpdir)
            mock_settings.gemini.cover_model = "gemini-3-pro-image"

            generator = CoverGenerator(
                gemini_client=mock_gemini,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Create art for: {lyrics}")

            # Generate with long lyrics
            long_lyrics = "\n".join([f"Verse {i}" for i in range(100)])

            result = generator.generate(
                song_id="1.16.10",
                lyrics=long_lyrics,
                prompt_template_path=prompt_path
            )

            # Verify Gemini was called with full lyrics
            call_args = mock_gemini.generate_cover_art.call_args
            assert call_args[1]["lyrics_text"] == long_lyrics
            assert result["regenerated"] is True

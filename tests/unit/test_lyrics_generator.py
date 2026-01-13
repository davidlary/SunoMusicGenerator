"""
Unit tests for LyricsGenerator.

Tests cover lyrics generation workflow, state integration, and error handling.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from src.pipeline.lyrics_generator import LyricsGenerator
from src.core import LyricsGenerationError


class TestLyricsGeneratorInit:
    """Test LyricsGenerator initialization."""

    def test_init_default_clients(self):
        """Test initialization with default clients."""
        with patch('src.pipeline.lyrics_generator.GeminiClient'), \
             patch('src.pipeline.lyrics_generator.StateTracker'):
            generator = LyricsGenerator()

            assert generator.gemini_client is not None
            assert generator.state_tracker is not None
            assert generator.settings is not None

    def test_init_custom_clients(self):
        """Test initialization with custom clients."""
        mock_gemini = Mock()
        mock_state = Mock()

        generator = LyricsGenerator(
            gemini_client=mock_gemini,
            state_tracker=mock_state
        )

        assert generator.gemini_client == mock_gemini
        assert generator.state_tracker == mock_state


class TestLyricsGeneration:
    """Test lyrics generation workflow."""

    def test_generate_new_lyrics(self):
        """Test generating new lyrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup mocks
            mock_gemini = Mock()
            mock_gemini.generate_lyrics.return_value = {
                "lyrics": "Test lyrics content",
                "model": "gemini-2.0-flash"
            }

            mock_state = Mock()
            mock_state.get_active_lyrics.return_value = None

            mock_settings = Mock()
            mock_settings.paths.get_song_dir.return_value = Path(tmpdir)

            # Create generator
            generator = LyricsGenerator(
                gemini_client=mock_gemini,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            # Create prompt template
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Generate lyrics for: {narrative}")

            # Generate
            result = generator.generate(
                song_id="1.16.1",
                narrative_text="Test narrative",
                prompt_template_path=prompt_path,
                force_regenerate=False
            )

            # Verify
            assert result["regenerated"] is True
            assert "path" in result
            assert "lyrics" in result
            assert result["model"] == "gemini-2.0-flash"

            # Verify Gemini client called
            mock_gemini.generate_lyrics.assert_called_once()

            # Verify state tracker called
            mock_state.add_lyrics_version.assert_called_once()

    def test_generate_existing_lyrics_no_force(self):
        """Test that existing lyrics are returned without regeneration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            existing_path = Path(tmpdir) / "existing.txt"
            existing_path.write_text("Existing lyrics")

            mock_state = Mock()
            mock_state.get_active_lyrics.return_value = str(existing_path)

            generator = LyricsGenerator(state_tracker=mock_state)

            result = generator.generate(
                song_id="1.16.1",
                narrative_text="Test",
                prompt_template_path=Path(tmpdir) / "prompt.txt",
                force_regenerate=False
            )

            assert result["regenerated"] is False
            assert result["path"] == str(existing_path)

    def test_generate_force_regenerate(self):
        """Test force regeneration of existing lyrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            existing_path = Path(tmpdir) / "existing.txt"
            existing_path.write_text("Old lyrics")

            mock_gemini = Mock()
            mock_gemini.generate_lyrics.return_value = {
                "lyrics": "New lyrics",
                "model": "gemini-2.0-flash"
            }

            mock_state = Mock()
            mock_state.get_active_lyrics.return_value = str(existing_path)

            mock_settings = Mock()
            mock_settings.paths.get_song_dir.return_value = Path(tmpdir)

            generator = LyricsGenerator(
                gemini_client=mock_gemini,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Test prompt")

            result = generator.generate(
                song_id="1.16.1",
                narrative_text="Test",
                prompt_template_path=prompt_path,
                force_regenerate=True
            )

            assert result["regenerated"] is True
            assert result["lyrics"] == "New lyrics"

    def test_generate_creates_directories(self):
        """Test that generation creates necessary directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_gemini = Mock()
            mock_gemini.generate_lyrics.return_value = {
                "lyrics": "Test lyrics",
                "model": "gemini-2.0-flash"
            }

            mock_state = Mock()
            mock_state.get_active_lyrics.return_value = None

            lyrics_dir = Path(tmpdir) / "nested" / "dir" / "Lyrics"
            mock_settings = Mock()
            mock_settings.paths.get_song_dir.return_value = lyrics_dir.parent.parent

            generator = LyricsGenerator(
                gemini_client=mock_gemini,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Test")

            result = generator.generate(
                song_id="1.16.1",
                narrative_text="Test",
                prompt_template_path=prompt_path
            )

            # Verify directory was created
            assert Path(result["path"]).parent.exists()


class TestLyricsGenerationErrors:
    """Test error handling in lyrics generation."""

    def test_generate_missing_prompt_template(self):
        """Test error when prompt template doesn't exist."""
        generator = LyricsGenerator()

        with pytest.raises(LyricsGenerationError):
            generator.generate(
                song_id="1.16.1",
                narrative_text="Test",
                prompt_template_path=Path("/nonexistent/prompt.txt")
            )

    def test_generate_gemini_api_error(self):
        """Test error when Gemini API fails."""
        mock_gemini = Mock()
        mock_gemini.generate_lyrics.side_effect = Exception("API error")

        mock_state = Mock()
        mock_state.get_active_lyrics.return_value = None

        generator = LyricsGenerator(
            gemini_client=mock_gemini,
            state_tracker=mock_state
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Test")

            with pytest.raises(LyricsGenerationError) as exc_info:
                generator.generate(
                    song_id="1.16.1",
                    narrative_text="Test",
                    prompt_template_path=prompt_path
                )

            assert "Failed to generate lyrics" in str(exc_info.value)
            assert "1.16.1" in str(exc_info.value)

    def test_generate_state_save_error(self):
        """Test error when state saving fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_gemini = Mock()
            mock_gemini.generate_lyrics.return_value = {
                "lyrics": "Test",
                "model": "gemini-2.0-flash"
            }

            mock_state = Mock()
            mock_state.get_active_lyrics.return_value = None
            mock_state.add_lyrics_version.side_effect = Exception("State error")

            mock_settings = Mock()
            mock_settings.paths.get_song_dir.return_value = Path(tmpdir)

            generator = LyricsGenerator(
                gemini_client=mock_gemini,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Test")

            with pytest.raises(LyricsGenerationError):
                generator.generate(
                    song_id="1.16.1",
                    narrative_text="Test",
                    prompt_template_path=prompt_path
                )


class TestLyricsGeneratorIntegration:
    """Integration tests for complete lyrics workflow."""

    def test_full_lyrics_workflow(self):
        """Test complete lyrics generation workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock clients
            mock_gemini = Mock()
            mock_gemini.generate_lyrics.return_value = {
                "lyrics": "Scientific verse\nEducational chorus",
                "model": "gemini-2.0-flash",
                "metadata": {
                    "generation_time": 5.2,
                    "tokens_used": 150
                }
            }

            mock_state = Mock()
            mock_state.get_active_lyrics.return_value = None

            mock_settings = Mock()
            mock_settings.paths.get_song_dir.return_value = Path(tmpdir)

            # Create generator
            generator = LyricsGenerator(
                gemini_client=mock_gemini,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            # Create prompt
            prompt_path = Path(tmpdir) / "eureka_protocol.txt"
            prompt_path.write_text("Transform this narrative: {text}")

            # Generate
            result = generator.generate(
                song_id="1.16.1",
                narrative_text="Physics concepts about entropy",
                prompt_template_path=prompt_path,
                force_regenerate=False
            )

            # Verify result structure
            assert result["regenerated"] is True
            assert "path" in result
            assert result["lyrics"] == "Scientific verse\nEducational chorus"
            assert result["model"] == "gemini-2.0-flash"

            # Verify lyrics file created
            assert Path(result["path"]).exists()
            assert Path(result["path"]).read_text() == "Scientific verse\nEducational chorus"

            # Verify state tracker integration
            call_args = mock_state.add_lyrics_version.call_args
            assert call_args[1]["song_id"] == "1.16.1"
            assert "lyrics_path" in call_args[1]
            assert call_args[1]["model"] == "gemini-2.0-flash"

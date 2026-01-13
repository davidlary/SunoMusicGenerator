"""
Unit tests for SongGenerator.

Tests cover audio generation workflow, state integration, and error handling.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.pipeline.song_generator import SongGenerator
from src.core import SongGenerationError


class TestSongGeneratorInit:
    """Test SongGenerator initialization."""

    def test_init_default_clients(self):
        """Test initialization with default clients."""
        with patch('src.pipeline.song_generator.SunoClient'), \
             patch('src.pipeline.song_generator.StateTracker'):
            generator = SongGenerator()

            assert generator.suno_client is not None
            assert generator.state_tracker is not None
            assert generator.settings is not None

    def test_init_custom_clients(self):
        """Test initialization with custom clients."""
        mock_suno = Mock()
        mock_state = Mock()

        generator = SongGenerator(
            suno_client=mock_suno,
            state_tracker=mock_state
        )

        assert generator.suno_client == mock_suno
        assert generator.state_tracker == mock_state


class TestSongGeneration:
    """Test song audio generation workflow."""

    def test_generate_new_song(self):
        """Test generating new song audio."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup mocks
            mock_suno = Mock()
            mock_suno.generate_song.return_value = {
                "clips": [
                    {"id": "clip-123"},
                    {"id": "clip-456"}
                ]
            }
            mock_suno.download_audio.return_value = {
                "wav": Path(tmpdir) / "song.wav",
                "mp3": Path(tmpdir) / "song.mp3"
            }

            mock_state = Mock()
            mock_state.get_active_audio_directory.return_value = None

            mock_settings = Mock()
            mock_settings.paths.get_audio_dir.return_value = Path(tmpdir) / "Audio"

            # Create generator
            generator = SongGenerator(
                suno_client=mock_suno,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            # Generate
            result = generator.generate(
                song_id="1.16.1",
                lyrics="Test lyrics",
                title="Test Song",
                tags="rock, energetic",
                download_formats=["wav", "mp3"],
                force_regenerate=False
            )

            # Verify
            assert result["regenerated"] is True
            assert "directory" in result
            assert result["clip_ids"] == ["clip-123", "clip-456"]
            assert "files" in result

            # Verify Suno client called
            mock_suno.generate_song.assert_called_once()
            assert mock_suno.download_audio.call_count == 2  # Two clips

            # Verify state tracker called
            mock_state.add_audio_version.assert_called_once()

    def test_generate_existing_audio_no_force(self):
        """Test that existing audio is returned without regeneration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            existing_dir = Path(tmpdir) / "Audio"
            existing_dir.mkdir()

            mock_state = Mock()
            mock_state.get_active_audio_directory.return_value = str(existing_dir)

            generator = SongGenerator(state_tracker=mock_state)

            result = generator.generate(
                song_id="1.16.1",
                lyrics="Test",
                title="Test Song",
                force_regenerate=False
            )

            assert result["regenerated"] is False
            assert result["directory"] == str(existing_dir)

    def test_generate_force_regenerate(self):
        """Test force regeneration of existing audio."""
        with tempfile.TemporaryDirectory() as tmpdir:
            existing_dir = Path(tmpdir) / "old_audio"
            existing_dir.mkdir()

            mock_suno = Mock()
            mock_suno.generate_song.return_value = {
                "clips": [{"id": "new-clip"}]
            }
            mock_suno.download_audio.return_value = {
                "wav": Path(tmpdir) / "new.wav"
            }

            mock_state = Mock()
            mock_state.get_active_audio_directory.return_value = str(existing_dir)

            mock_settings = Mock()
            mock_settings.paths.get_audio_dir.return_value = Path(tmpdir) / "Audio"

            generator = SongGenerator(
                suno_client=mock_suno,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            result = generator.generate(
                song_id="1.16.1",
                lyrics="New lyrics",
                title="New Song",
                force_regenerate=True
            )

            assert result["regenerated"] is True
            assert result["clip_ids"] == ["new-clip"]

    def test_generate_default_tags(self):
        """Test that default tags are used when not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_suno = Mock()
            mock_suno.generate_song.return_value = {
                "clips": [{"id": "clip-1"}]
            }
            mock_suno.download_audio.return_value = {}

            mock_state = Mock()
            mock_state.get_active_audio_directory.return_value = None

            mock_settings = Mock()
            mock_settings.paths.get_audio_dir.return_value = Path(tmpdir)

            generator = SongGenerator(
                suno_client=mock_suno,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            generator.generate(
                song_id="1.16.1",
                lyrics="Test",
                title="Test",
                tags=None
            )

            # Verify default "educational" tag was used
            call_args = mock_suno.generate_song.call_args
            assert call_args[1]["tags"] == "educational"

    def test_generate_multiple_formats(self):
        """Test downloading multiple audio formats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_suno = Mock()
            mock_suno.generate_song.return_value = {
                "clips": [{"id": "clip-1"}]
            }

            wav_path = Path(tmpdir) / "song.wav"
            mp3_path = Path(tmpdir) / "song.mp3"
            wav_path.touch()
            mp3_path.touch()

            mock_suno.download_audio.return_value = {
                "wav": wav_path,
                "mp3": mp3_path
            }

            mock_state = Mock()
            mock_state.get_active_audio_directory.return_value = None

            mock_settings = Mock()
            mock_settings.paths.get_audio_dir.return_value = Path(tmpdir)

            generator = SongGenerator(
                suno_client=mock_suno,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            result = generator.generate(
                song_id="1.16.1",
                lyrics="Test",
                title="Test",
                download_formats=["wav", "mp3"]
            )

            # Verify both formats in result
            assert "files" in result
            files = result["files"]["clip-1"]
            assert "wav" in files
            assert "mp3" in files

    def test_generate_creates_directories(self):
        """Test that generation creates necessary directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_suno = Mock()
            mock_suno.generate_song.return_value = {
                "clips": [{"id": "clip-1"}]
            }
            mock_suno.download_audio.return_value = {}

            mock_state = Mock()
            mock_state.get_active_audio_directory.return_value = None

            audio_dir = Path(tmpdir) / "nested" / "dir" / "Audio"
            mock_settings = Mock()
            mock_settings.paths.get_audio_dir.return_value = audio_dir

            generator = SongGenerator(
                suno_client=mock_suno,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            result = generator.generate(
                song_id="1.16.1",
                lyrics="Test",
                title="Test"
            )

            # Verify directory was created
            assert Path(result["directory"]).exists()


class TestSongGenerationErrors:
    """Test error handling in song generation."""

    def test_generate_suno_api_error(self):
        """Test error when Suno API fails."""
        mock_suno = Mock()
        mock_suno.generate_song.side_effect = Exception("API error")

        mock_state = Mock()
        mock_state.get_active_audio_directory.return_value = None

        generator = SongGenerator(
            suno_client=mock_suno,
            state_tracker=mock_state
        )

        with pytest.raises(SongGenerationError) as exc_info:
            generator.generate(
                song_id="1.16.1",
                lyrics="Test",
                title="Test"
            )

        assert "Failed to generate audio" in str(exc_info.value)
        assert "1.16.1" in str(exc_info.value)

    def test_generate_download_error(self):
        """Test error when audio download fails."""
        mock_suno = Mock()
        mock_suno.generate_song.return_value = {
            "clips": [{"id": "clip-1"}]
        }
        mock_suno.download_audio.side_effect = Exception("Download failed")

        mock_state = Mock()
        mock_state.get_active_audio_directory.return_value = None

        mock_settings = Mock()
        mock_settings.paths.get_audio_dir.return_value = Path("/tmp/audio")

        generator = SongGenerator(
            suno_client=mock_suno,
            state_tracker=mock_state
        )
        generator.settings = mock_settings

        with pytest.raises(SongGenerationError):
            generator.generate(
                song_id="1.16.1",
                lyrics="Test",
                title="Test"
            )

    def test_generate_state_save_error(self):
        """Test error when state saving fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_suno = Mock()
            mock_suno.generate_song.return_value = {
                "clips": [{"id": "clip-1"}]
            }
            mock_suno.download_audio.return_value = {}

            mock_state = Mock()
            mock_state.get_active_audio_directory.return_value = None
            mock_state.add_audio_version.side_effect = Exception("State error")

            mock_settings = Mock()
            mock_settings.paths.get_audio_dir.return_value = Path(tmpdir)

            generator = SongGenerator(
                suno_client=mock_suno,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            with pytest.raises(SongGenerationError):
                generator.generate(
                    song_id="1.16.1",
                    lyrics="Test",
                    title="Test"
                )


class TestSongGeneratorIntegration:
    """Integration tests for complete song generation workflow."""

    def test_full_song_workflow(self):
        """Test complete audio generation workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock clients
            mock_suno = Mock()
            mock_suno.generate_song.return_value = {
                "clips": [
                    {"id": "clip-abc-123"},
                    {"id": "clip-def-456"}
                ],
                "status": "complete"
            }

            wav1 = Path(tmpdir) / "clip1.wav"
            mp3_1 = Path(tmpdir) / "clip1.mp3"
            wav2 = Path(tmpdir) / "clip2.wav"
            mp3_2 = Path(tmpdir) / "clip2.mp3"

            for p in [wav1, mp3_1, wav2, mp3_2]:
                p.touch()

            mock_suno.download_audio.side_effect = [
                {"wav": wav1, "mp3": mp3_1},
                {"wav": wav2, "mp3": mp3_2}
            ]

            mock_state = Mock()
            mock_state.get_active_audio_directory.return_value = None

            audio_dir = Path(tmpdir) / "Audio"
            mock_settings = Mock()
            mock_settings.paths.get_audio_dir.return_value = audio_dir

            # Create generator
            generator = SongGenerator(
                suno_client=mock_suno,
                state_tracker=mock_state
            )
            generator.settings = mock_settings

            # Generate
            result = generator.generate(
                song_id="1.16.5",
                lyrics="Verse 1\nChorus\nVerse 2",
                title="Physics in Motion",
                tags="rock, educational",
                download_formats=["wav", "mp3"],
                force_regenerate=False
            )

            # Verify result structure
            assert result["regenerated"] is True
            assert "directory" in result
            assert len(result["clip_ids"]) == 2
            assert result["clip_ids"] == ["clip-abc-123", "clip-def-456"]

            # Verify files dictionary
            assert "clip-abc-123" in result["files"]
            assert "clip-def-456" in result["files"]
            assert "wav" in result["files"]["clip-abc-123"]
            assert "mp3" in result["files"]["clip-abc-123"]

            # Verify state tracker integration
            call_args = mock_state.add_audio_version.call_args
            assert call_args[1]["song_id"] == "1.16.5"
            assert "audio_dir" in call_args[1]
            assert call_args[1]["clip_ids"] == ["clip-abc-123", "clip-def-456"]
            assert "metadata" in call_args[1]

            # Verify metadata structure
            metadata = call_args[1]["metadata"]
            assert metadata["title"] == "Physics in Motion"
            assert metadata["tags"] == "rock, educational"
            assert "files" in metadata

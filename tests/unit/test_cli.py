"""
Unit tests for CLI interface.

Tests cover command structure, argument parsing, and error handling.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path

from src.cli.main import cli


class TestCLIStructure:
    """Test CLI command structure."""

    def test_cli_group_exists(self):
        """Test that main CLI group exists."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "SunoMusicGenerator" in result.output

    def test_cli_version(self):
        """Test version option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "1.0.0" in result.output


class TestGenerateLyricsCommand:
    """Test generate-lyrics command."""

    def test_command_help(self):
        """Test lyrics command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["generate-lyrics", "--help"])

        assert result.exit_code == 0
        assert "Generate lyrics" in result.output
        assert "SONG_ID" in result.output
        assert "NARRATIVE_FILE" in result.output

    @patch('src.cli.main.LyricsGenerator')
    def test_generate_lyrics_success(self, mock_lyrics_gen):
        """Test successful lyrics generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test narrative file
            narrative_file = Path(tmpdir) / "narrative.txt"
            narrative_file.write_text("Test scientific content")

            # Create test prompt
            prompt_file = Path(tmpdir) / "prompt.md"
            prompt_file.write_text("Test prompt")

            # Mock generator
            mock_instance = Mock()
            mock_instance.generate.return_value = {
                "path": "/tmp/lyrics.txt",
                "lyrics": "Test lyrics content",
                "model": "gemini-2.0-flash",
                "regenerated": True
            }
            mock_lyrics_gen.return_value = mock_instance

            # Run command
            runner = CliRunner()
            result = runner.invoke(cli, [
                "generate-lyrics",
                "1.16.1",
                str(narrative_file),
                "--prompt-template", str(prompt_file)
            ])

            # Verify
            assert result.exit_code == 0
            assert "generated successfully" in result.output.lower() or "lyrics" in result.output.lower()
            mock_instance.generate.assert_called_once()

    def test_generate_lyrics_missing_file(self):
        """Test error when narrative file doesn't exist."""
        runner = CliRunner()
        result = runner.invoke(cli, [
            "generate-lyrics",
            "1.16.1",
            "/nonexistent/file.txt"
        ])

        assert result.exit_code != 0


class TestGenerateAudioCommand:
    """Test generate-audio command."""

    def test_command_help(self):
        """Test audio command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["generate-audio", "--help"])

        assert result.exit_code == 0
        assert "Generate audio" in result.output
        assert "SONG_ID" in result.output
        assert "--title" in result.output

    @patch('src.cli.main.SongGenerator')
    def test_generate_audio_success(self, mock_song_gen):
        """Test successful audio generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test lyrics file
            lyrics_file = Path(tmpdir) / "lyrics.txt"
            lyrics_file.write_text("Test lyrics")

            # Mock generator
            mock_instance = Mock()
            mock_instance.generate.return_value = {
                "directory": "/tmp/audio",
                "clip_ids": ["clip-1"],
                "files": {
                    "clip-1": {
                        "wav": "/tmp/audio/song.wav",
                        "mp3": "/tmp/audio/song.mp3"
                    }
                },
                "regenerated": True
            }
            mock_song_gen.return_value = mock_instance

            # Run command
            runner = CliRunner()
            result = runner.invoke(cli, [
                "generate-audio",
                "1.16.1",
                str(lyrics_file),
                "--title", "Test Song"
            ])

            # Verify
            assert result.exit_code == 0
            mock_instance.generate.assert_called_once()


class TestGenerateCoverCommand:
    """Test generate-cover command."""

    def test_command_help(self):
        """Test cover command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["generate-cover", "--help"])

        assert result.exit_code == 0
        assert "Generate cover" in result.output or "cover art" in result.output.lower()

    @patch('src.cli.main.CoverGenerator')
    def test_generate_cover_success(self, mock_cover_gen):
        """Test successful cover generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test lyrics file
            lyrics_file = Path(tmpdir) / "lyrics.txt"
            lyrics_file.write_text("Test lyrics")

            # Create test prompt
            prompt_file = Path(tmpdir) / "cover_prompt.md"
            prompt_file.write_text("Test cover prompt")

            # Mock generator
            mock_instance = Mock()
            mock_instance.generate.return_value = {
                "path": "/tmp/cover.jpg",
                "size": 5242880,
                "regenerated": True
            }
            mock_cover_gen.return_value = mock_instance

            # Run command
            runner = CliRunner()
            result = runner.invoke(cli, [
                "generate-cover",
                "1.16.1",
                str(lyrics_file),
                "--prompt-template", str(prompt_file)
            ])

            # Verify
            assert result.exit_code == 0
            mock_instance.generate.assert_called_once()


class TestGenerateAllCommand:
    """Test generate-all full pipeline command."""

    def test_command_help(self):
        """Test full pipeline command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["generate-all", "--help"])

        assert result.exit_code == 0
        assert "Full" in result.output or "pipeline" in result.output.lower()
        assert "--title" in result.output

    @patch('src.cli.main.CoverGenerator')
    @patch('src.cli.main.SongGenerator')
    @patch('src.cli.main.LyricsGenerator')
    def test_generate_all_success(self, mock_lyrics, mock_song, mock_cover):
        """Test successful full pipeline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            narrative_file = Path(tmpdir) / "narrative.txt"
            narrative_file.write_text("Test content")

            lyrics_prompt = Path(tmpdir) / "lyrics_prompt.md"
            lyrics_prompt.write_text("Lyrics prompt")

            cover_prompt = Path(tmpdir) / "cover_prompt.md"
            cover_prompt.write_text("Cover prompt")

            # Mock generators
            mock_lyrics_inst = Mock()
            mock_lyrics_inst.generate.return_value = {
                "path": "/tmp/lyrics.txt",
                "lyrics": "Generated lyrics",
                "model": "gemini-2.0-flash",
                "regenerated": True
            }
            mock_lyrics.return_value = mock_lyrics_inst

            mock_song_inst = Mock()
            mock_song_inst.generate.return_value = {
                "directory": "/tmp/audio",
                "clip_ids": ["clip-1"],
                "files": {},
                "regenerated": True
            }
            mock_song.return_value = mock_song_inst

            mock_cover_inst = Mock()
            mock_cover_inst.generate.return_value = {
                "path": "/tmp/cover.jpg",
                "size": 5000000,
                "regenerated": True
            }
            mock_cover.return_value = mock_cover_inst

            # Run command
            runner = CliRunner()
            result = runner.invoke(cli, [
                "generate-all",
                "1.16.1",
                str(narrative_file),
                "--title", "Test Song",
                "--lyrics-prompt", str(lyrics_prompt),
                "--cover-prompt", str(cover_prompt)
            ])

            # Verify
            assert result.exit_code == 0
            mock_lyrics_inst.generate.assert_called_once()
            mock_song_inst.generate.assert_called_once()
            mock_cover_inst.generate.assert_called_once()


class TestStatusCommand:
    """Test status command."""

    def test_command_help(self):
        """Test status command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])

        assert result.exit_code == 0

    @patch('src.cli.main.StateTracker')
    def test_status_no_songs(self, mock_tracker):
        """Test status with no songs."""
        mock_inst = Mock()
        mock_inst.state = {"songs": {}}
        mock_tracker.return_value = mock_inst

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "No songs" in result.output

    @patch('src.cli.main.StateTracker')
    def test_status_with_songs(self, mock_tracker):
        """Test status with generated songs."""
        mock_inst = Mock()
        mock_inst.state = {
            "songs": {
                "1.16.1": {
                    "title": "Test Song",
                    "source_path": "/tmp/test.txt",
                    "created_at": "2026-01-13T12:00:00",
                    "lyrics": {"active_version": "20260113-120000"},
                    "audio": {"active_version": "20260113-120100"},
                    "cover": {"active_version": "20260113-120200"}
                }
            }
        }
        mock_tracker.return_value = mock_inst

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "1.16.1" in result.output

    @patch('src.cli.main.StateTracker')
    def test_status_specific_song(self, mock_tracker):
        """Test status for specific song."""
        mock_inst = Mock()
        mock_inst.state = {
            "songs": {
                "1.16.1": {
                    "title": "Test Song",
                    "source_path": "/tmp/test.txt",
                    "created_at": "2026-01-13T12:00:00",
                    "lyrics": {"active_version": "20260113-120000"}
                }
            }
        }
        mock_tracker.return_value = mock_inst

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "1.16.1"])

        assert result.exit_code == 0
        assert "Test Song" in result.output

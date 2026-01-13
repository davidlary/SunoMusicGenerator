"""
Unit tests for StateTracker.

Tests cover state management, versioning, hash computation,
and all CRUD operations.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.state.state_tracker import StateTracker, Version, SourceInfo
from src.core import StateFileError, VersionError, init_settings


class TestStateTrackerInitialization:
    """Test StateTracker initialization."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_initialization_new_state(self):
        """Test initialization with no existing state file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"
            tracker = StateTracker(state_file=state_file)

            assert tracker.state_file == state_file
            assert tracker.state == {"songs": {}}

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_initialization_existing_state(self):
        """Test initialization with existing state file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"

            # Create existing state
            existing_state = {
                "songs": {
                    "1.16.1": {
                        "source": {
                            "path": "/path/to/source.txt",
                            "title": "Test Song",
                            "content_hash": "abc123"
                        }
                    }
                }
            }

            with open(state_file, 'w') as f:
                json.dump(existing_state, f)

            # Load state
            tracker = StateTracker(state_file=state_file)

            assert "1.16.1" in tracker.state["songs"]
            assert tracker.state["songs"]["1.16.1"]["source"]["title"] == "Test Song"


class TestTimestampGeneration:
    """Test timestamp generation."""

    def test_generate_timestamp_format(self):
        """Test timestamp format."""
        timestamp = StateTracker.generate_timestamp()

        # Should be YYYYMMDD-HHMMSS format
        assert len(timestamp) == 15
        assert timestamp[8] == '-'

        # Should be valid date
        date_part, time_part = timestamp.split('-')
        assert len(date_part) == 8  # YYYYMMDD
        assert len(time_part) == 6  # HHMMSS


class TestHashComputation:
    """Test hash computation."""

    def test_compute_hash(self):
        """Test hash computation."""
        content = "Test content"
        hash1 = StateTracker.compute_hash(content)

        assert len(hash1) == 64  # SHA256 hex digest

        # Same content should give same hash
        hash2 = StateTracker.compute_hash(content)
        assert hash1 == hash2

        # Different content should give different hash
        hash3 = StateTracker.compute_hash("Different content")
        assert hash1 != hash3


class TestSongRegistration:
    """Test song registration."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_register_new_song(self):
        """Test registering a new song."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"
            tracker = StateTracker(state_file=state_file)

            tracker.register_song(
                song_id="1.16.1",
                source_path=Path("/test/source.txt"),
                title="Test Song",
                content="Test content"
            )

            assert tracker.song_exists("1.16.1")
            assert tracker.state["songs"]["1.16.1"]["source"]["title"] == "Test Song"

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_register_existing_song_unchanged(self):
        """Test registering song with unchanged content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"
            tracker = StateTracker(state_file=state_file)

            content = "Test content"

            # Register twice with same content
            tracker.register_song("1.16.1", Path("/test.txt"), "Test", content)
            tracker.register_song("1.16.1", Path("/test.txt"), "Test", content)

            # Should still be registered once
            assert tracker.song_exists("1.16.1")

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_register_existing_song_changed(self):
        """Test registering song with changed content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"
            tracker = StateTracker(state_file=state_file)

            # Register with original content
            tracker.register_song("1.16.1", Path("/test.txt"), "Test", "Original")

            original_hash = tracker.state["songs"]["1.16.1"]["source"]["content_hash"]

            # Re-register with new content
            tracker.register_song("1.16.1", Path("/test.txt"), "Test", "Modified")

            new_hash = tracker.state["songs"]["1.16.1"]["source"]["content_hash"]

            # Hash should have changed
            assert original_hash != new_hash


class TestLyricsVersioning:
    """Test lyrics versioning."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_add_lyrics_version(self):
        """Test adding a lyrics version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"
            tracker = StateTracker(state_file=state_file)

            # Register song first
            tracker.register_song("1.16.1", Path("/test.txt"), "Test", "Content")

            # Add lyrics version
            tracker.add_lyrics_version(
                song_id="1.16.1",
                lyrics_path=Path("/lyrics.txt"),
                prompt="Test prompt",
                model="gemini-2.0",
                metadata={"test": "data"}
            )

            versions = tracker.get_lyrics_versions("1.16.1")
            assert len(versions) == 1
            assert versions[0]["model"] == "gemini-2.0"
            assert versions[0]["metadata"]["test"] == "data"

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_add_lyrics_version_unregistered_song(self):
        """Test adding lyrics version for unregistered song raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"
            tracker = StateTracker(state_file=state_file)

            with pytest.raises(VersionError):
                tracker.add_lyrics_version(
                    "1.16.1", Path("/lyrics.txt"), "Prompt", "model"
                )

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_get_active_lyrics(self):
        """Test getting active lyrics path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"
            tracker = StateTracker(state_file=state_file)

            tracker.register_song("1.16.1", Path("/test.txt"), "Test", "Content")
            tracker.add_lyrics_version(
                "1.16.1", Path("/lyrics.txt"), "Prompt", "model"
            )

            active = tracker.get_active_lyrics("1.16.1")
            assert active == "/lyrics.txt"


class TestAudioVersioning:
    """Test audio versioning."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_add_audio_version(self):
        """Test adding an audio version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"
            tracker = StateTracker(state_file=state_file)

            tracker.register_song("1.16.1", Path("/test.txt"), "Test", "Content")

            tracker.add_audio_version(
                song_id="1.16.1",
                audio_dir=Path("/audio"),
                clip_ids=["clip-1", "clip-2"],
                metadata={"duration": 180.5}
            )

            versions = tracker.get_audio_versions("1.16.1")
            assert len(versions) == 1
            assert len(versions[0]["clip_ids"]) == 2
            assert versions[0]["metadata"]["duration"] == 180.5

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_get_active_audio_directory(self):
        """Test getting active audio directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"
            tracker = StateTracker(state_file=state_file)

            tracker.register_song("1.16.1", Path("/test.txt"), "Test", "Content")
            tracker.add_audio_version(
                "1.16.1", Path("/audio"), ["clip-1"]
            )

            active = tracker.get_active_audio_directory("1.16.1")
            assert active == "/audio"


class TestCoverVersioning:
    """Test cover art versioning."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_add_cover_version(self):
        """Test adding a cover art version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"
            tracker = StateTracker(state_file=state_file)

            tracker.register_song("1.16.1", Path("/test.txt"), "Test", "Content")

            tracker.add_cover_version(
                song_id="1.16.1",
                cover_path=Path("/cover.jpg"),
                prompt="Renaissance art",
                model="gemini-3-pro-image",
                metadata={"resolution": "4096x4096"}
            )

            versions = tracker.get_cover_versions("1.16.1")
            assert len(versions) == 1
            assert versions[0]["model"] == "gemini-3-pro-image"

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_get_active_cover(self):
        """Test getting active cover path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"
            tracker = StateTracker(state_file=state_file)

            tracker.register_song("1.16.1", Path("/test.txt"), "Test", "Content")
            tracker.add_cover_version(
                "1.16.1", Path("/cover.jpg"), "Prompt", "model"
            )

            active = tracker.get_active_cover("1.16.1")
            assert active == "/cover.jpg"


class TestStatePersistence:
    """Test state persistence."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_state_persists_after_reload(self):
        """Test state persists after reload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"

            # Create and modify state
            tracker1 = StateTracker(state_file=state_file)
            tracker1.register_song("1.16.1", Path("/test.txt"), "Test", "Content")
            tracker1.add_lyrics_version(
                "1.16.1", Path("/lyrics.txt"), "Prompt", "model"
            )

            # Reload state
            tracker2 = StateTracker(state_file=state_file)

            # Should have persisted
            assert tracker2.song_exists("1.16.1")
            assert len(tracker2.get_lyrics_versions("1.16.1")) == 1


class TestQueryMethods:
    """Test query methods."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_get_all_songs(self):
        """Test getting all song IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"
            tracker = StateTracker(state_file=state_file)

            tracker.register_song("1.16.1", Path("/test1.txt"), "Test 1", "Content 1")
            tracker.register_song("1.16.2", Path("/test2.txt"), "Test 2", "Content 2")
            tracker.register_song("1.16.3", Path("/test3.txt"), "Test 3", "Content 3")

            all_songs = tracker.get_all_songs()
            assert len(all_songs) == 3
            assert "1.16.1" in all_songs
            assert "1.16.2" in all_songs
            assert "1.16.3" in all_songs

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_get_song_state(self):
        """Test getting complete song state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"
            tracker = StateTracker(state_file=state_file)

            tracker.register_song("1.16.1", Path("/test.txt"), "Test", "Content")
            tracker.add_lyrics_version("1.16.1", Path("/lyrics.txt"), "Prompt", "model")

            state = tracker.get_song_state("1.16.1")

            assert state is not None
            assert "source" in state
            assert "lyrics" in state

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_get_statistics(self):
        """Test getting statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "test_state.json"
            tracker = StateTracker(state_file=state_file)

            # Register and add versions
            tracker.register_song("1.16.1", Path("/test1.txt"), "Test 1", "Content 1")
            tracker.add_lyrics_version("1.16.1", Path("/lyrics1.txt"), "Prompt", "model")

            tracker.register_song("1.16.2", Path("/test2.txt"), "Test 2", "Content 2")
            tracker.add_lyrics_version("1.16.2", Path("/lyrics2.txt"), "Prompt", "model")
            tracker.add_audio_version("1.16.2", Path("/audio2"), ["clip-1"])

            stats = tracker.get_statistics()

            assert stats["total_songs"] == 2
            assert stats["songs_with_lyrics"] == 2
            assert stats["songs_with_audio"] == 1
            assert stats["total_versions"]["lyrics"] == 2
            assert stats["total_versions"]["audio"] == 1

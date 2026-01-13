"""
Unit tests for FastAPI web API.

Tests cover all endpoints, request/response validation, and error handling.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from src.web.app import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client):
        """Test health endpoint returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data


class TestLyricsGeneration:
    """Test lyrics generation endpoint."""

    @patch('src.web.routes.LyricsGenerator')
    def test_generate_lyrics_success(self, mock_lyrics_gen, client):
        """Test successful lyrics generation."""
        # Mock generator
        mock_instance = Mock()
        mock_instance.generate.return_value = {
            "path": "/tmp/lyrics.txt",
            "lyrics": "Test lyrics content",
            "model": "gemini-2.0-flash",
            "regenerated": True
        }
        mock_lyrics_gen.return_value = mock_instance

        # Make request
        response = client.post(
            "/api/v1/lyrics/generate",
            json={
                "song_id": "1.16.1",
                "narrative_text": "Test narrative",
                "prompt_template_path": "prompts/test.md",
                "force_regenerate": False
            }
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "/tmp/lyrics.txt"
        assert data["lyrics"] == "Test lyrics content"
        assert data["model"] == "gemini-2.0-flash"
        assert data["regenerated"] is True

    def test_generate_lyrics_validation_error(self, client):
        """Test lyrics generation with missing required fields."""
        response = client.post(
            "/api/v1/lyrics/generate",
            json={"song_id": "1.16.1"}  # Missing narrative_text
        )

        assert response.status_code == 422

    @patch('src.web.routes.LyricsGenerator')
    def test_generate_lyrics_internal_error(self, mock_lyrics_gen, client):
        """Test lyrics generation with internal error."""
        mock_instance = Mock()
        mock_instance.generate.side_effect = Exception("API error")
        mock_lyrics_gen.return_value = mock_instance

        response = client.post(
            "/api/v1/lyrics/generate",
            json={
                "song_id": "1.16.1",
                "narrative_text": "Test"
            }
        )

        assert response.status_code == 500


class TestAudioGeneration:
    """Test audio generation endpoint."""

    @patch('src.web.routes.SongGenerator')
    def test_generate_audio_success(self, mock_song_gen, client):
        """Test successful audio generation."""
        mock_instance = Mock()
        mock_instance.generate.return_value = {
            "directory": "/tmp/audio",
            "clip_ids": ["clip-1", "clip-2"],
            "files": {
                "clip-1": {"wav": "/tmp/audio/song1.wav", "mp3": "/tmp/audio/song1.mp3"}
            },
            "regenerated": True
        }
        mock_song_gen.return_value = mock_instance

        response = client.post(
            "/api/v1/audio/generate",
            json={
                "song_id": "1.16.1",
                "lyrics": "Test lyrics",
                "title": "Test Song",
                "tags": "rock, educational",
                "download_formats": ["wav", "mp3"],
                "force_regenerate": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["directory"] == "/tmp/audio"
        assert len(data["clip_ids"]) == 2
        assert data["regenerated"] is True

    def test_generate_audio_validation_error(self, client):
        """Test audio generation with missing required fields."""
        response = client.post(
            "/api/v1/audio/generate",
            json={"song_id": "1.16.1", "lyrics": "Test"}  # Missing title
        )

        assert response.status_code == 422


class TestCoverGeneration:
    """Test cover art generation endpoint."""

    @patch('src.web.routes.CoverGenerator')
    def test_generate_cover_success(self, mock_cover_gen, client):
        """Test successful cover generation."""
        mock_instance = Mock()
        mock_instance.generate.return_value = {
            "path": "/tmp/cover.jpg",
            "size": 5242880,
            "regenerated": True
        }
        mock_cover_gen.return_value = mock_instance

        response = client.post(
            "/api/v1/cover/generate",
            json={
                "song_id": "1.16.1",
                "lyrics": "Test lyrics",
                "prompt_template_path": "prompts/cover.md",
                "force_regenerate": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "/tmp/cover.jpg"
        assert data["size"] == 5242880
        assert data["regenerated"] is True

    def test_generate_cover_validation_error(self, client):
        """Test cover generation with missing required fields."""
        response = client.post(
            "/api/v1/cover/generate",
            json={"song_id": "1.16.1"}  # Missing lyrics
        )

        assert response.status_code == 422


class TestPipelineGeneration:
    """Test full pipeline endpoint."""

    @patch('src.web.routes.CoverGenerator')
    @patch('src.web.routes.SongGenerator')
    @patch('src.web.routes.LyricsGenerator')
    def test_generate_pipeline_success(self, mock_lyrics, mock_song, mock_cover, client):
        """Test successful full pipeline generation."""
        # Mock lyrics generator
        mock_lyrics_inst = Mock()
        mock_lyrics_inst.generate.return_value = {
            "path": "/tmp/lyrics.txt",
            "lyrics": "Generated lyrics",
            "model": "gemini-2.0-flash",
            "regenerated": True
        }
        mock_lyrics.return_value = mock_lyrics_inst

        # Mock song generator
        mock_song_inst = Mock()
        mock_song_inst.generate.return_value = {
            "directory": "/tmp/audio",
            "clip_ids": ["clip-1"],
            "files": {"clip-1": {"wav": "/tmp/audio/song.wav"}},
            "regenerated": True
        }
        mock_song.return_value = mock_song_inst

        # Mock cover generator
        mock_cover_inst = Mock()
        mock_cover_inst.generate.return_value = {
            "path": "/tmp/cover.jpg",
            "size": 5000000,
            "regenerated": True
        }
        mock_cover.return_value = mock_cover_inst

        # Make request
        response = client.post(
            "/api/v1/pipeline/generate",
            json={
                "song_id": "1.16.1",
                "narrative_text": "Test narrative",
                "title": "Test Song",
                "tags": "educational",
                "lyrics_prompt_path": "prompts/lyrics.md",
                "cover_prompt_path": "prompts/cover.md",
                "force_regenerate": False
            }
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert "lyrics" in data
        assert "audio" in data
        assert "cover" in data
        assert data["lyrics"]["regenerated"] is True
        assert data["audio"]["regenerated"] is True
        assert data["cover"]["regenerated"] is True

    def test_generate_pipeline_validation_error(self, client):
        """Test pipeline generation with missing required fields."""
        response = client.post(
            "/api/v1/pipeline/generate",
            json={"song_id": "1.16.1", "narrative_text": "Test"}  # Missing title
        )

        assert response.status_code == 422


class TestStatusEndpoints:
    """Test status endpoints."""

    @patch('src.web.routes.StateTracker')
    def test_get_status_empty(self, mock_tracker, client):
        """Test status endpoint with no songs."""
        mock_inst = Mock()
        mock_inst.state = {"songs": {}}
        mock_tracker.return_value = mock_inst

        response = client.get("/api/v1/status")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        assert len(data["songs"]) == 0

    @patch('src.web.routes.StateTracker')
    def test_get_status_with_songs(self, mock_tracker, client):
        """Test status endpoint with generated songs."""
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
                },
                "1.16.2": {
                    "title": "Another Song",
                    "source_path": "/tmp/test2.txt",
                    "created_at": "2026-01-13T13:00:00"
                }
            }
        }
        mock_tracker.return_value = mock_inst

        response = client.get("/api/v1/status")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert len(data["songs"]) == 2

        # Check first song has all components
        song1 = next(s for s in data["songs"] if s["song_id"] == "1.16.1")
        assert song1["has_lyrics"] is True
        assert song1["has_audio"] is True
        assert song1["has_cover"] is True

        # Check second song has no components
        song2 = next(s for s in data["songs"] if s["song_id"] == "1.16.2")
        assert song2["has_lyrics"] is False
        assert song2["has_audio"] is False
        assert song2["has_cover"] is False

    @patch('src.web.routes.StateTracker')
    def test_get_song_status(self, mock_tracker, client):
        """Test specific song status endpoint."""
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

        response = client.get("/api/v1/status/1.16.1")

        assert response.status_code == 200
        data = response.json()
        assert data["song_id"] == "1.16.1"
        assert data["title"] == "Test Song"
        assert data["has_lyrics"] is True
        assert data["has_audio"] is False

    @patch('src.web.routes.StateTracker')
    def test_get_song_status_not_found(self, mock_tracker, client):
        """Test status for non-existent song."""
        mock_inst = Mock()
        mock_inst.state = {"songs": {}}
        mock_tracker.return_value = mock_inst

        response = client.get("/api/v1/status/nonexistent")

        assert response.status_code == 404


class TestAPIDocumentation:
    """Test API documentation endpoints."""

    def test_openapi_schema(self, client):
        """Test OpenAPI schema is accessible."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert schema["info"]["title"] == "SunoMusicGenerator API"

    def test_docs_page(self, client):
        """Test Swagger UI docs page is accessible."""
        response = client.get("/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_page(self, client):
        """Test ReDoc docs page is accessible."""
        response = client.get("/redoc")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

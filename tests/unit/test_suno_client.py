"""
Unit tests for Suno API client.

Tests cover authentication, session management, song generation,
and audio downloads (WAV and MP3).
"""

import pytest
import json
import time
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from src.clients.suno_client import SunoClient
from src.core import (
    SunoAPIError,
    AuthenticationError,
    DownloadError,
    init_settings,
    init_rate_limiter,
)


class TestSunoClientInitialization:
    """Test Suno client initialization."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_client_initialization(self):
        """Test client initializes correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "suno_session.json"
            client = SunoClient(session_file=session_file)

            assert client.session_file == session_file
            assert client.base_url == "https://studio-api.prod.suno.com"
            assert client.session is None

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_client_uses_settings_session_file(self):
        """Test client uses session file from settings."""
        client = SunoClient()
        assert client.session_file is not None


class TestSessionManagement:
    """Test session persistence and management."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_save_and_load_session(self):
        """Test session save and load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "test_session.json"
            client = SunoClient(session_file=session_file)

            # Mock storage state
            storage_state = {
                'cookies': [
                    {
                        'name': 'test_cookie',
                        'value': 'test_value',
                        'domain': '.suno.com',
                        'path': '/'
                    }
                ]
            }

            # Save session
            client._save_session(storage_state)

            # Verify file exists
            assert session_file.exists()

            # Load session
            loaded = client._load_session()
            assert loaded is True
            assert client.session is not None

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_session_ttl_expiration(self):
        """Test session TTL expiration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "test_session.json"

            # Create expired session
            expired_data = {
                'timestamp': time.time() - 7200,  # 2 hours ago (expired)
                'storage_state': {
                    'cookies': []
                }
            }

            with open(session_file, 'w') as f:
                json.dump(expired_data, f)

            client = SunoClient(session_file=session_file)
            loaded = client._load_session()

            # Should reject expired session
            assert loaded is False

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_session_verification(self):
        """Test session verification."""
        client = SunoClient()

        # No session
        assert client._verify_session() is False

        # Mock session
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        client.session = mock_session

        # Should be valid
        assert client._verify_session() is True

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_create_requests_session(self):
        """Test creating requests session from cookies."""
        client = SunoClient()

        cookies = [
            {
                'name': 'session_id',
                'value': 'abc123',
                'domain': '.suno.com',
                'path': '/'
            }
        ]

        client._create_requests_session(cookies)

        assert client.session is not None
        assert 'session_id' in [c.name for c in client.session.cookies]


class TestSongGeneration:
    """Test song generation functionality."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.suno_client.requests.Session")
    def test_generate_song_success(self, mock_session_class):
        """Test successful song generation."""
        init_rate_limiter(gemini_rpm=60, suno_rpm=60)  # Higher RPM for tests

        # Mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock verify session
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        # Mock generate response
        generate_response = MagicMock()
        generate_response.status_code = 200
        generate_response.json.return_value = {
            'clips': [
                {'id': 'clip-123', 'status': 'complete'},
                {'id': 'clip-456', 'status': 'complete'}
            ]
        }
        mock_session.post.return_value = generate_response

        client = SunoClient()
        client.session = mock_session

        result = client.generate_song(
            prompt="Test lyrics",
            tags="rock",
            title="Test Song",
            wait_for_completion=False
        )

        assert 'clips' in result
        assert len(result['clips']) == 2
        mock_session.post.assert_called_once()

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.suno_client.requests.Session")
    def test_generate_song_http_error(self, mock_session_class):
        """Test song generation HTTP error handling."""
        init_rate_limiter(gemini_rpm=60, suno_rpm=60)

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock verify
        mock_verify_response = MagicMock()
        mock_verify_response.status_code = 200

        # Mock failed generation
        mock_generate_response = MagicMock()
        mock_generate_response.status_code = 400
        mock_generate_response.text = "Bad Request"

        mock_session.get.return_value = mock_verify_response
        mock_session.post.return_value = mock_generate_response

        client = SunoClient()
        client.session = mock_session

        with pytest.raises(SunoAPIError):
            client.generate_song(prompt="Test", wait_for_completion=False)

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.suno_client.requests.Session")
    def test_generate_song_no_clips(self, mock_session_class):
        """Test error when no clips generated."""
        init_rate_limiter(gemini_rpm=60, suno_rpm=60)

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_verify_response = MagicMock()
        mock_verify_response.status_code = 200

        mock_generate_response = MagicMock()
        mock_generate_response.status_code = 200
        mock_generate_response.json.return_value = {'clips': []}

        mock_session.get.return_value = mock_verify_response
        mock_session.post.return_value = mock_generate_response

        client = SunoClient()
        client.session = mock_session

        with pytest.raises(SunoAPIError) as exc_info:
            client.generate_song(prompt="Test", wait_for_completion=False)

        assert "no clips" in str(exc_info.value).lower()


class TestCompletionWaiting:
    """Test waiting for clip completion."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_wait_for_completion_success(self):
        """Test successful completion waiting."""
        client = SunoClient()

        # Mock session
        mock_session = MagicMock()
        client.session = mock_session

        # Mock clips status
        complete_clips = [
            {'id': 'clip-1', 'status': 'complete'},
            {'id': 'clip-2', 'status': 'complete'}
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = complete_clips
        mock_session.get.return_value = mock_response

        result = client._wait_for_completion(['clip-1', 'clip-2'], timeout=10)

        assert len(result) == 2
        assert all(clip['status'] == 'complete' for clip in result)

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.suno_client.time.sleep")
    def test_wait_for_completion_timeout(self, mock_sleep):
        """Test completion timeout."""
        client = SunoClient()

        mock_session = MagicMock()
        client.session = mock_session

        # Mock clips that never complete
        pending_clips = [
            {'id': 'clip-1', 'status': 'pending'}
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = pending_clips
        mock_session.get.return_value = mock_response

        with pytest.raises(SunoAPIError) as exc_info:
            client._wait_for_completion(['clip-1'], timeout=1)

        assert "timeout" in str(exc_info.value).lower()

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_wait_for_completion_error_status(self):
        """Test error when clip has error status."""
        client = SunoClient()

        mock_session = MagicMock()
        client.session = mock_session

        # Mock clips with error
        error_clips = [
            {'id': 'clip-1', 'status': 'error', 'error_message': 'Generation failed'}
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = error_clips
        mock_session.get.return_value = mock_response

        with pytest.raises(SunoAPIError) as exc_info:
            client._wait_for_completion(['clip-1'], timeout=10)

        assert "failed" in str(exc_info.value).lower()


class TestAudioDownload:
    """Test audio download functionality."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.suno_client.requests.get")
    def test_download_mp3_success(self, mock_requests_get):
        """Test successful MP3 download."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = SunoClient()

            # Mock session
            mock_session = MagicMock()
            client.session = mock_session

            # Mock clip status
            clip_data = [
                {'id': 'clip-123', 'audio_url': 'https://example.com/audio.mp3'}
            ]

            mock_status_response = MagicMock()
            mock_status_response.status_code = 200
            mock_status_response.json.return_value = clip_data
            mock_session.get.return_value = mock_status_response

            # Mock MP3 download
            mock_download_response = MagicMock()
            mock_download_response.status_code = 200
            mock_download_response.iter_content.return_value = [b'fake_mp3_data']
            mock_requests_get.return_value = mock_download_response

            output_path = client._download_mp3('clip-123', Path(tmpdir))

            assert output_path is not None
            assert output_path.exists()
            assert output_path.suffix == '.mp3'

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_download_wav_success(self):
        """Test successful WAV download."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = SunoClient()

            mock_session = MagicMock()
            client.session = mock_session

            # Mock WAV conversion request
            mock_convert_response = MagicMock()
            mock_convert_response.status_code = 200

            # Mock WAV file ready
            mock_wav_response = MagicMock()
            mock_wav_response.status_code = 200
            mock_wav_response.content = b'fake_wav_data'

            mock_session.post.return_value = mock_convert_response
            mock_session.get.return_value = mock_wav_response

            output_path = client._download_wav('clip-123', Path(tmpdir))

            assert output_path is not None
            assert output_path.exists()
            assert output_path.suffix == '.wav'

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.suno_client.time.sleep")
    def test_download_wav_timeout(self, mock_sleep):
        """Test WAV download timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = SunoClient()

            mock_session = MagicMock()
            client.session = mock_session

            # Mock conversion success
            mock_convert_response = MagicMock()
            mock_convert_response.status_code = 200

            # Mock WAV not ready (404)
            mock_wav_response = MagicMock()
            mock_wav_response.status_code = 404

            mock_session.post.return_value = mock_convert_response
            mock_session.get.return_value = mock_wav_response

            # Should timeout and return None
            output_path = client._download_wav('clip-123', Path(tmpdir))

            assert output_path is None

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.suno_client.requests.get")
    def test_download_audio_both_formats(self, mock_requests_get):
        """Test downloading both WAV and MP3."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = SunoClient()

            mock_session = MagicMock()
            client.session = mock_session

            # Mock clip status for MP3
            clip_data = [
                {'id': 'clip-123', 'audio_url': 'https://example.com/audio.mp3'}
            ]

            # Mock responses
            mock_status_response = MagicMock()
            mock_status_response.status_code = 200
            mock_status_response.json.return_value = clip_data

            mock_wav_response = MagicMock()
            mock_wav_response.status_code = 200
            mock_wav_response.content = b'wav_data'

            mock_session.get.return_value = mock_status_response
            mock_session.post.return_value = MagicMock(status_code=200)

            # For WAV poll
            def side_effect(*args, **kwargs):
                url = args[0] if args else kwargs.get('url', '')
                if 'wav_file' in url:
                    return mock_wav_response
                return mock_status_response

            mock_session.get.side_effect = side_effect

            # Mock MP3 download
            mock_mp3_response = MagicMock()
            mock_mp3_response.status_code = 200
            mock_mp3_response.iter_content.return_value = [b'mp3_data']
            mock_requests_get.return_value = mock_mp3_response

            results = client.download_audio(
                'clip-123',
                Path(tmpdir),
                formats=["wav", "mp3"]
            )

            assert 'mp3' in results
            assert 'wav' in results


class TestClientCleanup:
    """Test client cleanup."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    def test_close_client(self):
        """Test closing client cleans up resources."""
        client = SunoClient()

        # Mock session
        mock_session = MagicMock()
        client.session = mock_session

        client.close()

        assert client.session is None
        mock_session.close.assert_called_once()

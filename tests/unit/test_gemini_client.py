"""
Unit tests for Gemini API client.

Tests cover lyrics generation, cover art generation, retry logic,
and rate limiting integration.
"""

import pytest
import time
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path

from src.clients.gemini_client import GeminiClient
from src.core import (
    GeminiAPIError,
    MaxRetriesExceededError,
    init_settings,
    init_rate_limiter,
)


class TestGeminiClientInitialization:
    """Test Gemini client initialization."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key_123"})
    def test_client_initialization(self):
        """Test client initializes correctly."""
        client = GeminiClient(api_key="test_key")
        assert client.api_key == "test_key"
        assert client.client is not None

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key_from_settings"})
    def test_client_uses_settings_api_key(self):
        """Test client uses API key from settings if not provided."""
        # When no explicit key provided, should use from settings
        client = GeminiClient()
        # Should have a valid API key set (from settings)
        assert client.api_key is not None
        assert len(client.api_key) > 0


class TestLyricsGeneration:
    """Test lyrics generation functionality."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.gemini_client.genai.Client")
    def test_generate_lyrics_success(self, mock_genai_client):
        """Test successful lyrics generation."""
        # Initialize rate limiter
        init_rate_limiter(gemini_rpm=60)

        # Mock response
        mock_response = MagicMock()
        mock_response.text = "Test lyrics\nGenerated successfully"
        mock_response.candidates = []

        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.return_value = mock_response
        mock_genai_client.return_value = mock_client_instance

        # Create client and generate
        client = GeminiClient(api_key="test_key")
        result = client.generate_lyrics(
            narrative_text="Test narrative",
            prompt_template="Test prompt: {narrative}",
            song_id="1.16.1"
        )

        # Verify result
        assert "lyrics" in result
        assert result["lyrics"] == "Test lyrics\nGenerated successfully"
        assert "model" in result
        assert "metadata" in result

        # Verify API was called
        mock_client_instance.models.generate_content.assert_called_once()

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.gemini_client.genai.Client")
    def test_generate_lyrics_with_reasoning(self, mock_genai_client):
        """Test lyrics generation extracts reasoning."""
        init_rate_limiter(gemini_rpm=60)

        # Mock response with reasoning
        mock_candidate = MagicMock()
        mock_candidate.grounding_metadata = "Reasoning process..."

        mock_response = MagicMock()
        mock_response.text = "Lyrics with reasoning"
        mock_response.candidates = [mock_candidate]

        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.return_value = mock_response
        mock_genai_client.return_value = mock_client_instance

        client = GeminiClient(api_key="test_key")
        result = client.generate_lyrics(
            narrative_text="Test narrative",
            prompt_template="Test prompt",
        )

        assert result["lyrics"] == "Lyrics with reasoning"
        assert result["reasoning"] is not None

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.gemini_client.genai.Client")
    def test_generate_lyrics_retry_on_failure(self, mock_genai_client):
        """Test retry logic on transient failures."""
        init_rate_limiter(gemini_rpm=60)

        # Mock client that fails twice then succeeds
        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.side_effect = [
            Exception("Transient error 1"),
            Exception("Transient error 2"),
            MagicMock(text="Success after retries", candidates=[])
        ]
        mock_genai_client.return_value = mock_client_instance

        client = GeminiClient(api_key="test_key")

        # Should succeed after retries
        result = client.generate_lyrics(
            narrative_text="Test",
            prompt_template="Prompt"
        )

        assert result["lyrics"] == "Success after retries"
        assert mock_client_instance.models.generate_content.call_count == 3

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.gemini_client.genai.Client")
    def test_generate_lyrics_max_retries_exceeded(self, mock_genai_client):
        """Test max retries exceeded raises error."""
        init_rate_limiter(gemini_rpm=60)

        # Mock client that always fails
        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.side_effect = Exception("Persistent error")
        mock_genai_client.return_value = mock_client_instance

        client = GeminiClient(api_key="test_key")

        # Should raise MaxRetriesExceededError
        with pytest.raises(GeminiAPIError) as exc_info:
            client.generate_lyrics(
                narrative_text="Test",
                prompt_template="Prompt"
            )

        assert "failed" in str(exc_info.value).lower()


class TestCoverArtGeneration:
    """Test cover art generation functionality."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.gemini_client.genai.Client")
    def test_generate_cover_success(self, mock_genai_client):
        """Test successful cover art generation."""
        init_rate_limiter(gemini_rpm=60)

        # Mock image response
        mock_image = MagicMock()
        mock_image_data = MagicMock()
        mock_image_data.data = b"fake_image_bytes_4k_resolution"
        mock_image.image = mock_image_data

        mock_response = MagicMock()
        mock_response.generated_images = [mock_image]

        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_images.return_value = mock_response
        mock_genai_client.return_value = mock_client_instance

        # Generate cover art
        client = GeminiClient(api_key="test_key")
        image_bytes = client.generate_cover_art(
            lyrics_text="Test lyrics",
            prompt_template="Generate Renaissance art",
            song_id="1.16.1"
        )

        assert image_bytes == b"fake_image_bytes_4k_resolution"
        mock_client_instance.models.generate_images.assert_called_once()

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.gemini_client.genai.Client")
    def test_generate_cover_no_images(self, mock_genai_client):
        """Test error when no images generated."""
        init_rate_limiter(gemini_rpm=60)

        # Mock response with no images
        mock_response = MagicMock()
        mock_response.generated_images = []

        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_images.return_value = mock_response
        mock_genai_client.return_value = mock_client_instance

        client = GeminiClient(api_key="test_key")

        with pytest.raises(GeminiAPIError) as exc_info:
            client.generate_cover_art(
                lyrics_text="Test",
                prompt_template="Prompt"
            )

        assert "failed" in str(exc_info.value).lower()

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.gemini_client.genai.Client")
    def test_generate_cover_retry_logic(self, mock_genai_client):
        """Test cover generation retry on failure."""
        init_rate_limiter(gemini_rpm=60)

        # Mock that fails once then succeeds
        mock_image = MagicMock()
        mock_image_data = MagicMock()
        mock_image_data.data = b"success_image"
        mock_image.image = mock_image_data

        mock_success_response = MagicMock()
        mock_success_response.generated_images = [mock_image]

        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_images.side_effect = [
            Exception("Network error"),
            mock_success_response
        ]
        mock_genai_client.return_value = mock_client_instance

        client = GeminiClient(api_key="test_key")
        result = client.generate_cover_art(
            lyrics_text="Test",
            prompt_template="Prompt"
        )

        assert result == b"success_image"
        assert mock_client_instance.models.generate_images.call_count == 2


class TestRetryLogic:
    """Test exponential backoff retry logic."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.gemini_client.time.sleep")
    @patch("src.clients.gemini_client.genai.Client")
    def test_retry_with_exponential_backoff(self, mock_genai_client, mock_sleep):
        """Test retry delays follow exponential backoff."""
        init_settings(google_api_key="test_key")
        init_rate_limiter(gemini_rpm=60)

        # Mock that fails 3 times
        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
            Exception("Error 3"),
        ]
        mock_genai_client.return_value = mock_client_instance

        client = GeminiClient(api_key="test_key")

        with pytest.raises(GeminiAPIError):
            client.generate_lyrics("test", "prompt")

        # Verify exponential backoff delays (2s, 4s)
        assert mock_sleep.call_count == 2
        calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert 2.0 in calls  # First retry delay
        assert 4.0 in calls  # Second retry delay


class TestModelAvailability:
    """Test model availability checking."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.gemini_client.genai.Client")
    def test_check_model_availability(self, mock_genai_client):
        """Test checking if a model is available."""
        # Mock model list
        mock_model1 = MagicMock()
        mock_model1.name = "gemini-2.0-flash-thinking-exp-1219"
        mock_model2 = MagicMock()
        mock_model2.name = "gemini-3-pro-image-preview"

        mock_client_instance = MagicMock()
        mock_client_instance.models.list.return_value = [mock_model1, mock_model2]
        mock_genai_client.return_value = mock_client_instance

        client = GeminiClient(api_key="test_key")

        # Check available model
        assert client.check_model_availability("gemini-2.0-flash") is True

        # Check unavailable model
        assert client.check_model_availability("nonexistent-model") is False

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.gemini_client.genai.Client")
    def test_get_available_models(self, mock_genai_client):
        """Test retrieving list of available models."""
        mock_model1 = MagicMock()
        mock_model1.name = "model-1"
        mock_model2 = MagicMock()
        mock_model2.name = "model-2"

        mock_client_instance = MagicMock()
        mock_client_instance.models.list.return_value = [mock_model1, mock_model2]
        mock_genai_client.return_value = mock_client_instance

        client = GeminiClient(api_key="test_key")
        models = client.get_available_models()

        assert len(models) == 2
        assert "model-1" in models
        assert "model-2" in models


class TestRateLimitingIntegration:
    """Test integration with rate limiter."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.gemini_client.genai.Client")
    def test_rate_limiting_applied(self, mock_genai_client):
        """Test that rate limiting is applied to API calls."""
        # Use a moderate RPM
        limiter = init_rate_limiter(gemini_rpm=60)  # 0.8 per second with 80% throttle

        mock_response = MagicMock()
        mock_response.text = "Test"
        mock_response.candidates = []

        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.return_value = mock_response
        mock_genai_client.return_value = mock_client_instance

        client = GeminiClient(api_key="test_key")

        # Make 4 requests (will exceed initial burst capacity of 1.2)
        start = time.time()
        for i in range(4):
            client.generate_lyrics(f"Test {i}", "Prompt")
        elapsed = time.time() - start

        # With 60 RPM at 80% = 48 RPM = 0.8/sec = 1.25s per request
        # First ~1 request uses burst, remaining 3 are rate limited
        # Should take at least ~3 * 1.25 = 3.75s
        assert elapsed >= 2.5  # Allow tolerance for burst


class TestErrorHandling:
    """Test error handling and reporting."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.gemini_client.genai.Client")
    def test_lyrics_generation_wraps_errors(self, mock_genai_client):
        """Test that errors are wrapped in GeminiAPIError."""
        init_rate_limiter(gemini_rpm=60)

        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.side_effect = ValueError("Test error")
        mock_genai_client.return_value = mock_client_instance

        client = GeminiClient(api_key="test_key")

        with pytest.raises(GeminiAPIError) as exc_info:
            client.generate_lyrics("test", "prompt", song_id="1.16.1")

        assert "failed" in str(exc_info.value).lower()
        # Check that error details contain context
        assert exc_info.value.details is not None
        assert "text_length" in exc_info.value.details

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test_key"})
    @patch("src.clients.gemini_client.genai.Client")
    def test_cover_generation_wraps_errors(self, mock_genai_client):
        """Test that cover errors are wrapped."""
        init_rate_limiter(gemini_rpm=60)

        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_images.side_effect = RuntimeError("Image error")
        mock_genai_client.return_value = mock_client_instance

        client = GeminiClient(api_key="test_key")

        with pytest.raises(GeminiAPIError) as exc_info:
            client.generate_cover_art("lyrics", "prompt", song_id="1.16.2")

        assert "failed" in str(exc_info.value).lower()
        # Check that error details contain context
        assert exc_info.value.details is not None
        assert "lyrics_length" in exc_info.value.details

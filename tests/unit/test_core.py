"""
Unit tests for core utilities module.

Tests cover configuration management, logging, error handling,
and rate limiting functionality.
"""

import os
import time
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core import (
    get_settings,
    init_settings,
    get_logger,
    get_rate_limiter,
    init_rate_limiter,
    MissingAPIKeyError,
    InvalidConfigurationError,
    RateLimitError,
    SunoMusicGeneratorError,
)
from src.core.config import Settings, GeminiConfig, SunoConfig
from src.core.rate_limiter import TokenBucket


class TestErrors:
    """Test custom exception hierarchy."""

    def test_base_error(self):
        """Test base exception with message and details."""
        error = SunoMusicGeneratorError(
            "Test error",
            details={"key": "value"}
        )
        assert str(error) == "Test error (key=value)"
        assert error.message == "Test error"
        assert error.details == {"key": "value"}

    def test_error_without_details(self):
        """Test exception without details."""
        error = SunoMusicGeneratorError("Simple error")
        assert str(error) == "Simple error"
        assert error.details == {}

    def test_rate_limit_error(self):
        """Test RateLimitError with retry_after."""
        error = RateLimitError(
            "Rate limit exceeded",
            retry_after=60.0
        )
        assert error.retry_after == 60.0

    def test_missing_api_key_error(self):
        """Test MissingAPIKeyError."""
        error = MissingAPIKeyError("API key not found")
        assert isinstance(error, SunoMusicGeneratorError)


class TestConfiguration:
    """Test configuration management."""

    def test_gemini_config_validation(self):
        """Test Gemini configuration validation."""
        # Valid config
        config = GeminiConfig(api_key="test_key_123")
        assert config.api_key == "test_key_123"
        assert config.lyrics_model == "gemini-2.0-flash-thinking-exp-1219"
        assert config.cover_model == "gemini-3-pro-image-preview"

    def test_gemini_config_invalid_key(self):
        """Test validation fails with invalid API key."""
        with pytest.raises(MissingAPIKeyError):
            GeminiConfig(api_key="")

        with pytest.raises(MissingAPIKeyError):
            GeminiConfig(api_key="your_google_api_key_here")

    def test_gemini_config_effective_rpm(self):
        """Test effective RPM calculation."""
        config = GeminiConfig(
            api_key="test_key",
            rpm_limit=60,
            throttle_percentage=0.8
        )
        assert config.effective_rpm == 48.0
        assert config.min_delay_seconds == 60.0 / 48.0

    def test_gemini_config_invalid_throttle(self):
        """Test validation fails with invalid throttle."""
        with pytest.raises(InvalidConfigurationError):
            GeminiConfig(
                api_key="test_key",
                throttle_percentage=1.5
            )

    def test_suno_config_defaults(self):
        """Test Suno configuration defaults."""
        config = SunoConfig()
        assert config.base_url == "https://studio-api.prod.suno.com"
        assert config.min_delay == 2.0
        assert config.max_delay == 5.0
        assert config.max_retries == 3

    def test_paths_config(self):
        """Test paths configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Settings(
                google_api_key="test_key_123",
                paths={
                    "project_root": tmpdir,
                    "songs_dir": Path(tmpdir) / "Songs"
                }
            )

            song_dir = config.paths.get_song_dir("1.16.1")
            assert str(song_dir).endswith("Songs/1.16.1")

            text_file = config.paths.get_text_file("1.16.1")
            assert str(text_file).endswith("Songs/1.16.1/Text/1.16.1.txt")

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key_from_env"})
    def test_settings_from_env(self):
        """Test settings load from environment."""
        settings = Settings()
        assert settings.google_api_key == "test_key_from_env"
        assert settings.gemini.api_key == "test_key_from_env"

    def test_settings_missing_api_key(self):
        """Test that GeminiConfig validation rejects empty API key."""
        # Test GeminiConfig directly (where validation happens)
        with pytest.raises(MissingAPIKeyError):
            GeminiConfig(api_key="")

        with pytest.raises(MissingAPIKeyError):
            GeminiConfig(api_key="your_google_api_key_here")

    def test_settings_validate_parallel_tasks(self):
        """Test parallel tasks validation."""
        with pytest.raises(InvalidConfigurationError):
            Settings(
                google_api_key="test_key",
                parallel_tasks=0
            )

    def test_settings_to_dict_redacts_keys(self):
        """Test that to_dict redacts sensitive information."""
        settings = Settings(google_api_key="secret_key_123")
        data = settings.to_dict()
        assert data["google_api_key"] == "***REDACTED***"
        assert data["gemini"]["api_key"] == "***REDACTED***"

    def test_get_settings_singleton(self):
        """Test get_settings returns singleton."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
            settings1 = get_settings()
            settings2 = get_settings()
            assert settings1 is settings2

    def test_init_settings_override(self):
        """Test init_settings accepts custom values."""
        settings = init_settings(
            google_api_key="override_key_test_123",
            parallel_tasks=4
        )
        # The settings should use our override value
        assert settings.parallel_tasks == 4
        # gemini config should be initialized with provided key
        assert settings.gemini is not None


class TestLogging:
    """Test logging functionality."""

    def test_get_logger(self):
        """Test logger creation."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
            logger = get_logger("test_logger")
            assert logger.name == "test_logger"

    def test_logger_singleton(self):
        """Test logger returns same instance for same name."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
            logger1 = get_logger("test_logger")
            logger2 = get_logger("test_logger")
            assert logger1 is logger2

    def test_logger_format_message(self):
        """Test message formatting with context."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
            logger = get_logger("test")
            formatted = logger._format_message(
                "Test message",
                {"key1": "value1", "key2": "value2"}
            )
            assert "Test message" in formatted
            assert "key1=value1" in formatted
            assert "key2=value2" in formatted

    def test_logger_log_operation(self):
        """Test operation logging."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
            logger = get_logger("test")
            # Should not raise
            logger.log_operation("test_op", "started")
            logger.log_operation("test_op", "completed")

    def test_logger_log_api_call(self):
        """Test API call logging."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
            logger = get_logger("test")
            logger.log_api_call(
                api="Gemini",
                endpoint="/generate",
                method="POST",
                status_code=200,
                duration=1.23
            )

    def test_logger_log_generation(self):
        """Test generation logging."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
            logger = get_logger("test")
            logger.log_generation(
                song_id="1.16.1",
                stage="lyrics",
                status="started"
            )


class TestTokenBucket:
    """Test token bucket rate limiting."""

    def test_token_bucket_creation(self):
        """Test token bucket initialization."""
        bucket = TokenBucket(capacity=10.0, rate=1.0)
        assert bucket.capacity == 10.0
        assert bucket.rate == 1.0
        assert bucket.tokens == 10.0

    def test_token_bucket_consume(self):
        """Test consuming tokens."""
        bucket = TokenBucket(capacity=10.0, rate=1.0)
        result = bucket.consume(5.0, blocking=False)
        assert result is True
        assert bucket.tokens == 5.0

    def test_token_bucket_insufficient_tokens(self):
        """Test non-blocking consume with insufficient tokens."""
        bucket = TokenBucket(capacity=10.0, rate=1.0)
        bucket.consume(9.0, blocking=False)
        result = bucket.consume(5.0, blocking=False)
        assert result is False

    def test_token_bucket_refill(self):
        """Test token refill over time."""
        bucket = TokenBucket(capacity=10.0, rate=2.0)  # 2 tokens per second
        bucket.consume(8.0, blocking=False)
        time.sleep(1.1)  # Wait for refill
        assert bucket.get_available_tokens() >= 2.0

    def test_token_bucket_capacity_error(self):
        """Test error when requesting more than capacity."""
        bucket = TokenBucket(capacity=10.0, rate=1.0)
        with pytest.raises(RateLimitError):
            bucket.consume(15.0)

    def test_token_bucket_wait_time(self):
        """Test wait time calculation."""
        bucket = TokenBucket(capacity=10.0, rate=2.0)
        bucket.consume(9.0, blocking=False)
        wait_time = bucket.get_wait_time(5.0)
        # Need 4 more tokens at rate of 2/sec = 2 seconds
        assert wait_time == pytest.approx(2.0, rel=0.1)


class TestRateLimiter:
    """Test rate limiter."""

    def test_rate_limiter_creation(self):
        """Test rate limiter initialization."""
        limiter = get_rate_limiter()
        assert limiter is not None

    def test_add_bucket(self):
        """Test adding a rate limiting bucket."""
        limiter = init_rate_limiter(gemini_rpm=60, suno_rpm=30)
        assert "gemini" in limiter.buckets
        assert "suno" in limiter.buckets

    def test_acquire_tokens(self):
        """Test acquiring tokens."""
        limiter = init_rate_limiter(gemini_rpm=60)
        result = limiter.acquire("gemini", tokens=1.0, blocking=False)
        assert result is True

    def test_acquire_invalid_service(self):
        """Test acquiring from non-existent service."""
        limiter = init_rate_limiter()
        with pytest.raises(ValueError):
            limiter.acquire("invalid_service")

    def test_wait_time(self):
        """Test wait time calculation."""
        limiter = init_rate_limiter(gemini_rpm=60)
        bucket = limiter.get_bucket("gemini")
        bucket.consume(bucket.capacity, blocking=False)
        wait_time = limiter.wait_time("gemini", tokens=1.0)
        assert wait_time > 0

    def test_get_status(self):
        """Test status retrieval."""
        limiter = init_rate_limiter(gemini_rpm=60)
        status = limiter.get_status("gemini")
        assert "available_tokens" in status
        assert "capacity" in status
        assert "rate" in status

    def test_get_status_all_services(self):
        """Test status for all services."""
        limiter = init_rate_limiter(gemini_rpm=60, suno_rpm=30)
        status = limiter.get_status()
        assert "gemini" in status
        assert "suno" in status


class TestIntegration:
    """Integration tests for core module."""

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test_integration_key"})
    def test_full_initialization(self):
        """Test full system initialization."""
        # Initialize settings
        settings = init_settings(parallel_tasks=2)
        assert settings.google_api_key == "test_integration_key"

        # Initialize logger
        logger = get_logger("integration_test")
        logger.info("Integration test message")

        # Initialize rate limiter
        limiter = init_rate_limiter(gemini_rpm=60, suno_rpm=30)
        assert limiter.acquire("gemini", blocking=False)

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"})
    def test_rate_limiting_integration(self):
        """Test rate limiting with actual timing."""
        limiter = init_rate_limiter(gemini_rpm=120)  # 2 per second
        bucket = limiter.get_bucket("gemini")

        # Consume all tokens
        bucket.consume(bucket.capacity, blocking=False)

        # Next request should wait
        start = time.time()
        result = limiter.acquire("gemini", tokens=1.0, blocking=True)
        elapsed = time.time() - start

        assert result is True
        assert elapsed >= 0.4  # Should wait at least 0.5s (with some tolerance)

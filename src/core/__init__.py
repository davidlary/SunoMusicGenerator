"""
Core utilities for SunoMusicGenerator.

This module provides configuration management, logging, error handling,
and rate limiting for the entire application.
"""

from .config import (
    Settings,
    GeminiConfig,
    SunoConfig,
    PathsConfig,
    LoggingConfig,
    get_settings,
    init_settings,
)

from .logger import (
    CPFLogger,
    get_logger,
    setup_root_logger,
)

from .errors import (
    SunoMusicGeneratorError,
    ConfigurationError,
    MissingAPIKeyError,
    InvalidConfigurationError,
    APIError,
    GeminiAPIError,
    SunoAPIError,
    RateLimitError,
    AuthenticationError,
    NetworkError,
    StateError,
    StateFileError,
    VersionError,
    MetadataError,
    PipelineError,
    LyricsGenerationError,
    SongGenerationError,
    CoverGenerationError,
    DownloadError,
    FileSystemError,
    FileNotFoundError,
    FileWriteError,
    DirectoryError,
    ValidationError,
    InvalidInputError,
    InvalidFormatError,
    RetryableError,
    MaxRetriesExceededError,
)

from .rate_limiter import (
    TokenBucket,
    RateLimiter,
    get_rate_limiter,
    init_rate_limiter,
)

__all__ = [
    # Config
    "Settings",
    "GeminiConfig",
    "SunoConfig",
    "PathsConfig",
    "LoggingConfig",
    "get_settings",
    "init_settings",
    # Logger
    "CPFLogger",
    "get_logger",
    "setup_root_logger",
    # Errors
    "SunoMusicGeneratorError",
    "ConfigurationError",
    "MissingAPIKeyError",
    "InvalidConfigurationError",
    "APIError",
    "GeminiAPIError",
    "SunoAPIError",
    "RateLimitError",
    "AuthenticationError",
    "NetworkError",
    "StateError",
    "StateFileError",
    "VersionError",
    "MetadataError",
    "PipelineError",
    "LyricsGenerationError",
    "SongGenerationError",
    "CoverGenerationError",
    "DownloadError",
    "FileSystemError",
    "FileNotFoundError",
    "FileWriteError",
    "DirectoryError",
    "ValidationError",
    "InvalidInputError",
    "InvalidFormatError",
    "RetryableError",
    "MaxRetriesExceededError",
    # Rate Limiter
    "TokenBucket",
    "RateLimiter",
    "get_rate_limiter",
    "init_rate_limiter",
]

"""
Custom exception hierarchy for SunoMusicGenerator.

This module defines all custom exceptions used throughout the application,
organized in a clear hierarchy for easy error handling and debugging.
"""

from typing import Optional, Dict, Any


class SunoMusicGeneratorError(Exception):
    """Base exception for all SunoMusicGenerator errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


# Configuration Errors
class ConfigurationError(SunoMusicGeneratorError):
    """Raised when there's a configuration issue."""
    pass


class MissingAPIKeyError(ConfigurationError):
    """Raised when a required API key is missing."""
    pass


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values are invalid."""
    pass


# API Client Errors
class APIError(SunoMusicGeneratorError):
    """Base class for API-related errors."""
    pass


class GeminiAPIError(APIError):
    """Raised when Gemini API calls fail."""
    pass


class SunoAPIError(APIError):
    """Raised when Suno API calls fail."""
    pass


class RateLimitError(APIError):
    """Raised when API rate limits are exceeded."""

    def __init__(self, message: str, retry_after: Optional[float] = None,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.retry_after = retry_after


class AuthenticationError(APIError):
    """Raised when authentication fails."""
    pass


class NetworkError(APIError):
    """Raised when network requests fail."""
    pass


# State Management Errors
class StateError(SunoMusicGeneratorError):
    """Base class for state management errors."""
    pass


class StateFileError(StateError):
    """Raised when state file operations fail."""
    pass


class VersionError(StateError):
    """Raised when version-related operations fail."""
    pass


class MetadataError(StateError):
    """Raised when metadata operations fail."""
    pass


# Pipeline Errors
class PipelineError(SunoMusicGeneratorError):
    """Base class for pipeline execution errors."""
    pass


class LyricsGenerationError(PipelineError):
    """Raised when lyrics generation fails."""
    pass


class SongGenerationError(PipelineError):
    """Raised when song generation fails."""
    pass


class CoverGenerationError(PipelineError):
    """Raised when cover art generation fails."""
    pass


class DownloadError(PipelineError):
    """Raised when file downloads fail."""
    pass


# File System Errors
class FileSystemError(SunoMusicGeneratorError):
    """Base class for file system errors."""
    pass


class FileNotFoundError(FileSystemError):
    """Raised when a required file is not found."""
    pass


class FileWriteError(FileSystemError):
    """Raised when writing files fails."""
    pass


class DirectoryError(FileSystemError):
    """Raised when directory operations fail."""
    pass


# Validation Errors
class ValidationError(SunoMusicGeneratorError):
    """Base class for validation errors."""
    pass


class InvalidInputError(ValidationError):
    """Raised when input validation fails."""
    pass


class InvalidFormatError(ValidationError):
    """Raised when data format validation fails."""
    pass


# Retry Errors
class RetryableError(SunoMusicGeneratorError):
    """Base class for errors that should trigger retry logic."""

    def __init__(self, message: str, max_retries: int = 3,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.max_retries = max_retries


class MaxRetriesExceededError(SunoMusicGeneratorError):
    """Raised when maximum retry attempts are exceeded."""

    def __init__(self, message: str, attempts: int,
                 original_error: Optional[Exception] = None,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.attempts = attempts
        self.original_error = original_error

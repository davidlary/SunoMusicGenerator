"""
Configuration management for SunoMusicGenerator.

This module loads environment variables, validates API keys, manages model
selection, and provides centralized configuration for the entire application.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

from .errors import (
    MissingAPIKeyError,
    InvalidConfigurationError,
    ConfigurationError,
)


# Load environment variables from .env file
ENV_PATH = Path(__file__).parent.parent.parent / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


class GeminiConfig(BaseModel):
    """Configuration for Gemini API."""

    api_key: str
    lyrics_model: str = "gemini-2.0-flash-thinking-exp-1219"
    cover_model: str = "gemini-3-pro-image-preview"
    max_retries: int = 3
    retry_delays: list[float] = Field(default_factory=lambda: [2.0, 4.0, 8.0])
    timeout: int = 120
    rpm_limit: int = 60  # Requests per minute
    throttle_percentage: float = 0.80  # Use 80% of limit

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate that API key is not empty or placeholder."""
        if not v or v == "your_google_api_key_here":
            raise MissingAPIKeyError(
                "GOOGLE_API_KEY is not set. Please configure it in .env file."
            )
        return v

    @field_validator("throttle_percentage")
    @classmethod
    def validate_throttle(cls, v: float) -> float:
        """Validate throttle percentage is between 0 and 1."""
        if not 0 < v <= 1:
            raise InvalidConfigurationError(
                "throttle_percentage must be between 0 and 1",
                details={"value": v}
            )
        return v

    @property
    def effective_rpm(self) -> float:
        """Calculate effective RPM based on throttle percentage."""
        return self.rpm_limit * self.throttle_percentage

    @property
    def min_delay_seconds(self) -> float:
        """Calculate minimum delay between requests in seconds."""
        return 60.0 / self.effective_rpm


class SunoConfig(BaseModel):
    """Configuration for Suno API."""

    base_url: str = "https://studio-api.prod.suno.com"
    session_file: Path = Field(
        default_factory=lambda: Path("suno_session.json")
    )
    session_ttl: int = 3600  # Session TTL in seconds (1 hour)
    min_delay: float = 2.0  # Minimum delay between requests
    max_delay: float = 5.0  # Maximum delay between requests
    max_retries: int = 3
    retry_delay: float = 2.0
    wav_poll_interval: float = 2.0  # Seconds between WAV conversion polls
    wav_poll_timeout: int = 120  # Maximum seconds to wait for WAV conversion

    @field_validator("session_file")
    @classmethod
    def resolve_session_file(cls, v: Path) -> Path:
        """Resolve session file path relative to project root."""
        if not v.is_absolute():
            project_root = Path(__file__).parent.parent.parent
            return project_root / v
        return v


class PathsConfig(BaseModel):
    """Configuration for file paths and directories."""

    project_root: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent
    )
    songs_dir: Path = Field(default_factory=lambda: Path("Songs"))
    state_file: Path = Field(default_factory=lambda: Path("Songs/state_tracking.json"))
    prompts_dir: Path = Field(default_factory=lambda: Path("."))

    @field_validator("songs_dir", "prompts_dir")
    @classmethod
    def resolve_path(cls, v: Path) -> Path:
        """Resolve paths relative to project root."""
        if not v.is_absolute():
            project_root = Path(__file__).parent.parent.parent
            return project_root / v
        return v

    @field_validator("state_file")
    @classmethod
    def resolve_state_file(cls, v: Path) -> Path:
        """Resolve state file path and ensure parent directory exists."""
        if not v.is_absolute():
            project_root = Path(__file__).parent.parent.parent
            v = project_root / v
        v.parent.mkdir(parents=True, exist_ok=True)
        return v

    def get_song_dir(self, song_id: str) -> Path:
        """Get directory path for a specific song."""
        return self.songs_dir / song_id

    def get_text_file(self, song_id: str) -> Path:
        """Get path to source text file for a song."""
        return self.get_song_dir(song_id) / "Text" / f"{song_id}.txt"

    def get_lyrics_file(self, song_id: str) -> Path:
        """Get path to active lyrics file for a song."""
        return self.get_song_dir(song_id) / "Lyrics" / f"{song_id}.txt"

    def get_lyrics_version_dir(self, song_id: str) -> Path:
        """Get directory for lyrics versions."""
        return self.get_song_dir(song_id) / "Lyrics" / "versions"

    def get_audio_dir(self, song_id: str) -> Path:
        """Get directory for audio files."""
        return self.get_song_dir(song_id) / "Audio"

    def get_cover_dir(self, song_id: str) -> Path:
        """Get directory for cover art."""
        return self.get_song_dir(song_id) / "Cover"


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_dir: Path = Field(default_factory=lambda: Path(".cpf/logs"))
    enable_console: bool = True
    enable_file: bool = True
    max_bytes: int = 10 * 1024 * 1024  # 10 MB
    backup_count: int = 5

    @field_validator("log_dir")
    @classmethod
    def resolve_log_dir(cls, v: Path) -> Path:
        """Resolve log directory and ensure it exists."""
        if not v.is_absolute():
            project_root = Path(__file__).parent.parent.parent
            v = project_root / v
        v.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in valid_levels:
            raise InvalidConfigurationError(
                f"Invalid logging level: {v}",
                details={"valid_levels": valid_levels}
            )
        return v


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Keys
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")

    # Sub-configurations
    gemini: Optional[GeminiConfig] = None
    suno: SunoConfig = Field(default_factory=SunoConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # General settings
    debug: bool = False
    parallel_tasks: int = 1  # Number of parallel generation tasks

    def __init__(self, **kwargs):
        """Initialize settings and validate configuration."""
        super().__init__(**kwargs)

        # Initialize Gemini config with API key
        if not self.gemini and self.google_api_key:
            self.gemini = GeminiConfig(api_key=self.google_api_key)
        elif not self.gemini:
            raise MissingAPIKeyError(
                "GOOGLE_API_KEY must be set in environment variables or .env file"
            )

    @field_validator("parallel_tasks")
    @classmethod
    def validate_parallel_tasks(cls, v: int) -> int:
        """Validate parallel tasks is positive."""
        if v < 1:
            raise InvalidConfigurationError(
                "parallel_tasks must be at least 1",
                details={"value": v}
            )
        return v

    def validate_environment(self) -> None:
        """Validate that the environment is properly configured."""
        # Check that critical directories exist
        if not self.paths.songs_dir.exists():
            self.paths.songs_dir.mkdir(parents=True, exist_ok=True)

        # Validate API key
        if not self.gemini or not self.gemini.api_key:
            raise MissingAPIKeyError(
                "GOOGLE_API_KEY is required but not set"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary (excluding sensitive data)."""
        data = self.model_dump()
        # Redact API key
        if "google_api_key" in data:
            data["google_api_key"] = "***REDACTED***"
        if "gemini" in data and data["gemini"]:
            data["gemini"]["api_key"] = "***REDACTED***"
        return data


# Global settings instance
_settings: Optional[Settings] = None


def get_settings(reload: bool = False) -> Settings:
    """
    Get the global settings instance.

    Args:
        reload: If True, reload settings from environment

    Returns:
        Settings instance
    """
    global _settings
    if _settings is None or reload:
        _settings = Settings()
        _settings.validate_environment()
    return _settings


def init_settings(**kwargs) -> Settings:
    """
    Initialize settings with custom values.

    Args:
        **kwargs: Configuration overrides

    Returns:
        Settings instance
    """
    global _settings
    _settings = Settings(**kwargs)
    _settings.validate_environment()
    return _settings

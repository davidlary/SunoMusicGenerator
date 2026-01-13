"""
CPF-compatible logging system for SunoMusicGenerator.

This module provides structured logging with console and file outputs,
color-coded log levels, and integration with the Context-Preserving Framework.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler
import colorlog

from .config import get_settings


class CPFLogger:
    """
    CPF-compatible logger with console and file outputs.

    Features:
    - Color-coded console output
    - Rotating file logs
    - Structured log format
    - Context preservation
    """

    def __init__(self, name: str, level: Optional[str] = None):
        """
        Initialize logger.

        Args:
            name: Logger name (typically __name__)
            level: Optional logging level override
        """
        self.settings = get_settings()
        self.name = name
        self.logger = logging.getLogger(name)

        # Set level
        log_level = level or self.settings.logging.level
        self.logger.setLevel(getattr(logging, log_level))

        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()

    def _setup_handlers(self):
        """Set up console and file handlers."""
        # Console handler with colors
        if self.settings.logging.enable_console:
            console_handler = colorlog.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)

            console_format = colorlog.ColoredFormatter(
                "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s%(reset)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bg_white",
                },
            )
            console_handler.setFormatter(console_format)
            self.logger.addHandler(console_handler)

        # File handler with rotation
        if self.settings.logging.enable_file:
            log_file = self.settings.logging.log_dir / f"{self.name.replace('.', '_')}.log"
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=self.settings.logging.max_bytes,
                backupCount=self.settings.logging.backup_count,
            )
            file_handler.setLevel(logging.DEBUG)

            file_format = logging.Formatter(
                self.settings.logging.format,
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(self._format_message(message, kwargs))

    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(self._format_message(message, kwargs))

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(self._format_message(message, kwargs))

    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Log error message."""
        self.logger.error(self._format_message(message, kwargs), exc_info=exc_info)

    def critical(self, message: str, exc_info: bool = False, **kwargs):
        """Log critical message."""
        self.logger.critical(self._format_message(message, kwargs), exc_info=exc_info)

    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        self.logger.exception(self._format_message(message, kwargs))

    def _format_message(self, message: str, context: dict) -> str:
        """
        Format message with context.

        Args:
            message: Log message
            context: Additional context dictionary

        Returns:
            Formatted message string
        """
        if not context:
            return message

        context_str = " | ".join(f"{k}={v}" for k, v in context.items())
        return f"{message} | {context_str}"

    def log_operation(self, operation: str, status: str, **kwargs):
        """
        Log an operation with status.

        Args:
            operation: Operation name
            status: Status (started, completed, failed, etc.)
            **kwargs: Additional context
        """
        message = f"[{operation}] {status}"
        if status.lower() in ["failed", "error"]:
            self.error(message, **kwargs)
        elif status.lower() == "warning":
            self.warning(message, **kwargs)
        else:
            self.info(message, **kwargs)

    def log_api_call(
        self,
        api: str,
        endpoint: str,
        method: str = "POST",
        status_code: Optional[int] = None,
        duration: Optional[float] = None,
        **kwargs
    ):
        """
        Log an API call.

        Args:
            api: API name (e.g., "Gemini", "Suno")
            endpoint: API endpoint
            method: HTTP method
            status_code: Response status code
            duration: Request duration in seconds
            **kwargs: Additional context
        """
        context = {
            "api": api,
            "endpoint": endpoint,
            "method": method,
            **kwargs
        }

        if status_code:
            context["status_code"] = status_code
        if duration:
            context["duration"] = f"{duration:.2f}s"

        message = f"API Call: {method} {endpoint}"

        if status_code and status_code >= 400:
            self.error(message, **context)
        else:
            self.info(message, **context)

    def log_generation(
        self,
        song_id: str,
        stage: str,
        status: str,
        **kwargs
    ):
        """
        Log a generation pipeline stage.

        Args:
            song_id: Song identifier
            stage: Generation stage (lyrics, audio, cover)
            status: Status (started, completed, failed)
            **kwargs: Additional context
        """
        context = {
            "song_id": song_id,
            "stage": stage,
            **kwargs
        }

        message = f"Generation [{stage}] {status}"

        if status.lower() in ["failed", "error"]:
            self.error(message, **context)
        else:
            self.info(message, **context)


# Global logger cache
_loggers = {}


def get_logger(name: str, level: Optional[str] = None) -> CPFLogger:
    """
    Get or create a logger instance.

    Args:
        name: Logger name (typically __name__)
        level: Optional logging level override

    Returns:
        CPFLogger instance
    """
    if name not in _loggers:
        _loggers[name] = CPFLogger(name, level)
    return _loggers[name]


def setup_root_logger():
    """Set up the root logger with basic configuration."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.logging.level),
        format=settings.logging.format,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

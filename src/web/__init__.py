"""
Web API module for SunoMusicGenerator.

Provides FastAPI REST API for generating lyrics, audio, and cover art.
"""

from .app import app

__all__ = ["app"]

"""
API clients for SunoMusicGenerator.

This module provides clients for interacting with external APIs:
- Gemini API for lyrics and cover art generation
- Suno API for music generation
"""

from .gemini_client import GeminiClient
from .suno_client import SunoClient

__all__ = [
    "GeminiClient",
    "SunoClient",
]

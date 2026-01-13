"""
Generation pipelines for SunoMusicGenerator.

This module provides end-to-end pipelines for generating
lyrics, songs, and cover art.
"""

from .lyrics_generator import LyricsGenerator
from .song_generator import SongGenerator
from .cover_generator import CoverGenerator

__all__ = [
    "LyricsGenerator",
    "SongGenerator",
    "CoverGenerator",
]

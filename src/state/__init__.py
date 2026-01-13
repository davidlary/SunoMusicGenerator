"""
State management for SunoMusicGenerator.

This module provides state tracking, versioning, and metadata management
for the song generation pipeline.
"""

from .state_tracker import StateTracker
from .metadata_manager import MetadataManager

__all__ = [
    "StateTracker",
    "MetadataManager",
]

"""
State tracking for song generation pipeline.

This module manages the state_tracking.json file that tracks all songs,
their versions, and generation status.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from ..core import (
    get_logger,
    get_settings,
    StateFileError,
    VersionError,
)

logger = get_logger(__name__)


@dataclass
class Version:
    """Represents a version of generated content."""
    timestamp: str
    path: str
    prompt: Optional[str] = None
    model: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SourceInfo:
    """Source text information."""
    path: str
    title: str
    content_hash: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class SongState:
    """Complete state for a song."""
    song_id: str
    source: SourceInfo
    lyrics: Optional[Dict[str, Any]] = None
    audio: Optional[Dict[str, Any]] = None
    cover: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            "song_id": self.song_id,
            "source": self.source.to_dict()
        }
        if self.lyrics:
            data["lyrics"] = self.lyrics
        if self.audio:
            data["audio"] = self.audio
        if self.cover:
            data["cover"] = self.cover
        return data


class StateTracker:
    """
    Manages state tracking for the song generation pipeline.

    Features:
    - Tracks all songs and their generation status
    - Version management for lyrics, audio, cover art
    - SHA256 hashing for change detection
    - Atomic file updates
    - Timestamp-based versioning (YYYYMMDD-HHMMSS)
    """

    def __init__(self, state_file: Optional[Path] = None):
        """
        Initialize state tracker.

        Args:
            state_file: Optional path to state file
        """
        self.settings = get_settings()
        self.state_file = state_file or self.settings.paths.state_file
        self.state: Dict[str, Any] = {"songs": {}}

        # Load existing state
        self._load_state()

        logger.info(
            "State tracker initialized",
            state_file=str(self.state_file),
            song_count=len(self.state["songs"])
        )

    def _load_state(self):
        """Load state from file."""
        if not self.state_file.exists():
            logger.info("No existing state file, starting fresh")
            return

        try:
            with open(self.state_file, 'r') as f:
                self.state = json.load(f)

            logger.info(
                f"State loaded: {len(self.state.get('songs', {}))} songs"
            )

        except Exception as e:
            logger.error(f"Failed to load state: {e}", exc_info=True)
            raise StateFileError(
                f"Failed to load state from {self.state_file}"
            ) from e

    def _save_state(self):
        """Save state to file (atomic write)."""
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write: write to temp file then rename
            temp_file = self.state_file.with_suffix('.tmp')

            with open(temp_file, 'w') as f:
                json.dump(self.state, f, indent=2)

            # Atomic rename
            temp_file.replace(self.state_file)

            logger.debug("State saved")

        except Exception as e:
            logger.error(f"Failed to save state: {e}", exc_info=True)
            raise StateFileError(
                f"Failed to save state to {self.state_file}"
            ) from e

    @staticmethod
    def generate_timestamp() -> str:
        """
        Generate timestamp for versioning.

        Returns:
            Timestamp string (YYYYMMDD-HHMMSS)
        """
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    @staticmethod
    def compute_hash(content: str) -> str:
        """
        Compute SHA256 hash of content.

        Args:
            content: Content to hash

        Returns:
            Hex digest of hash
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def register_song(
        self,
        song_id: str,
        source_path: Path,
        title: str,
        content: str
    ):
        """
        Register a new song in the state.

        Args:
            song_id: Song identifier (e.g., "1.16.1")
            source_path: Path to source text file
            title: Song title
            content: Source content
        """
        # Compute content hash
        content_hash = self.compute_hash(content)

        # Create source info
        source_info = SourceInfo(
            path=str(source_path),
            title=title,
            content_hash=content_hash
        )

        # Check if already exists and unchanged
        if song_id in self.state["songs"]:
            existing = self.state["songs"][song_id]
            if existing["source"]["content_hash"] == content_hash:
                logger.debug(f"Song {song_id} already registered (unchanged)")
                return

        # Register song
        self.state["songs"][song_id] = {
            "source": source_info.to_dict()
        }

        self._save_state()

        logger.info(f"Registered song: {song_id}", title=title)

    def add_lyrics_version(
        self,
        song_id: str,
        lyrics_path: Path,
        prompt: str,
        model: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add a lyrics version.

        Args:
            song_id: Song identifier
            lyrics_path: Path to lyrics file
            prompt: Prompt used for generation
            model: Model name
            metadata: Additional metadata
        """
        if song_id not in self.state["songs"]:
            raise VersionError(f"Song not registered: {song_id}")

        timestamp = self.generate_timestamp()

        # Create version entry
        version = Version(
            timestamp=timestamp,
            path=str(lyrics_path),
            prompt=prompt,
            model=model,
            metadata=metadata or {}
        )

        # Initialize lyrics tracking if needed
        if "lyrics" not in self.state["songs"][song_id]:
            self.state["songs"][song_id]["lyrics"] = {
                "active": str(lyrics_path),
                "versions": []
            }

        # Add version
        self.state["songs"][song_id]["lyrics"]["versions"].append(
            version.to_dict()
        )

        # Update active path
        self.state["songs"][song_id]["lyrics"]["active"] = str(lyrics_path)

        self._save_state()

        logger.info(
            f"Added lyrics version: {song_id}",
            timestamp=timestamp,
            version_count=len(self.state["songs"][song_id]["lyrics"]["versions"])
        )

    def add_audio_version(
        self,
        song_id: str,
        audio_dir: Path,
        clip_ids: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add an audio version.

        Args:
            song_id: Song identifier
            audio_dir: Directory containing audio files
            clip_ids: List of Suno clip IDs
            metadata: Additional metadata
        """
        if song_id not in self.state["songs"]:
            raise VersionError(f"Song not registered: {song_id}")

        timestamp = self.generate_timestamp()

        # Create version entry
        version = {
            "timestamp": timestamp,
            "directory": str(audio_dir),
            "clip_ids": clip_ids,
            "metadata": metadata or {}
        }

        # Initialize audio tracking if needed
        if "audio" not in self.state["songs"][song_id]:
            self.state["songs"][song_id]["audio"] = {
                "active_directory": str(audio_dir),
                "versions": []
            }

        # Add version
        self.state["songs"][song_id]["audio"]["versions"].append(version)

        # Update active directory
        self.state["songs"][song_id]["audio"]["active_directory"] = str(audio_dir)

        self._save_state()

        logger.info(
            f"Added audio version: {song_id}",
            timestamp=timestamp,
            clip_count=len(clip_ids)
        )

    def add_cover_version(
        self,
        song_id: str,
        cover_path: Path,
        prompt: str,
        model: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add a cover art version.

        Args:
            song_id: Song identifier
            cover_path: Path to cover image
            prompt: Prompt used for generation
            model: Model name
            metadata: Additional metadata
        """
        if song_id not in self.state["songs"]:
            raise VersionError(f"Song not registered: {song_id}")

        timestamp = self.generate_timestamp()

        # Create version entry
        version = Version(
            timestamp=timestamp,
            path=str(cover_path),
            prompt=prompt,
            model=model,
            metadata=metadata or {}
        )

        # Initialize cover tracking if needed
        if "cover" not in self.state["songs"][song_id]:
            self.state["songs"][song_id]["cover"] = {
                "active": str(cover_path),
                "versions": []
            }

        # Add version
        self.state["songs"][song_id]["cover"]["versions"].append(
            version.to_dict()
        )

        # Update active path
        self.state["songs"][song_id]["cover"]["active"] = str(cover_path)

        self._save_state()

        logger.info(
            f"Added cover version: {song_id}",
            timestamp=timestamp
        )

    def get_song_state(self, song_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete state for a song.

        Args:
            song_id: Song identifier

        Returns:
            Song state dictionary or None if not found
        """
        return self.state["songs"].get(song_id)

    def get_all_songs(self) -> List[str]:
        """
        Get list of all registered song IDs.

        Returns:
            List of song IDs
        """
        return list(self.state["songs"].keys())

    def song_exists(self, song_id: str) -> bool:
        """
        Check if song is registered.

        Args:
            song_id: Song identifier

        Returns:
            True if song exists
        """
        return song_id in self.state["songs"]

    def get_lyrics_versions(self, song_id: str) -> List[Dict[str, Any]]:
        """
        Get all lyrics versions for a song.

        Args:
            song_id: Song identifier

        Returns:
            List of version dictionaries
        """
        song = self.get_song_state(song_id)
        if not song or "lyrics" not in song:
            return []
        return song["lyrics"].get("versions", [])

    def get_active_lyrics(self, song_id: str) -> Optional[str]:
        """
        Get path to active lyrics file.

        Args:
            song_id: Song identifier

        Returns:
            Path string or None
        """
        song = self.get_song_state(song_id)
        if not song or "lyrics" not in song:
            return None
        return song["lyrics"].get("active")

    def get_audio_versions(self, song_id: str) -> List[Dict[str, Any]]:
        """
        Get all audio versions for a song.

        Args:
            song_id: Song identifier

        Returns:
            List of version dictionaries
        """
        song = self.get_song_state(song_id)
        if not song or "audio" not in song:
            return []
        return song["audio"].get("versions", [])

    def get_active_audio_directory(self, song_id: str) -> Optional[str]:
        """
        Get path to active audio directory.

        Args:
            song_id: Song identifier

        Returns:
            Directory path string or None
        """
        song = self.get_song_state(song_id)
        if not song or "audio" not in song:
            return None
        return song["audio"].get("active_directory")

    def get_cover_versions(self, song_id: str) -> List[Dict[str, Any]]:
        """
        Get all cover art versions for a song.

        Args:
            song_id: Song identifier

        Returns:
            List of version dictionaries
        """
        song = self.get_song_state(song_id)
        if not song or "cover" not in song:
            return []
        return song["cover"].get("versions", [])

    def get_active_cover(self, song_id: str) -> Optional[str]:
        """
        Get path to active cover art file.

        Args:
            song_id: Song identifier

        Returns:
            Path string or None
        """
        song = self.get_song_state(song_id)
        if not song or "cover" not in song:
            return None
        return song["cover"].get("active")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about tracked songs.

        Returns:
            Statistics dictionary
        """
        total_songs = len(self.state["songs"])
        songs_with_lyrics = sum(
            1 for song in self.state["songs"].values()
            if "lyrics" in song
        )
        songs_with_audio = sum(
            1 for song in self.state["songs"].values()
            if "audio" in song
        )
        songs_with_cover = sum(
            1 for song in self.state["songs"].values()
            if "cover" in song
        )

        total_versions = {
            "lyrics": sum(
                len(song.get("lyrics", {}).get("versions", []))
                for song in self.state["songs"].values()
            ),
            "audio": sum(
                len(song.get("audio", {}).get("versions", []))
                for song in self.state["songs"].values()
            ),
            "cover": sum(
                len(song.get("cover", {}).get("versions", []))
                for song in self.state["songs"].values()
            )
        }

        return {
            "total_songs": total_songs,
            "songs_with_lyrics": songs_with_lyrics,
            "songs_with_audio": songs_with_audio,
            "songs_with_cover": songs_with_cover,
            "total_versions": total_versions
        }

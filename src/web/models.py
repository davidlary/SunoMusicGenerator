"""
Pydantic models for FastAPI request/response validation.

Defines data structures for API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class LyricsGenerateRequest(BaseModel):
    """Request model for lyrics generation."""
    song_id: str = Field(..., description="Song identifier (e.g., 1.16.1)")
    narrative_text: str = Field(..., description="Scientific narrative content")
    prompt_template_path: Optional[str] = Field(
        default="prompts/EurekaProtocol.md",
        description="Path to lyrics prompt template"
    )
    force_regenerate: bool = Field(default=False, description="Force regeneration")


class LyricsGenerateResponse(BaseModel):
    """Response model for lyrics generation."""
    path: str = Field(..., description="Path to generated lyrics file")
    lyrics: str = Field(..., description="Generated lyrics text")
    model: str = Field(..., description="Model used for generation")
    regenerated: bool = Field(..., description="Whether new generation occurred")


class AudioGenerateRequest(BaseModel):
    """Request model for audio generation."""
    song_id: str = Field(..., description="Song identifier")
    lyrics: str = Field(..., description="Lyrics text")
    title: str = Field(..., description="Song title")
    tags: Optional[str] = Field(default="educational, rock", description="Genre tags")
    download_formats: List[str] = Field(
        default=["wav", "mp3"],
        description="Audio formats to download"
    )
    force_regenerate: bool = Field(default=False, description="Force regeneration")


class AudioGenerateResponse(BaseModel):
    """Response model for audio generation."""
    directory: str = Field(..., description="Audio directory path")
    clip_ids: List[str] = Field(..., description="Generated clip IDs")
    files: Dict[str, Dict[str, str]] = Field(..., description="Downloaded files")
    regenerated: bool = Field(..., description="Whether new generation occurred")


class CoverGenerateRequest(BaseModel):
    """Request model for cover art generation."""
    song_id: str = Field(..., description="Song identifier")
    lyrics: str = Field(..., description="Lyrics text")
    prompt_template_path: Optional[str] = Field(
        default="prompts/CoverArtPrompt.md",
        description="Path to cover prompt template"
    )
    force_regenerate: bool = Field(default=False, description="Force regeneration")


class CoverGenerateResponse(BaseModel):
    """Response model for cover art generation."""
    path: str = Field(..., description="Path to cover art file")
    size: int = Field(..., description="File size in bytes")
    regenerated: bool = Field(..., description="Whether new generation occurred")


class PipelineGenerateRequest(BaseModel):
    """Request model for full pipeline generation."""
    song_id: str = Field(..., description="Song identifier")
    narrative_text: str = Field(..., description="Scientific narrative")
    title: str = Field(..., description="Song title")
    tags: Optional[str] = Field(default="educational, rock", description="Genre tags")
    lyrics_prompt_path: Optional[str] = Field(
        default="prompts/EurekaProtocol.md",
        description="Lyrics prompt path"
    )
    cover_prompt_path: Optional[str] = Field(
        default="prompts/CoverArtPrompt.md",
        description="Cover prompt path"
    )
    force_regenerate: bool = Field(default=False, description="Force regeneration")


class PipelineGenerateResponse(BaseModel):
    """Response model for full pipeline generation."""
    lyrics: LyricsGenerateResponse
    audio: AudioGenerateResponse
    cover: CoverGenerateResponse


class SongStatus(BaseModel):
    """Status model for a single song."""
    song_id: str
    title: str
    source_path: str
    created_at: str
    has_lyrics: bool
    has_audio: bool
    has_cover: bool
    lyrics_version: Optional[str] = None
    audio_version: Optional[str] = None
    cover_version: Optional[str] = None


class StatusResponse(BaseModel):
    """Response model for status endpoint."""
    songs: List[SongStatus]
    total_count: int


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Health status")
    version: str = Field(..., description="API version")

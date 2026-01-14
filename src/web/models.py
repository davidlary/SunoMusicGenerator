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


class SourceFile(BaseModel):
    """Model for a source text file."""
    song_id: str = Field(..., description="Song identifier")
    file_path: str = Field(..., description="Absolute path to source file")
    title: Optional[str] = Field(None, description="Song title if registered")
    has_lyrics: bool = Field(default=False, description="Has generated lyrics")
    has_audio: bool = Field(default=False, description="Has generated audio")
    has_cover: bool = Field(default=False, description="Has generated cover")
    text_preview: Optional[str] = Field(None, description="First 200 chars of text")


class SourceListResponse(BaseModel):
    """Response model for source file discovery."""
    sources: List[SourceFile]
    total_count: int


class PromptReadRequest(BaseModel):
    """Request model for reading a prompt."""
    prompt_name: str = Field(..., description="Prompt name (EurekaProtocol or CoverArtPrompt)")


class PromptReadResponse(BaseModel):
    """Response model for reading a prompt."""
    prompt_name: str
    content: str
    file_path: str


class PromptUpdateRequest(BaseModel):
    """Request model for updating a prompt."""
    prompt_name: str = Field(..., description="Prompt name")
    content: str = Field(..., description="New prompt content")


class PromptUpdateResponse(BaseModel):
    """Response model for prompt update."""
    prompt_name: str
    old_version: str = Field(..., description="Previous version file path")
    new_version: str = Field(..., description="New version file path")
    timestamp: str = Field(..., description="Update timestamp")


class CoverVersion(BaseModel):
    """Model for a cover art version."""
    version_id: str = Field(..., description="Version identifier (timestamp or base)")
    file_path: str = Field(..., description="Path to cover file")
    is_active: bool = Field(..., description="Is this the active cover")
    created_at: str = Field(..., description="Creation timestamp")
    size: int = Field(..., description="File size in bytes")


class CoverVersionsResponse(BaseModel):
    """Response model for cover versions list."""
    song_id: str
    versions: List[CoverVersion]
    total_count: int


class CoverPromoteRequest(BaseModel):
    """Request model for promoting a cover version."""
    song_id: str = Field(..., description="Song identifier")
    version_id: str = Field(..., description="Version to promote")


class CoverPromoteResponse(BaseModel):
    """Response model for cover promotion."""
    song_id: str
    promoted_version: str
    new_active_path: str
    backup_path: Optional[str] = Field(None, description="Backed up previous active")

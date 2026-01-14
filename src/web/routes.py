"""
FastAPI routes for SunoMusicGenerator API.

Provides REST endpoints for lyrics, audio, and cover art generation.
"""

from fastapi import APIRouter, HTTPException, status
from pathlib import Path
from typing import List
import shutil
from datetime import datetime

from ..core import get_logger, get_settings, LyricsGenerationError, SongGenerationError, CoverGenerationError
from ..pipeline import LyricsGenerator, SongGenerator, CoverGenerator
from ..state import StateTracker
from .models import (
    LyricsGenerateRequest,
    LyricsGenerateResponse,
    AudioGenerateRequest,
    AudioGenerateResponse,
    CoverGenerateRequest,
    CoverGenerateResponse,
    PipelineGenerateRequest,
    PipelineGenerateResponse,
    SongStatus,
    StatusResponse,
    ErrorResponse,
    SourceFile,
    SourceListResponse,
    PromptReadRequest,
    PromptReadResponse,
    PromptUpdateRequest,
    PromptUpdateResponse,
    CoverVersion,
    CoverVersionsResponse,
    CoverPromoteRequest,
    CoverPromoteResponse
)

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/lyrics/generate",
    response_model=LyricsGenerateResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Generate lyrics from narrative",
    description="Generate song lyrics from scientific narrative text using Gemini API"
)
async def generate_lyrics(request: LyricsGenerateRequest) -> LyricsGenerateResponse:
    """Generate lyrics from scientific narrative."""
    try:
        logger.info(f"Generating lyrics for {request.song_id}")

        generator = LyricsGenerator()
        result = generator.generate(
            song_id=request.song_id,
            narrative_text=request.narrative_text,
            prompt_template_path=Path(request.prompt_template_path),
            force_regenerate=request.force_regenerate
        )

        return LyricsGenerateResponse(**result)

    except LyricsGenerationError as e:
        logger.error(f"Lyrics generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/audio/generate",
    response_model=AudioGenerateResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Generate audio from lyrics",
    description="Generate audio from lyrics using Suno API"
)
async def generate_audio(request: AudioGenerateRequest) -> AudioGenerateResponse:
    """Generate audio from lyrics."""
    try:
        logger.info(f"Generating audio for {request.song_id}")

        generator = SongGenerator()
        result = generator.generate(
            song_id=request.song_id,
            lyrics=request.lyrics,
            title=request.title,
            tags=request.tags,
            download_formats=request.download_formats,
            force_regenerate=request.force_regenerate
        )

        return AudioGenerateResponse(**result)

    except SongGenerationError as e:
        logger.error(f"Audio generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/cover/generate",
    response_model=CoverGenerateResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Generate cover art from lyrics",
    description="Generate 4K cover art from lyrics using Gemini API"
)
async def generate_cover(request: CoverGenerateRequest) -> CoverGenerateResponse:
    """Generate cover art from lyrics."""
    try:
        logger.info(f"Generating cover art for {request.song_id}")

        generator = CoverGenerator()
        result = generator.generate(
            song_id=request.song_id,
            lyrics=request.lyrics,
            prompt_template_path=Path(request.prompt_template_path),
            force_regenerate=request.force_regenerate
        )

        return CoverGenerateResponse(**result)

    except CoverGenerationError as e:
        logger.error(f"Cover generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/pipeline/generate",
    response_model=PipelineGenerateResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Run full generation pipeline",
    description="Generate lyrics, audio, and cover art in one request"
)
async def generate_pipeline(request: PipelineGenerateRequest) -> PipelineGenerateResponse:
    """Run full generation pipeline: lyrics -> audio -> cover."""
    try:
        logger.info(f"Running full pipeline for {request.song_id}")

        # Generate lyrics
        lyrics_gen = LyricsGenerator()
        lyrics_result = lyrics_gen.generate(
            song_id=request.song_id,
            narrative_text=request.narrative_text,
            prompt_template_path=Path(request.lyrics_prompt_path),
            force_regenerate=request.force_regenerate
        )

        # Generate audio
        audio_gen = SongGenerator()
        audio_result = audio_gen.generate(
            song_id=request.song_id,
            lyrics=lyrics_result["lyrics"],
            title=request.title,
            tags=request.tags,
            download_formats=["wav", "mp3"],
            force_regenerate=request.force_regenerate
        )

        # Generate cover
        cover_gen = CoverGenerator()
        cover_result = cover_gen.generate(
            song_id=request.song_id,
            lyrics=lyrics_result["lyrics"],
            prompt_template_path=Path(request.cover_prompt_path),
            force_regenerate=request.force_regenerate
        )

        return PipelineGenerateResponse(
            lyrics=LyricsGenerateResponse(**lyrics_result),
            audio=AudioGenerateResponse(**audio_result),
            cover=CoverGenerateResponse(**cover_result)
        )

    except (LyricsGenerationError, SongGenerationError, CoverGenerationError) as e:
        logger.error(f"Pipeline failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/status",
    response_model=StatusResponse,
    summary="Get generation status for all songs",
    description="Retrieve status of all generated songs"
)
async def get_status() -> StatusResponse:
    """Get status for all songs."""
    try:
        tracker = StateTracker()
        state = tracker.state

        songs: List[SongStatus] = []
        for song_id, song_data in state["songs"].items():
            songs.append(SongStatus(
                song_id=song_id,
                title=song_data["title"],
                source_path=song_data["source_path"],
                created_at=song_data["created_at"],
                has_lyrics=bool(song_data.get("lyrics")),
                has_audio=bool(song_data.get("audio")),
                has_cover=bool(song_data.get("cover")),
                lyrics_version=song_data.get("lyrics", {}).get("active_version"),
                audio_version=song_data.get("audio", {}).get("active_version"),
                cover_version=song_data.get("cover", {}).get("active_version")
            ))

        return StatusResponse(
            songs=songs,
            total_count=len(songs)
        )

    except Exception as e:
        logger.error(f"Status retrieval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve status: {str(e)}"
        )


@router.get(
    "/status/{song_id}",
    response_model=SongStatus,
    responses={404: {"model": ErrorResponse}},
    summary="Get status for specific song",
    description="Retrieve detailed status for a specific song"
)
async def get_song_status(song_id: str) -> SongStatus:
    """Get status for specific song."""
    try:
        tracker = StateTracker()
        state = tracker.state

        if song_id not in state["songs"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Song {song_id} not found"
            )

        song_data = state["songs"][song_id]

        return SongStatus(
            song_id=song_id,
            title=song_data["title"],
            source_path=song_data["source_path"],
            created_at=song_data["created_at"],
            has_lyrics=bool(song_data.get("lyrics")),
            has_audio=bool(song_data.get("audio")),
            has_cover=bool(song_data.get("cover")),
            lyrics_version=song_data.get("lyrics", {}).get("active_version"),
            audio_version=song_data.get("audio", {}).get("active_version"),
            cover_version=song_data.get("cover", {}).get("active_version")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status retrieval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve status: {str(e)}"
        )


@router.get(
    "/sources/list",
    response_model=SourceListResponse,
    summary="List all source text files",
    description="Auto-discover all source text files in Songs/*/Text/*.txt"
)
async def list_sources() -> SourceListResponse:
    """Discover and list all source text files."""
    try:
        settings = get_settings()
        base_dir = Path(settings.paths.base_dir)
        songs_dir = base_dir / settings.paths.songs_dir

        # Find all source files
        source_files = sorted(songs_dir.glob("*/Text/*.txt"))

        # Load state to check generation status
        tracker = StateTracker()
        state = tracker.state

        sources: List[SourceFile] = []
        for source_file in source_files:
            # Extract song_id from path (Songs/1.16.1/Text/1.16.1.txt)
            song_id = source_file.parent.parent.name

            # Read text preview
            try:
                text_content = source_file.read_text(encoding='utf-8')
                text_preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
            except Exception:
                text_preview = None

            # Check generation status
            song_data = state["songs"].get(song_id, {})

            sources.append(SourceFile(
                song_id=song_id,
                file_path=str(source_file.absolute()),
                title=song_data.get("title"),
                has_lyrics=bool(song_data.get("lyrics")),
                has_audio=bool(song_data.get("audio")),
                has_cover=bool(song_data.get("cover")),
                text_preview=text_preview
            ))

        return SourceListResponse(
            sources=sources,
            total_count=len(sources)
        )

    except Exception as e:
        logger.error(f"Source discovery failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to discover sources: {str(e)}"
        )


@router.get(
    "/prompts/read",
    response_model=PromptReadResponse,
    summary="Read a prompt template",
    description="Read EurekaProtocol or CoverArtPrompt"
)
async def read_prompt(prompt_name: str) -> PromptReadResponse:
    """Read a prompt template."""
    try:
        settings = get_settings()
        base_dir = Path(settings.paths.base_dir)
        prompts_dir = base_dir / settings.paths.prompts_dir

        # Map prompt names to files
        prompt_files = {
            "EurekaProtocol": "EurekaProtocol.md",
            "CoverArtPrompt": "CoverArtPrompt.md"
        }

        if prompt_name not in prompt_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown prompt: {prompt_name}"
            )

        prompt_file = prompts_dir / prompt_files[prompt_name]

        if not prompt_file.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt file not found: {prompt_file}"
            )

        content = prompt_file.read_text(encoding='utf-8')

        return PromptReadResponse(
            prompt_name=prompt_name,
            content=content,
            file_path=str(prompt_file.absolute())
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prompt read failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read prompt: {str(e)}"
        )


@router.post(
    "/prompts/update",
    response_model=PromptUpdateResponse,
    summary="Update a prompt template",
    description="Update prompt with automatic versioning (backup with timestamp)"
)
async def update_prompt(request: PromptUpdateRequest) -> PromptUpdateResponse:
    """Update a prompt template with versioning."""
    try:
        settings = get_settings()
        base_dir = Path(settings.paths.base_dir)
        prompts_dir = base_dir / settings.paths.prompts_dir

        # Map prompt names to files
        prompt_files = {
            "EurekaProtocol": "EurekaProtocol.md",
            "CoverArtPrompt": "CoverArtPrompt.md"
        }

        if request.prompt_name not in prompt_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown prompt: {request.prompt_name}"
            )

        prompt_file = prompts_dir / prompt_files[request.prompt_name]

        # Create backup with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_name = prompt_file.stem + f"-{timestamp}" + prompt_file.suffix
        backup_file = prompts_dir / backup_name

        # Backup existing if it exists
        if prompt_file.exists():
            shutil.copy2(prompt_file, backup_file)

        # Write new content
        prompt_file.write_text(request.content, encoding='utf-8')

        logger.info(f"Updated prompt {request.prompt_name}, backup at {backup_file}")

        return PromptUpdateResponse(
            prompt_name=request.prompt_name,
            old_version=str(backup_file.absolute()) if backup_file.exists() else "none",
            new_version=str(prompt_file.absolute()),
            timestamp=timestamp
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prompt update failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update prompt: {str(e)}"
        )


@router.get(
    "/cover/versions/{song_id}",
    response_model=CoverVersionsResponse,
    summary="List all cover art versions",
    description="Get all cover art versions for a song"
)
async def list_cover_versions(song_id: str) -> CoverVersionsResponse:
    """List all cover art versions for a song."""
    try:
        settings = get_settings()
        base_dir = Path(settings.paths.base_dir)
        songs_dir = base_dir / settings.paths.songs_dir

        cover_dir = songs_dir / song_id / "Cover"

        if not cover_dir.exists():
            return CoverVersionsResponse(
                song_id=song_id,
                versions=[],
                total_count=0
            )

        # Find all cover files
        cover_files = list(cover_dir.glob("*.jpeg")) + list(cover_dir.glob("*.jpg"))

        # Load state to get creation times
        tracker = StateTracker()
        state = tracker.state
        song_data = state["songs"].get(song_id, {})
        cover_data = song_data.get("cover", {})
        versions_data = cover_data.get("versions", [])

        # Build version list
        versions: List[CoverVersion] = []
        active_cover_path = cover_dir / "CoverArt.jpeg"

        for cover_file in sorted(cover_files):
            # Determine version_id
            if cover_file.name == "CoverArt.jpeg":
                version_id = "active"
                # Find which timestamp this is from
                created_at = "unknown"
                for v in versions_data:
                    if Path(v["path"]).name == cover_file.name:
                        created_at = v["created_at"]
                        break
            else:
                # Extract timestamp from filename (1.16.1-20260114-123456.jpeg)
                version_id = cover_file.stem.split('-', 1)[-1] if '-' in cover_file.stem else cover_file.stem
                # Find creation time
                created_at = "unknown"
                for v in versions_data:
                    if Path(v["path"]).name == cover_file.name:
                        created_at = v["created_at"]
                        break

            versions.append(CoverVersion(
                version_id=version_id,
                file_path=str(cover_file.absolute()),
                is_active=(cover_file == active_cover_path),
                created_at=created_at,
                size=cover_file.stat().st_size
            ))

        return CoverVersionsResponse(
            song_id=song_id,
            versions=versions,
            total_count=len(versions)
        )

    except Exception as e:
        logger.error(f"Cover versions list failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list cover versions: {str(e)}"
        )


@router.post(
    "/cover/promote",
    response_model=CoverPromoteResponse,
    summary="Promote a cover version to active",
    description="Set a specific cover version as the active CoverArt.jpeg"
)
async def promote_cover(request: CoverPromoteRequest) -> CoverPromoteResponse:
    """Promote a cover version to active."""
    try:
        settings = get_settings()
        base_dir = Path(settings.paths.base_dir)
        songs_dir = base_dir / settings.paths.songs_dir

        cover_dir = songs_dir / request.song_id / "Cover"

        if not cover_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cover directory not found for {request.song_id}"
            )

        # Find the version to promote
        version_file = None
        for ext in [".jpeg", ".jpg"]:
            candidate = cover_dir / f"{request.song_id}-{request.version_id}{ext}"
            if candidate.exists():
                version_file = candidate
                break

        if not version_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {request.version_id} not found"
            )

        active_cover = cover_dir / "CoverArt.jpeg"
        backup_path = None

        # Backup current active if it exists
        if active_cover.exists():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = cover_dir / f"CoverArt-backup-{timestamp}.jpeg"
            shutil.copy2(active_cover, backup_path)

        # Promote the version
        shutil.copy2(version_file, active_cover)

        logger.info(f"Promoted cover version {request.version_id} for {request.song_id}")

        return CoverPromoteResponse(
            song_id=request.song_id,
            promoted_version=request.version_id,
            new_active_path=str(active_cover.absolute()),
            backup_path=str(backup_path.absolute()) if backup_path else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cover promotion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to promote cover: {str(e)}"
        )

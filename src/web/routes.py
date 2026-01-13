"""
FastAPI routes for SunoMusicGenerator API.

Provides REST endpoints for lyrics, audio, and cover art generation.
"""

from fastapi import APIRouter, HTTPException, status
from pathlib import Path
from typing import List

from ..core import get_logger, LyricsGenerationError, SongGenerationError, CoverGenerationError
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
    ErrorResponse
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

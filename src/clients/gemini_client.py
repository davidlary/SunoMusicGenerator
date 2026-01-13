"""
Gemini API client for lyrics and cover art generation.

This module provides a client for interacting with Google's Gemini API
using the google.genai package (NOT the deprecated google.generativeai).
"""

import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types
import base64

from ..core import (
    get_logger,
    get_settings,
    get_rate_limiter,
    GeminiAPIError,
    NetworkError,
    MaxRetriesExceededError,
)

logger = get_logger(__name__)


class GeminiClient:
    """
    Client for Google Gemini API interactions.

    Supports:
    - Lyrics generation using thinking models
    - 4K cover art generation
    - Automatic rate limiting
    - Exponential backoff retry logic
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini client.

        Args:
            api_key: Optional API key (uses settings if not provided)
        """
        self.settings = get_settings()
        self.api_key = api_key or self.settings.gemini.api_key
        self.rate_limiter = get_rate_limiter()

        # Initialize the Gemini client
        self.client = genai.Client(api_key=self.api_key)

        logger.info(
            "Gemini client initialized",
            lyrics_model=self.settings.gemini.lyrics_model,
            cover_model=self.settings.gemini.cover_model
        )

    def _retry_with_backoff(
        self,
        operation: callable,
        operation_name: str,
        **kwargs
    ) -> Any:
        """
        Execute operation with exponential backoff retry logic.

        Args:
            operation: Function to execute
            operation_name: Name for logging
            **kwargs: Arguments to pass to operation

        Returns:
            Operation result

        Raises:
            MaxRetriesExceededError: If all retries fail
        """
        max_retries = self.settings.gemini.max_retries
        retry_delays = self.settings.gemini.retry_delays

        last_error = None
        for attempt in range(max_retries):
            try:
                logger.debug(
                    f"{operation_name} attempt {attempt + 1}/{max_retries}"
                )
                result = operation(**kwargs)
                if attempt > 0:
                    logger.info(
                        f"{operation_name} succeeded after {attempt + 1} attempts"
                    )
                return result

            except Exception as e:
                last_error = e
                is_last_attempt = attempt == max_retries - 1

                if is_last_attempt:
                    logger.error(
                        f"{operation_name} failed after {max_retries} attempts",
                        exc_info=True,
                        error=str(e)
                    )
                    break

                # Calculate delay (use configured delays or default)
                delay = retry_delays[attempt] if attempt < len(retry_delays) else retry_delays[-1]

                logger.warning(
                    f"{operation_name} failed, retrying in {delay}s",
                    attempt=attempt + 1,
                    error=str(e)
                )
                time.sleep(delay)

        raise MaxRetriesExceededError(
            f"{operation_name} failed after {max_retries} attempts",
            attempts=max_retries,
            original_error=last_error
        )

    def generate_lyrics(
        self,
        narrative_text: str,
        prompt_template: str,
        song_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate song lyrics from scientific narrative text.

        Uses Gemini thinking model with the Eureka Protocol to create
        scientifically accurate, memorable song lyrics.

        Args:
            narrative_text: Source scientific text
            prompt_template: Prompt template (Eureka Protocol)
            song_id: Optional song identifier for logging

        Returns:
            Dictionary containing:
                - lyrics: Generated lyrics text
                - reasoning: Model's reasoning process
                - model: Model name used
                - metadata: Additional metadata

        Raises:
            GeminiAPIError: If generation fails
        """
        # Apply rate limiting
        self.rate_limiter.acquire("gemini", blocking=True)

        context = {
            "text_length": len(narrative_text)
        }

        logger.log_generation(
            song_id=song_id or "unknown",
            stage="lyrics",
            status="started",
            **context
        )

        start_time = time.time()

        try:
            result = self._retry_with_backoff(
                operation=self._generate_lyrics_impl,
                operation_name=f"Lyrics generation ({song_id})",
                narrative_text=narrative_text,
                prompt_template=prompt_template
            )

            duration = time.time() - start_time

            logger.log_generation(
                song_id=song_id or "unknown",
                stage="lyrics",
                status="completed",
                duration=duration,
                lyrics_length=len(result["lyrics"])
            )

            return result

        except Exception as e:
            duration = time.time() - start_time
            logger.log_generation(
                song_id=song_id or "unknown",
                stage="lyrics",
                status="failed",
                duration=duration,
                error=str(e)
            )
            raise GeminiAPIError(
                f"Lyrics generation failed: {str(e)}",
                details=context
            ) from e

    def _generate_lyrics_impl(
        self,
        narrative_text: str,
        prompt_template: str
    ) -> Dict[str, Any]:
        """
        Internal implementation of lyrics generation.

        Args:
            narrative_text: Source text
            prompt_template: Prompt template

        Returns:
            Generation result dictionary
        """
        # Construct full prompt
        full_prompt = f"{prompt_template}\n\n**Narrative Text to Process:**\n{narrative_text}"

        # Generate with thinking model
        response = self.client.models.generate_content(
            model=self.settings.gemini.lyrics_model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                top_p=0.95,
                max_output_tokens=8192,
            )
        )

        # Extract text from response
        lyrics_text = response.text if hasattr(response, 'text') else str(response)

        # Try to extract thinking/reasoning if available
        reasoning = None
        if hasattr(response, 'candidates') and len(response.candidates) > 0:
            candidate = response.candidates[0]
            # Check for thinking metadata
            if hasattr(candidate, 'grounding_metadata'):
                reasoning = str(candidate.grounding_metadata)

        return {
            "lyrics": lyrics_text.strip(),
            "reasoning": reasoning,
            "model": self.settings.gemini.lyrics_model,
            "metadata": {
                "prompt_length": len(full_prompt),
                "response_length": len(lyrics_text),
            }
        }

    def generate_cover_art(
        self,
        lyrics_text: str,
        prompt_template: str,
        song_id: Optional[str] = None,
    ) -> bytes:
        """
        Generate 4K cover art from lyrics.

        Uses Gemini image generation model with Renaissance Photorealistic
        Schematic style prompt.

        Args:
            lyrics_text: Song lyrics
            prompt_template: Image generation prompt template
            song_id: Optional song identifier for logging

        Returns:
            JPEG image bytes (4K resolution)

        Raises:
            GeminiAPIError: If generation fails
        """
        # Apply rate limiting
        self.rate_limiter.acquire("gemini", blocking=True)

        context = {
            "lyrics_length": len(lyrics_text)
        }

        logger.log_generation(
            song_id=song_id or "unknown",
            stage="cover",
            status="started",
            **context
        )

        start_time = time.time()

        try:
            result = self._retry_with_backoff(
                operation=self._generate_cover_impl,
                operation_name=f"Cover generation ({song_id})",
                lyrics_text=lyrics_text,
                prompt_template=prompt_template
            )

            duration = time.time() - start_time

            logger.log_generation(
                song_id=song_id or "unknown",
                stage="cover",
                status="completed",
                duration=duration,
                image_size=len(result)
            )

            return result

        except Exception as e:
            duration = time.time() - start_time
            logger.log_generation(
                song_id=song_id or "unknown",
                stage="cover",
                status="failed",
                duration=duration,
                error=str(e)
            )
            raise GeminiAPIError(
                f"Cover art generation failed: {str(e)}",
                details=context
            ) from e

    def _generate_cover_impl(
        self,
        lyrics_text: str,
        prompt_template: str
    ) -> bytes:
        """
        Internal implementation of cover art generation.

        Args:
            lyrics_text: Lyrics text
            prompt_template: Image prompt template

        Returns:
            JPEG image bytes
        """
        # Construct full prompt with lyrics
        full_prompt = f"{prompt_template}\n\n**Lyrics:**\n{lyrics_text}"

        # Generate image
        response = self.client.models.generate_images(
            model=self.settings.gemini.cover_model,
            prompt=full_prompt,
            config=types.GenerateImageConfig(
                number_of_images=1,
                aspect_ratio="1:1",  # Square format for album art
                safety_filter_level="BLOCK_ONLY_HIGH",
            )
        )

        # Extract image from response
        if not response.generated_images or len(response.generated_images) == 0:
            raise GeminiAPIError("No images generated")

        image = response.generated_images[0]

        # Get image bytes
        if hasattr(image, 'image'):
            # Image is already in bytes format
            image_bytes = image.image.data
        elif hasattr(image, 'data'):
            image_bytes = image.data
        else:
            raise GeminiAPIError("Could not extract image data from response")

        return image_bytes

    def check_model_availability(self, model_name: str) -> bool:
        """
        Check if a model is available.

        Args:
            model_name: Model identifier

        Returns:
            True if model is available
        """
        try:
            # Try to get model info
            models = self.client.models.list()
            available_models = [m.name for m in models]

            # Check if model exists
            is_available = any(model_name in m for m in available_models)

            logger.debug(
                f"Model availability check: {model_name}",
                available=is_available
            )

            return is_available

        except Exception as e:
            logger.warning(
                f"Could not check model availability: {model_name}",
                error=str(e)
            )
            # Assume available if check fails
            return True

    def get_available_models(self) -> List[str]:
        """
        Get list of available models.

        Returns:
            List of model names
        """
        try:
            models = self.client.models.list()
            model_names = [m.name for m in models]

            logger.info(
                "Retrieved available models",
                count=len(model_names)
            )

            return model_names

        except Exception as e:
            logger.error(
                "Failed to retrieve available models",
                error=str(e)
            )
            return []

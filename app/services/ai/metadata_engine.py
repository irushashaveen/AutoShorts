import logging
from typing import Tuple, Optional
from app.schemas.metadata import AIMetadataOutput
from app.services.ai.gemini_client import GeminiClient, GeminiInferenceError
from app.services.ai.ollama_client import OllamaClient, OllamaInferenceError

logger = logging.getLogger(__name__)


class MetadataGenerationFailedError(Exception):
    """Raised when both Google Gemini and Ollama fallback fail to generate metadata."""
    pass


class MetadataEngine:
    """Orchestrates AI metadata generation with cloud-to-local fallback."""

    def __init__(
        self,
        gemini_client: Optional[GeminiClient] = None,
        ollama_client: Optional[OllamaClient] = None
    ):
        self.gemini = gemini_client or GeminiClient()
        self.ollama = ollama_client or OllamaClient()

    def generate(
        self,
        caption: str,
        creator_username: str,
        creator_nickname: str = "",
        duration: float = 0.0
    ) -> Tuple[AIMetadataOutput, str]:
        """
        Attempts generation via Google Gemini 1.5 Flash (Primary).
        On 429 rate limit or timeout (>8s), transitions to local Ollama (Fallback).
        Returns: (AIMetadataOutput, engine_used)
        """
        gemini_err: Optional[Exception] = None

        # 1. Primary: Google Gemini 1.5 Flash
        try:
            logger.info("Generating metadata via primary Google Gemini 1.5 Flash")
            result = self.gemini.generate_metadata(
                caption=caption,
                creator_username=creator_username,
                creator_nickname=creator_nickname,
                duration=duration
            )
            return result, "gemini-1.5-flash"
        except Exception as e:
            gemini_err = e
            logger.warning(f"Primary Gemini API failed ({e}). Activating Ollama fallback.")

        # 2. Fallback: Local Ollama Qwen 2.5 3B
        try:
            logger.info("Generating metadata via fallback local Ollama (qwen2.5:3b)")
            result = self.ollama.generate_metadata(
                caption=caption,
                creator_username=creator_username,
                creator_nickname=creator_nickname,
                duration=duration
            )
            return result, "ollama-qwen2.5:3b"
        except Exception as ollama_err:
            logger.error(f"Both AI engines failed. Gemini: {gemini_err} | Ollama: {ollama_err}")
            raise MetadataGenerationFailedError(
                f"Metadata generation failed across all engines. Primary: {gemini_err} | Fallback: {ollama_err}"
            ) from ollama_err


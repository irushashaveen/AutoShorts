import json
import logging
from typing import Optional, Dict, Any
from app.config import settings
from app.schemas.metadata import AIMetadataOutput
from app.services.ai.prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class GeminiInferenceError(Exception):
    """Raised when Google Gemini API encounters 429 quota exhaustion or timeout."""
    pass


class GeminiClient:
    """Primary metadata optimization client using Google Gemini 1.5 Flash Free Tier."""

    def __init__(
        self,
        api_key: str = settings.GEMINI_API_KEY,
        model_name: str = settings.GEMINI_MODEL,
        timeout: float = settings.GEMINI_TIMEOUT_SECONDS
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout

    def generate_metadata(
        self,
        caption: str,
        creator_username: str,
        creator_nickname: str = "",
        duration: float = 0.0
    ) -> AIMetadataOutput:
        """Call Gemini 1.5 Flash with JSON schema enforcement."""
        if not self.api_key:
            raise GeminiInferenceError("GEMINI_API_KEY is not configured in settings.")

        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)

            generation_config = genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.7,
                top_p=0.9,
            )

            model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=generation_config,
                system_instruction=SYSTEM_PROMPT
            )

            user_prompt = build_user_prompt(caption, creator_username, creator_nickname, duration)
            
            # Execute generation request
            response = model.generate_content(
                user_prompt,
                request_options={"timeout": self.timeout}
            )

            raw_text = response.text
            if not raw_text:
                raise GeminiInferenceError("Empty text completion returned from Gemini API")

            parsed_json = json.loads(raw_text)

            # Ensure creator attribution is formatted in description
            desc = parsed_json.get("description", "")
            attribution = f"Original Creator: @{creator_username}"
            if attribution not in desc:
                desc = f"{desc}\n\nCredit: @{creator_username}"
                parsed_json["description"] = desc

            return AIMetadataOutput(**parsed_json)
        except Exception as e:
            logger.warning(f"Gemini API inference failed ({e}). Flagging for fallback.")
            raise GeminiInferenceError(f"Gemini inference failed: {e}") from e

import json
import logging
from typing import Optional, Dict, Any
import httpx
from app.config import settings
from app.schemas.metadata import AIMetadataOutput
from app.services.ai.prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class OllamaInferenceError(Exception):
    """Raised when Ollama local inference fails or times out."""
    pass


class OllamaClient:
    """Fallback client interacting with local Ollama running Qwen 2.5 3B."""

    def __init__(
        self,
        base_url: str = settings.OLLAMA_BASE_URL,
        model: str = settings.OLLAMA_MODEL,
        client: Optional[httpx.Client] = None,
        timeout: float = 30.0
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = client
        self.timeout = timeout

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=self.timeout)

    def generate_metadata(
        self,
        caption: str,
        creator_username: str,
        creator_nickname: str = "",
        duration: float = 0.0
    ) -> AIMetadataOutput:
        """Call Ollama /api/generate with JSON format constraint."""
        client = self._get_client()
        should_close = self._client is None

        user_prompt = build_user_prompt(caption, creator_username, creator_nickname, duration)
        full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
            }
        }

        try:
            url = f"{self.base_url}/api/generate"
            response = client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            raw_response_text = data.get("response", "")
            if not raw_response_text:
                raise OllamaInferenceError("Empty response returned from Ollama")

            # Parse inner JSON
            parsed_json = json.loads(raw_response_text)

            # Ensure attribution is present in description
            desc = parsed_json.get("description", "")
            attribution = f"Original Creator: @{creator_username}"
            if attribution not in desc:
                desc = f"{desc}\n\nCredit: @{creator_username}"
                parsed_json["description"] = desc

            return AIMetadataOutput(**parsed_json)
        except Exception as e:
            logger.warning(f"Ollama inference error: {e}")
            raise OllamaInferenceError(f"Ollama inference failed: {e}") from e
        finally:
            if should_close:
                client.close()


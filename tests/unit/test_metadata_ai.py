import pytest
from unittest.mock import MagicMock, patch
import json
import httpx
import respx
from app.schemas.metadata import AIMetadataOutput
from app.services.ai import (
    GeminiClient,
    GeminiInferenceError,
    OllamaClient,
    OllamaInferenceError,
    MetadataEngine,
    MetadataGenerationFailedError,
)


def test_ai_metadata_schema_cleaning():
    # Long title with hashtags should be cleaned and truncated under 60 chars
    raw_data = {
        "title": "Unbelievable Hidden Secret Inside This Old Watch! #viral #fyp #tech",
        "description": "Watchmaker discovers a secret message hidden inside a 100-year-old watch.",
        "tags": ["#WATCHES", "Horology ", "secret", "extra_tag_4"]
    }

    output = AIMetadataOutput(**raw_data)
    assert "#" not in output.title
    assert len(output.title) <= 60
    assert len(output.tags) == 3
    assert output.tags == ["watches", "horology", "secret"]


def test_gemini_client_success():
    mock_genai = MagicMock()
    mock_model = MagicMock()
    mock_response = MagicMock()

    payload_json = {
        "title": "Secret Feature in Your Phone",
        "description": "Here are two sentences explaining how this secret feature works on all modern smartphones.",
        "tags": ["smartphone", "tech", "tips"]
    }
    mock_response.text = json.dumps(payload_json)
    mock_model.generate_content.return_value = mock_response

    with patch.dict("sys.modules", {"google.generativeai": mock_genai}):
        mock_genai.GenerativeModel.return_value = mock_model
        client = GeminiClient(api_key="valid_dummy_key")
        result = client.generate_metadata(
            caption="Secret phone feature you didn't know #tech",
            creator_username="tech_guru",
            creator_nickname="Tech Guru",
            duration=35.0
        )

        assert result.title == "Secret Feature in Your Phone"
        assert "@tech_guru" in result.description
        assert len(result.tags) == 3


def test_gemini_client_missing_key():
    client = GeminiClient(api_key="")
    with pytest.raises(GeminiInferenceError):
        client.generate_metadata(caption="test", creator_username="user")


@respx.mock
def test_ollama_client_success():
    client = httpx.Client()
    ollama = OllamaClient(base_url="http://localhost:11434", client=client)

    inner_json = {
        "title": "Mind-Blowing Science Fact",
        "description": "A single lightning bolt contains enough energy to toast 100,000 slices of bread.",
        "tags": ["science", "facts", "nature"]
    }

    respx.post("http://localhost:11434/api/generate").respond(
        status_code=200,
        json={"response": json.dumps(inner_json)}
    )

    result = ollama.generate_metadata(
        caption="Did you know this about lightning? #science",
        creator_username="science_daily"
    )

    assert result.title == "Mind-Blowing Science Fact"
    assert "@science_daily" in result.description
    assert result.tags == ["science", "facts", "nature"]


def test_metadata_engine_primary_gemini():
    mock_gemini = MagicMock()
    mock_ollama = MagicMock()

    expected_output = AIMetadataOutput(
        title="Epic Coding Trick",
        description="Write clean code in seconds.\n\nCredit: @coder",
        tags=["code", "python", "dev"]
    )
    mock_gemini.generate_metadata.return_value = expected_output

    engine = MetadataEngine(gemini_client=mock_gemini, ollama_client=mock_ollama)
    result, engine_used = engine.generate(
        caption="Cool trick",
        creator_username="coder"
    )

    assert engine_used == "gemini-1.5-flash"
    assert result.title == "Epic Coding Trick"
    mock_gemini.generate_metadata.assert_called_once()
    mock_ollama.generate_metadata.assert_not_called()


def test_metadata_engine_fallback_to_ollama():
    mock_gemini = MagicMock()
    mock_ollama = MagicMock()

    # Gemini raises 429 / timeout
    mock_gemini.generate_metadata.side_effect = GeminiInferenceError("429 ResourceExhausted")

    fallback_output = AIMetadataOutput(
        title="Offline Generated Title",
        description="Generated locally via Qwen.\n\nCredit: @coder",
        tags=["offline", "slm", "qwen"]
    )
    mock_ollama.generate_metadata.return_value = fallback_output

    engine = MetadataEngine(gemini_client=mock_gemini, ollama_client=mock_ollama)
    result, engine_used = engine.generate(
        caption="Cool trick",
        creator_username="coder"
    )

    assert engine_used == "ollama-qwen2.5:3b"
    assert result.title == "Offline Generated Title"
    mock_gemini.generate_metadata.assert_called_once()
    mock_ollama.generate_metadata.assert_called_once()


def test_metadata_engine_both_failed():
    mock_gemini = MagicMock()
    mock_ollama = MagicMock()

    mock_gemini.generate_metadata.side_effect = GeminiInferenceError("Gemini down")
    mock_ollama.generate_metadata.side_effect = OllamaInferenceError("Ollama connection refused")

    engine = MetadataEngine(gemini_client=mock_gemini, ollama_client=mock_ollama)
    with pytest.raises(MetadataGenerationFailedError) as exc_info:
        engine.generate(caption="test", creator_username="user")

    assert "Metadata generation failed across all engines" in str(exc_info.value)


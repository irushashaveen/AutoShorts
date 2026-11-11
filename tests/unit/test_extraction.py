import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import httpx
import respx
from app.services.extraction import (
    TikWMClient,
    TikWMAPIError,
    YtDlpExtractor,
    YtDlpExtractionError,
    FFmpegNormalizer,
    FFmpegError,
    MediaExtractor,
    ExtractionFailedError,
    ExtractionResult,
)


@respx.mock
def test_tikwm_client_fetch_metadata(tmp_path):
    client = httpx.Client()
    tikwm = TikWMClient(client=client)

    sample_response = {
        "code": 0,
        "msg": "success",
        "data": {
            "id": "7999888777",
            "title": "Viral trend video #fyp",
            "cover": "https://tikwm.com/thumb.jpg",
            "play": "https://tikwm.com/play.mp4",
            "hdplay": "https://tikwm.com/hdplay.mp4",
            "duration": 28,
            "author": {
                "unique_id": "trendcreator",
                "nickname": "Trend Creator",
                "signature": "Check my YT: youtube.com/@trendcreator"
            }
        }
    }

    respx.post("https://www.tikwm.com/api/").respond(json=sample_response)
    data = tikwm.fetch_metadata("https://www.tiktok.com/@trendcreator/video/7999888777")

    assert data["id"] == "7999888777"
    assert data["author"]["unique_id"] == "trendcreator"
    assert data["hdplay"] == "https://tikwm.com/hdplay.mp4"


@respx.mock
def test_tikwm_client_extract_full_workflow(tmp_path):
    client = httpx.Client()
    tikwm = TikWMClient(client=client)

    sample_response = {
        "code": 0,
        "data": {
            "id": "7111222333",
            "title": "Cool short",
            "cover": "https://tikwm.com/thumb.jpg",
            "hdplay": "https://tikwm.com/video.mp4",
            "duration": 15,
            "author": {
                "unique_id": "shortcreator",
                "nickname": "Shorts Pro",
                "signature": "My bio"
            }
        }
    }

    respx.post("https://www.tikwm.com/api/").respond(json=sample_response)
    respx.get("https://tikwm.com/video.mp4").respond(status_code=200, content=b"fake_mp4_bytes")
    respx.get("https://tikwm.com/thumb.jpg").respond(status_code=200, content=b"fake_jpg_bytes")

    result = tikwm.extract("https://www.tiktok.com/@shortcreator/video/7111222333", staging_dir=tmp_path)

    assert result.video_id == "7111222333"
    assert result.video_path.exists()
    assert result.video_path.read_bytes() == b"fake_mp4_bytes"
    assert result.thumbnail_path.exists()
    assert result.thumbnail_path.read_bytes() == b"fake_jpg_bytes"
    assert result.creator_id == "shortcreator"
    assert result.engine_used == "tikwm"


@respx.mock
def test_tikwm_client_error():
    client = httpx.Client()
    tikwm = TikWMClient(client=client)

    respx.post("https://www.tikwm.com/api/").respond(json={"code": -1, "msg": "Video not found"})
    with pytest.raises(TikWMAPIError) as exc_info:
        tikwm.fetch_metadata("https://www.tiktok.com/@invalid/video/1")
    assert "Video not found" in str(exc_info.value)


def test_media_extractor_primary_success(tmp_path):
    mock_ytdlp = MagicMock()
    mock_tikwm = MagicMock()
    mock_normalizer = MagicMock()

    mock_result = ExtractionResult(
        video_id="12345",
        video_path=tmp_path / "12345.mp4",
        thumbnail_path=tmp_path / "12345_thumb.jpg",
        audio_path=None,
        caption="Primary test caption",
        creator_id="primary_user",
        creator_nickname="Primary User",
        creator_bio="Bio",
        duration=20.0,
        width=1080,
        height=1920,
        engine_used="yt-dlp"
    )
    mock_ytdlp.extract.return_value = mock_result
    mock_normalizer.normalize_video.return_value = tmp_path / "12345.mp4"
    mock_normalizer.extract_audio_wav.return_value = tmp_path / "12345_audio.wav"
    mock_normalizer.probe_video.return_value = {"width": 1080, "height": 1920, "duration": 20.0}

    extractor = MediaExtractor(ytdlp_extractor=mock_ytdlp, tikwm_client=mock_tikwm, normalizer=mock_normalizer)
    res = extractor.extract_media("https://www.tiktok.com/@primary_user/video/12345", tmp_path)

    assert res.engine_used == "yt-dlp"
    assert res.video_id == "12345"
    assert res.audio_path == tmp_path / "12345_audio.wav"
    mock_ytdlp.extract.assert_called_once()
    mock_tikwm.extract.assert_not_called()


def test_media_extractor_fallback_to_tikwm(tmp_path):
    mock_ytdlp = MagicMock()
    mock_tikwm = MagicMock()
    mock_normalizer = MagicMock()

    # yt-dlp raises error (simulating HTTP 403 / anti-scraping block)
    mock_ytdlp.extract.side_effect = YtDlpExtractionError("HTTP 403 Forbidden")

    mock_fallback_result = ExtractionResult(
        video_id="54321",
        video_path=tmp_path / "54321.mp4",
        thumbnail_path=tmp_path / "54321_thumb.jpg",
        audio_path=None,
        caption="Fallback caption",
        creator_id="fallback_user",
        creator_nickname="Fallback User",
        creator_bio="Bio",
        duration=15.0,
        width=0,
        height=0,
        engine_used="tikwm"
    )
    mock_tikwm.extract.return_value = mock_fallback_result
    mock_normalizer.normalize_video.return_value = tmp_path / "54321.mp4"
    mock_normalizer.extract_audio_wav.return_value = tmp_path / "54321_audio.wav"
    mock_normalizer.probe_video.return_value = {"width": 1080, "height": 1920, "duration": 15.0}

    extractor = MediaExtractor(ytdlp_extractor=mock_ytdlp, tikwm_client=mock_tikwm, normalizer=mock_normalizer)
    res = extractor.extract_media("https://www.tiktok.com/@fallback_user/video/54321", tmp_path)

    assert res.engine_used == "tikwm"
    assert res.video_id == "54321"
    assert res.audio_path == tmp_path / "54321_audio.wav"
    mock_ytdlp.extract.assert_called_once()
    mock_tikwm.extract.assert_called_once()


def test_media_extractor_all_failed(tmp_path):
    mock_ytdlp = MagicMock()
    mock_tikwm = MagicMock()

    mock_ytdlp.extract.side_effect = YtDlpExtractionError("yt-dlp blocked")
    mock_tikwm.extract.side_effect = TikWMAPIError("TikWM rate limit 429")

    extractor = MediaExtractor(ytdlp_extractor=mock_ytdlp, tikwm_client=mock_tikwm)
    with pytest.raises(ExtractionFailedError) as exc_info:
        extractor.extract_media("https://www.tiktok.com/@blocked/video/999", tmp_path)

    assert "Extraction failed across all engines" in str(exc_info.value)


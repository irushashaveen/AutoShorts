import pytest
import respx
import httpx
from app.services.extraction.sanitizer import URLSanitizer, InvalidTikTokURLError


def test_strip_tracking_params():
    raw = "https://www.tiktok.com/@mrbeast/video/7123456789012345678?_t=8abcDEF&_r=1&is_from_webapp=1&sender_device=pc"
    cleaned = URLSanitizer.strip_tracking_params(raw)
    assert cleaned == "https://www.tiktok.com/@mrbeast/video/7123456789012345678"


def test_validate_domain():
    assert URLSanitizer.validate_domain("https://www.tiktok.com/@user/video/123") is True
    assert URLSanitizer.validate_domain("https://vm.tiktok.com/ZM8abc/") is True
    assert URLSanitizer.validate_domain("https://vt.tiktok.com/ZS8abc/") is True
    assert URLSanitizer.validate_domain("https://instagram.com/p/12345") is False
    assert URLSanitizer.validate_domain("https://malicious-tiktok.com.fake/123") is False


def test_extract_video_id_and_username():
    url = "https://www.tiktok.com/@khaby.lame/video/7234567890123456789"
    assert URLSanitizer.extract_username(url) == "khaby.lame"
    assert URLSanitizer.extract_video_id(url) == "7234567890123456789"


def test_normalize_url_canonical():
    raw = "https://www.tiktok.com/@zachking/video/7987654321098765432?lang=en"
    clean = URLSanitizer.normalize_url(raw)
    assert clean == "https://www.tiktok.com/@zachking/video/7987654321098765432"


def test_normalize_invalid_domain_raises():
    with pytest.raises(InvalidTikTokURLError):
        URLSanitizer.normalize_url("https://youtube.com/watch?v=123456")


@respx.mock
def test_normalize_shortened_redirect():
    short_url = "https://vm.tiktok.com/ZM8xyz123/"
    resolved_url = "https://www.tiktok.com/@charlidamelio/video/7345678901234567890?_t=8abc"

    client = httpx.Client(follow_redirects=True)
    respx.head(short_url).respond(
        status_code=301,
        headers={"Location": resolved_url}
    )
    respx.head(resolved_url).respond(status_code=200)

    clean = URLSanitizer.normalize_url(short_url, client=client)
    assert clean == "https://www.tiktok.com/@charlidamelio/video/7345678901234567890"

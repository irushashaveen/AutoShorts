import pytest
from app.bot.keyboards.inline import (
    build_review_keyboard,
    build_duplicate_alert_keyboard,
    build_creator_alert_keyboard,
    build_upload_success_keyboard,
)
from app.bot.handlers.submission import TIKTOK_URL_REGEX
from app.bot.main import build_dispatcher


def test_build_review_keyboard():
    kb = build_review_keyboard("task_123")
    assert len(kb.inline_keyboard) == 2
    # First row is Approve
    assert kb.inline_keyboard[0][0].callback_data == "approve:task_123"
    # Second row contains Regenerate & Reject
    assert kb.inline_keyboard[1][0].callback_data == "regen:task_123"
    assert kb.inline_keyboard[1][1].callback_data == "reject:task_123"


def test_build_duplicate_alert_keyboard():
    kb = build_duplicate_alert_keyboard("task_456")
    assert len(kb.inline_keyboard) == 2
    assert kb.inline_keyboard[0][0].callback_data == "force_upload:task_456"
    assert kb.inline_keyboard[1][0].callback_data == "reject:task_456"


def test_build_creator_alert_keyboard():
    kb = build_creator_alert_keyboard("task_789", "@tech_channel")
    assert len(kb.inline_keyboard) == 2
    assert kb.inline_keyboard[0][0].url == "https://youtube.com/tech_channel"
    assert kb.inline_keyboard[1][0].callback_data == "allow_creator:task_789"


def test_build_upload_success_keyboard():
    kb = build_upload_success_keyboard("yt_abc123")
    assert kb.inline_keyboard[0][0].url == "https://youtube.com/shorts/yt_abc123"


def test_tiktok_url_regex_matching():
    text1 = "Hey check out this video https://www.tiktok.com/@mrbeast/video/7123456789 it is wild"
    match1 = TIKTOK_URL_REGEX.search(text1)
    assert match1 is not None
    assert "https://www.tiktok.com/@mrbeast/video/7123456789" in match1.group(0)

    text2 = "Sharing https://vm.tiktok.com/ZM8xyz123/ from mobile"
    match2 = TIKTOK_URL_REGEX.search(text2)
    assert match2 is not None

    text_invalid = "Look at this https://youtube.com/shorts/12345"
    assert TIKTOK_URL_REGEX.search(text_invalid) is None


def test_dispatcher_construction():
    dp = build_dispatcher()
    assert dp is not None
    assert len(dp.sub_routers) == 3


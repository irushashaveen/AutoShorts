from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_review_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Inline keyboard for staged video review card."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve & Auto-Schedule", callback_data=f"approve:{task_id}")
        ],
        [
            InlineKeyboardButton(text="⚡ Regenerate AI", callback_data=f"regen:{task_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"reject:{task_id}")
        ]
    ])


def build_duplicate_alert_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Inline keyboard when video is flagged as duplicate suspect (R_dup > 0.75)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚠️ Force Upload Anyway", callback_data=f"force_upload:{task_id}")
        ],
        [
            InlineKeyboardButton(text="🗑️ Discard Video", callback_data=f"reject:{task_id}")
        ]
    ])


def build_creator_alert_keyboard(task_id: str, yt_handle: str) -> InlineKeyboardMarkup:
    """Inline keyboard when TikTok author has official YouTube channel."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🔍 View {yt_handle}", url=f"https://youtube.com/{yt_handle.lstrip('@')}")
        ],
        [
            InlineKeyboardButton(text="⚠️ Allow Re-post", callback_data=f"allow_creator:{task_id}"),
            InlineKeyboardButton(text="🚫 Cancel Task", callback_data=f"reject:{task_id}")
        ]
    ])


def build_upload_success_keyboard(youtube_id: str) -> InlineKeyboardMarkup:
    """Inline keyboard delivered upon successful YouTube publication."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎬 Watch on YouTube Shorts", url=f"https://youtube.com/shorts/{youtube_id}")
        ],
        [
            InlineKeyboardButton(text="📋 Check Queue Status", callback_data="cmd:queue")
        ]
    ])


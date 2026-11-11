import re
import logging
from aiogram import Router, F
from aiogram.types import Message
from app.database import SessionLocal
from app.models import Task, TaskStatus
from app.services.extraction import URLSanitizer, InvalidTikTokURLError
from app.bot.keyboards.inline import build_review_keyboard

logger = logging.getLogger(__name__)
router = Router()

TIKTOK_URL_REGEX = re.compile(
    r"https?://(?:[a-zA-Z0-9_\-]+\.)?tiktok\.com/[^\s]+"
)


@router.message(F.text.regexp(TIKTOK_URL_REGEX))
async def handle_tiktok_link_submission(message: Message):
    """Detects and ingests TikTok links shared from mobile app or web."""
    match = TIKTOK_URL_REGEX.search(message.text)
    if not match:
        return

    raw_url = match.group(0)

    try:
        clean_url = URLSanitizer.normalize_url(raw_url)
    except InvalidTikTokURLError:
        await message.reply("❌ Invalid TikTok URL. Please share a valid TikTok video link.")
        return

    db = SessionLocal()
    try:
        # Check if already in database
        existing = db.query(Task).filter(Task.normalized_url == clean_url).first()
        if existing:
            await message.reply(
                f"ℹ️ This video is already staged in the pipeline with status `{existing.status.value}`.",
                parse_mode="Markdown"
            )
            return

        # Create new task
        task = Task(
            source_url=raw_url,
            normalized_url=clean_url,
            status=TaskStatus.QUEUED
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # Dispatch Celery pipeline task
        try:
            from app.tasks.pipeline import process_pipeline_task
            process_pipeline_task.delay(task.id)
        except Exception as e:
            logger.warning(f"Could not dispatch to Celery broker: {e}")

        text = (
            "📥 **Video Ingested Successfully**\n\n"
            f"• **Source URL**: `{clean_url}`\n"
            f"• **Task ID**: `{task.id}`\n"
            f"• **Status**: `QUEUED` ➔ Starting watermark-free extraction...\n\n"
            "You will receive an update once extraction and deduplication checks finish."
        )
        await message.reply(text, parse_mode="Markdown")

    finally:
        db.close()


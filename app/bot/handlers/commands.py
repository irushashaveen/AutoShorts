import logging
from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from app.database import SessionLocal
from app.models import Task, TaskStatus, AnalyticsCache
from app.services.youtube import QuotaTracker

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Welcome handler introducing the autonomous curation bot."""
    text = (
        "⚡ **AutoShorts Operator Bot Active**\n\n"
        "Share any TikTok video or mobile share link directly to this chat.\n\n"
        "**Available Commands:**\n"
        "• `/queue` - View active staged videos and review backlog\n"
        "• `/stats` - View 30-day view analytics and peak engagement hour\n"
        "• `/pause` - Pause automated publishing\n"
        "• `/resume` - Resume automated publishing"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("queue"))
async def cmd_queue(message: Message):
    """Lists current video tasks segmented by status."""
    db = SessionLocal()
    try:
        tasks = db.query(Task).order_by(Task.created_at.desc()).limit(10).all()
        if not tasks:
            await message.answer("📭 The curation queue is currently empty.")
            return

        lines = ["📋 **AutoShorts Pipeline Backlog:**\n"]
        for t in tasks:
            title = t.ai_title or t.raw_caption or "Pending Extraction"
            truncated_title = (title[:40] + "...") if len(title) > 40 else title
            status_icon = {
                TaskStatus.QUEUED: "⏳",
                TaskStatus.EXTRACTING: "📥",
                TaskStatus.EXTRACTED: "⚙️",
                TaskStatus.VERIFYING: "🔍",
                TaskStatus.FLAGGED_CREATOR_CHANNEL: "⚠️",
                TaskStatus.DUPLICATE_SUSPECT: "🚫",
                TaskStatus.READY_FOR_REVIEW: "✅",
                TaskStatus.SCHEDULED: "🕒",
                TaskStatus.UPLOADING: "🚀",
                TaskStatus.PUBLISHED: "🎉",
                TaskStatus.REJECTED: "🗑️"
            }.get(t.status, "•")

            lines.append(f"{status_icon} `[{t.status.value}]` {truncated_title}")

        await message.answer("\n".join(lines), parse_mode="Markdown")
    finally:
        db.close()


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Outputs situational awareness stats and quota tracking."""
    db = SessionLocal()
    try:
        quota_used = QuotaTracker.get_today_consumption(db)
        cached = db.query(AnalyticsCache).order_by(AnalyticsCache.calculated_at.desc()).first()
        peak_hour = cached.peak_hour_utc if cached else 15
        total_views = cached.total_views_30d if cached else 0
        published_count = db.query(Task).filter(Task.status == TaskStatus.PUBLISHED).count()

        text = (
            "📊 **AutoShorts 30-Day Channel Telemetry**\n\n"
            f"• **Shorts Published**: {published_count}\n"
            f"• **Historical Views (30d)**: {total_views:,}\n"
            f"• **Peak Audience Slot**: `{peak_hour}:00 UTC`\n"
            f"• **Daily YouTube Quota**: `{quota_used} / 10,000 units`\n"
        )
        await message.answer(text, parse_mode="Markdown")
    finally:
        db.close()

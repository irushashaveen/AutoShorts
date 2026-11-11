import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from app.database import SessionLocal
from app.models import Task, TaskStatus, AnalyticsCache
from app.services.youtube import AnalyticsScheduler
from app.services.ai import MetadataEngine
from app.config import settings

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("approve:"))
async def handle_approve_callback(callback: CallbackQuery):
    """Handles operator approval via Telegram inline keyboard."""
    task_id = callback.data.split(":", 1)[1]
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            await callback.answer("Task not found.", show_alert=True)
            return

        cached = db.query(AnalyticsCache).order_by(AnalyticsCache.calculated_at.desc()).first()
        peak_hour = cached.peak_hour_utc if cached else settings.DEFAULT_PUBLISH_HOUR_UTC
        scheduled_time = AnalyticsScheduler.calculate_publish_timestamp(peak_hour)

        task.scheduled_publish_at = scheduled_time
        task.status = TaskStatus.SCHEDULED
        db.commit()

        await callback.message.edit_text(
            f"✅ **Approved & Auto-Scheduled**\n\n"
            f"• **Title**: {task.ai_title}\n"
            f"• **Publication Time**: `{scheduled_time.strftime('%Y-%m-%d %H:%M:%S UTC')}`\n"
            f"• **Status**: `SCHEDULED`",
            parse_mode="Markdown"
        )
        await callback.answer("Video scheduled for optimal engagement slot!")
    finally:
        db.close()


@router.callback_query(F.data.startswith("reject:"))
async def handle_reject_callback(callback: CallbackQuery):
    """Handles operator rejection / discarding."""
    task_id = callback.data.split(":", 1)[1]
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatus.REJECTED
            db.commit()

        await callback.message.edit_text(
            "🗑️ **Task Discarded**\nThe video has been rejected and will not be published.",
            parse_mode="Markdown"
        )
        await callback.answer("Task discarded.")
    finally:
        db.close()


@router.callback_query(F.data.startswith("force_upload:"))
async def handle_force_upload_callback(callback: CallbackQuery):
    """Allows manual override of duplicate suspect flag."""
    task_id = callback.data.split(":", 1)[1]
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            await callback.answer("Task not found.", show_alert=True)
            return

        task.status = TaskStatus.OPTIMIZING
        db.commit()

        # Re-trigger pipeline
        try:
            from app.tasks.pipeline import process_pipeline_task
            process_pipeline_task.delay(task.id)
        except Exception:
            pass

        await callback.message.edit_text(
            "⚠️ **Duplicate Warning Overridden**\nProceeding with AI metadata optimization...",
            parse_mode="Markdown"
        )
        await callback.answer("Override accepted.")
    finally:
        db.close()


@router.callback_query(F.data.startswith("allow_creator:"))
async def handle_allow_creator_callback(callback: CallbackQuery):
    """Allows manual authorization when creator has an official YouTube channel."""
    task_id = callback.data.split(":", 1)[1]
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            await callback.answer("Task not found.", show_alert=True)
            return

        task.status = TaskStatus.OPTIMIZING
        db.commit()

        try:
            from app.tasks.pipeline import process_pipeline_task
            process_pipeline_task.delay(task.id)
        except Exception:
            pass

        await callback.message.edit_text(
            "⚠️ **Creator Re-post Authorized**\nProceeding with metadata optimization...",
            parse_mode="Markdown"
        )
        await callback.answer("Authorized.")
    finally:
        db.close()


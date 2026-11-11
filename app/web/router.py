import json
import logging
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, Form, Request, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.config import settings
from app.models import Task, Creator, TaskStatus, AnalyticsCache, User
from app.schemas.task import TaskResponse
from app.services.extraction import URLSanitizer, InvalidTikTokURLError
from app.services.youtube import QuotaTracker, AnalyticsScheduler
from app.services.ai import MetadataEngine
from app.core.events import broadcaster
from app.core.deps import get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

# Template directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Add custom Jinja2 filter for parsing JSON tags
def from_json_filter(value):
    if not value:
        return []
    try:
        return json.loads(value)
    except Exception:
        return []

templates.env.filters["from_json"] = from_json_filter


@router.get("/", response_class=HTMLResponse)
def get_dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Render the dark-mode main operational workspace."""
    tasks = db.query(Task).order_by(Task.created_at.desc()).limit(50).all()
    quota_used = QuotaTracker.get_today_consumption(db)

    # Metrics
    queue_count = db.query(Task).filter(Task.status != TaskStatus.PUBLISHED).count()
    ready_count = db.query(Task).filter(Task.status == TaskStatus.READY_FOR_REVIEW).count()
    flagged_count = db.query(Task).filter(
        or_(
            Task.status == TaskStatus.FLAGGED_CREATOR_CHANNEL,
            Task.status == TaskStatus.DUPLICATE_SUSPECT
        )
    ).count()
    published_count = db.query(Task).filter(Task.status == TaskStatus.PUBLISHED).count()

    cached = db.query(AnalyticsCache).order_by(AnalyticsCache.calculated_at.desc()).first()
    peak_hour = cached.peak_hour_utc if cached else settings.DEFAULT_PUBLISH_HOUR_UTC
    avg_duration = cached.avg_view_duration if cached else 0.0

    user_context = current_user if isinstance(current_user, User) else None

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "tasks": tasks,
            "quota_used": quota_used,
            "queue_count": queue_count,
            "ready_count": ready_count,
            "flagged_count": flagged_count,
            "published_count": published_count,
            "peak_hour": peak_hour,
            "avg_view_duration": avg_duration,
            "current_user": user_context,
            "title": "AutoShorts - Autonomous Shorts Publishing"
        }
    )


@router.post("/api/queue/submit", response_class=HTMLResponse)
def submit_video_url(
    request: Request,
    url: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Intake endpoint for TikTok URLs submitted from Web or Telegram."""
    try:
        clean_url = URLSanitizer.normalize_url(url)
    except InvalidTikTokURLError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check if duplicate submission in queue
    existing = db.query(Task).filter(Task.normalized_url == clean_url).first()
    if existing:
        return templates.TemplateResponse(
            request=request,
            name="partials/queue_card.html",
            context={"task": existing}
        )

    # Create new task in SQLite
    task = Task(
        source_url=url,
        normalized_url=clean_url,
        status=TaskStatus.QUEUED
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Trigger Celery asynchronous worker task
    try:
        from app.tasks.pipeline import process_pipeline_task
        process_pipeline_task.delay(task.id)
    except Exception as e:
        logger.warning(f"Could not dispatch to Celery broker: {e}. Executing synchronously or queuing.")

    return templates.TemplateResponse(
        request=request,
        name="partials/queue_card.html",
        context={"task": task}
    )


@router.post("/api/queue/{task_id}/approve", response_class=HTMLResponse)
def approve_and_schedule(
    request: Request,
    task_id: str,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Operator approval: saves edited title/description and schedules publication."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if title:
        task.ai_title = title.strip()
    if description:
        task.ai_description = description.strip()

    # Calculate optimal publishing slot
    cached = db.query(AnalyticsCache).order_by(AnalyticsCache.calculated_at.desc()).first()
    peak_hour = cached.peak_hour_utc if cached else settings.DEFAULT_PUBLISH_HOUR_UTC
    scheduled_time = AnalyticsScheduler.calculate_publish_timestamp(peak_hour)

    task.scheduled_publish_at = scheduled_time
    task.status = TaskStatus.SCHEDULED
    db.commit()
    db.refresh(task)

    return templates.TemplateResponse(
        request=request,
        name="partials/queue_card.html",
        context={"task": task}
    )


@router.put("/api/queue/{task_id}/metadata", response_class=HTMLResponse)
def update_metadata(
    request: Request,
    task_id: str,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Inline metadata editor for modifying titles and descriptions."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if title:
        task.ai_title = title.strip()
    if description:
        task.ai_description = description.strip()

    db.commit()
    db.refresh(task)

    return templates.TemplateResponse(
        request=request,
        name="partials/queue_card.html",
        context={"task": task}
    )


@router.post("/api/queue/{task_id}/regenerate-ai", response_class=HTMLResponse)
def regenerate_ai_metadata(
    request: Request,
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Re-executes AI metadata generation via Gemini or Ollama."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    engine = MetadataEngine()
    try:
        creator_id = task.creator_id or "creator"
        creator_nickname = task.creator.nickname if task.creator else ""
        ai_out, engine_used = engine.generate(
            caption=task.raw_caption or "",
            creator_username=creator_id,
            creator_nickname=creator_nickname or "",
            duration=task.duration or 0.0
        )
        task.ai_title = ai_out.title
        task.ai_description = ai_out.description
        task.ai_tags = json.dumps(ai_out.tags)
        task.ai_engine_used = engine_used
        db.commit()
        db.refresh(task)
    except Exception as e:
        logger.error(f"Regenerate AI failed: {e}")

    return templates.TemplateResponse(
        request=request,
        name="partials/queue_card.html",
        context={"task": task}
    )


@router.delete("/api/queue/{task_id}", response_class=HTMLResponse)
def discard_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deletes task and staging files from disk."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Clean staging files
    if task.media_path and Path(task.media_path).exists():
        try:
            Path(task.media_path).unlink(missing_ok=True)
        except Exception:
            pass

    if task.thumbnail_path and Path(task.thumbnail_path).exists():
        try:
            Path(task.thumbnail_path).unlink(missing_ok=True)
        except Exception:
            pass

    db.delete(task)
    db.commit()
    return HTMLResponse(content="", status_code=200)


@router.get("/api/media/{task_id}/thumbnail")
def get_thumbnail(task_id: str, db: Session = Depends(get_db)):
    """Serve staged video thumbnail."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task or not task.thumbnail_path or not Path(task.thumbnail_path).exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(task.thumbnail_path)


@router.get("/api/events/stream")
async def sse_event_stream():
    """Server-Sent Events endpoint for real-time queue synchronization."""
    return EventSourceResponse(broadcaster.event_generator())


@router.get("/api/health")
def healthcheck():
    """Container healthcheck probe."""
    return {
        "status": "healthy",
        "service": "AutoShorts",
        "version": "0.1.0"
    }


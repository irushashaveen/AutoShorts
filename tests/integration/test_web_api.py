import pytest
from unittest.mock import MagicMock
from fastapi import Request
from app.models import Task, TaskStatus
from app.web.router import (
    healthcheck,
    get_dashboard,
    submit_video_url,
    approve_and_schedule,
    update_metadata,
    discard_task,
)


@pytest.fixture
def mock_request():
    """Mock FastAPI Request object with scope for template rendering."""
    req = MagicMock(spec=Request)
    req.scope = {"type": "http", "app": None}
    return req


def test_healthcheck_route():
    res = healthcheck()
    assert res["status"] == "healthy"
    assert res["service"] == "AutoShorts"


def test_dashboard_route(mock_request, db_session):
    task = Task(
        source_url="https://www.tiktok.com/@creator/video/123",
        normalized_url="https://www.tiktok.com/@creator/video/123",
        status=TaskStatus.READY_FOR_REVIEW,
        ai_title="Awesome Test Short"
    )
    db_session.add(task)
    db_session.commit()

    response = get_dashboard(mock_request, db=db_session)
    assert response.status_code == 200
    assert response.template.name == "dashboard.html"
    assert response.context["queue_count"] == 1


def test_submit_valid_url_route(mock_request, db_session):
    url = "https://www.tiktok.com/@mrbeast/video/7123456789012345678?_t=8abc"
    response = submit_video_url(mock_request, url=url, db=db_session)
    assert response.status_code == 200
    assert response.template.name == "partials/queue_card.html"

    created = db_session.query(Task).filter(
        Task.normalized_url == "https://www.tiktok.com/@mrbeast/video/7123456789012345678"
    ).first()
    assert created is not None
    assert created.status == TaskStatus.QUEUED


def test_submit_invalid_domain_raises(mock_request, db_session):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        submit_video_url(mock_request, url="https://instagram.com/reel/12345", db=db_session)
    assert exc_info.value.status_code == 400


def test_approve_task_route(mock_request, db_session):
    task = Task(
        source_url="https://www.tiktok.com/@user/video/555",
        normalized_url="https://www.tiktok.com/@user/video/555",
        status=TaskStatus.READY_FOR_REVIEW,
        ai_title="Original Title"
    )
    db_session.add(task)
    db_session.commit()

    response = approve_and_schedule(
        mock_request,
        task_id=task.id,
        title="Approved & Edited Title",
        description="New description",
        db=db_session
    )
    assert response.status_code == 200

    updated = db_session.query(Task).filter(Task.id == task.id).first()
    assert updated.status == TaskStatus.SCHEDULED
    assert updated.ai_title == "Approved & Edited Title"
    assert updated.scheduled_publish_at is not None


def test_update_metadata_route(mock_request, db_session):
    task = Task(
        source_url="https://www.tiktok.com/@user/video/777",
        normalized_url="https://www.tiktok.com/@user/video/777",
        status=TaskStatus.QUEUED
    )
    db_session.add(task)
    db_session.commit()

    response = update_metadata(
        mock_request,
        task_id=task.id,
        title="Custom Inline Title",
        description="Custom Description",
        db=db_session
    )
    assert response.status_code == 200

    updated = db_session.query(Task).filter(Task.id == task.id).first()
    assert updated.ai_title == "Custom Inline Title"


def test_discard_task_route(db_session):
    task = Task(
        source_url="https://www.tiktok.com/@user/video/999",
        normalized_url="https://www.tiktok.com/@user/video/999",
        status=TaskStatus.QUEUED
    )
    db_session.add(task)
    db_session.commit()
    task_id = task.id

    response = discard_task(task_id=task_id, db=db_session)
    assert response.status_code == 200

    deleted = db_session.query(Task).filter(Task.id == task_id).first()
    assert deleted is None

---
name: autoshorts-pipeline
description: >-
  Use this skill to operate, inspect, troubleshoot, and execute the AutoShorts autonomous TikTok-to-YouTube-Shorts pipeline, including ingestion, extraction, deduplication, AI metadata generation, scheduling, and resumable YouTube uploads.
---

# AutoShorts Autonomous Pipeline Skill

This skill provides operational workflows, diagnostic commands, and runbooks for the **AutoShorts** autonomous cross-publishing pipeline.

## 1. Operational Overview

The AutoShorts system automates vertical video curation through 6 orchestrated phases:
1. **Ingestion & URL Sanitization**: Validates TikTok mobile/web URLs, strips tracking parameters.
2. **Media Extraction**: Primary extraction with `yt-dlp`; automated fallback to TikWM REST API; FFmpeg 1080x1920 portrait normalization.
3. **Creator & Duplicate Verification**: Bio regex scanning for official YouTube channels, Chromaprint acoustic fingerprinting, TF-IDF + Levenshtein caption deduplication ($R_{dup} > 0.75$).
4. **AI Metadata Transformation**: Google Gemini 1.5 Flash (primary, JSON schema mode) with local Ollama Qwen 2.5 3B fallback.
5. **Scheduling & Publication**: YouTube Analytics hourly viewer engagement optimization, 5 MB chunked resumable upload to YouTube Shorts.
6. **Telemetry & Control**: Telegram Bot (`aiogram 3.x`) and Web Dashboard (FastAPI + HTMX + SSE).

---

## 2. Common CLI & Service Operations

### Running Services with Docker Compose
```powershell
# Start all microservices in background (Redis, Celery, Web, Bot, Ollama)
docker compose up -d

# Check running status
docker compose ps

# Inspect logs for a specific service
docker compose logs -f web
docker compose logs -f celery_worker
docker compose logs -f telegram_bot
```

### Local Development Mode
```powershell
# Run FastAPI server locally
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run Celery Worker locally (using Windows solo pool for dev if needed)
celery -A app.core.celery_app worker --loglevel=info -P solo

# Run Telegram Bot locally
python -m app.bot.main
```

---

## 3. Pipeline Troubleshooting Runbook

### Issue A: TikTok Anti-Scraping / 403 Forbidden
1. Check Celery task logs for `yt_dlp.utils.DownloadError`.
2. Verify secondary extraction (`TikWMClient`) fallback engagement.
3. If TikWM returns rate limit, configure rotating user-agents or proxy support in `.env`.

### Issue B: Gemini API Rate Limit (429)
1. Verify `GEMINI_API_KEY` status and quota.
2. Ensure Ollama service is reachable at `http://ollama:11434` (or `http://localhost:11434`).
3. Verify `qwen2.5:3b` model is pulled: `docker exec -it autoshorts_ollama ollama pull qwen2.5:3b`.

### Issue C: YouTube Upload Quota Ceiling
1. Daily quota limit is 10,000 units (~6 uploads/day at 1,600 units each).
2. Check SQLite quota tracker: `SELECT SUM(quota_units) FROM youtube_quota_log WHERE date(created_at) = date('now')`.
3. If quota is near ceiling (>= 9,600 units), the pipeline freezes publishing until 00:00 PST.


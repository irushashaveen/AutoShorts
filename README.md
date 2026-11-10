# AutoShorts ⚡
### Autonomous TikTok to YouTube Shorts Curation & Publishing System

AutoShorts is an enterprise-grade, zero-cost pipeline engineered to ingest, curate, deduplicate, optimize, schedule, and publish vertical short-form video content from TikTok to YouTube Shorts.

---

## 🚀 Key Features

* **Dual Ingestion**: Seamless link submission via asynchronous Telegram Bot (`aiogram 3.x`) or responsive Dark-Mode Web Dashboard (`FastAPI` + `HTMX` + `Tailwind CSS`).
* **Resilient Media Extraction**: High-definition, watermark-free vertical video extraction via `yt-dlp` with automatic fallback to `TikWM REST API` and standard H.264/AAC 1080x1920 normalization via `FFmpeg`.
* **Cross-Platform Rights & Deduplication**:
  * Scans creator bio with regex heuristics to detect active, official YouTube channels.
  * Perceptual acoustic fingerprinting via `Chromaprint` (`pyacoustid`).
  * Sparse vector text proximity via `TF-IDF` cosine similarity and normalized Levenshtein distance ($R_{dup} > 0.75$).
* **AI Metadata Transformation**: Generates high-CTR titles (<60 chars, zero hashtags), 2-sentence descriptions with original creator attribution, and 3 targeted tags using Google Gemini 1.5 Flash (Free Tier) with automatic fallback to local Ollama (`qwen2.5:3b`).
* **Smart Publishing & Scheduling**: Queries YouTube Analytics API for channel-specific peak viewership hours, queuing 5 MB chunked resumable uploads via YouTube Data API v3 while strictly monitoring the 10,000 unit daily quota limit.
* **Zero Locking Database**: High-concurrency persistence powered by SQLite 3 in Write-Ahead Logging (WAL) mode.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Web & API** | FastAPI, Starlette, HTMX, Tailwind CSS, Server-Sent Events (SSE) |
| **Worker & Task Broker** | Celery 5.x, Redis 7.x |
| **Bot Intake** | aiogram 3.x, asyncio |
| **Extraction & Media** | yt-dlp, TikWM API, FFmpeg, ffprobe |
| **Fingerprinting & NLP** | Chromaprint (`pyacoustid`), scikit-learn, numpy |
| **Generative AI** | Google Gemini 1.5 Flash, Ollama (`qwen2.5:3b`) |
| **Destination API** | YouTube Data API v3, YouTube Analytics API v2 |
| **Persistence** | SQLite 3 (WAL Mode), SQLAlchemy 2.x |

---

## 📦 Directory Structure

```text
AutoShorts/
├── .agents/skills/               # Antigravity agent operational skills
│   ├── autoshorts-pipeline/SKILL.md
│   └── autoshorts-testing/SKILL.md
├── docs/                         # Technical specifications & plans
│   ├── DEVELOPMENT_PLAN.md
│   ├── TESTING_PLAN.md
│   ├── SYSTEM_ARCHITECTURE.md
│   └── DATABASE_SCHEMA.md
├── app/
│   ├── main.py                   # FastAPI application entrypoint
│   ├── config.py                 # Pydantic Settings & environment variables
│   ├── database.py               # SQLite WAL mode engine & session provider
│   ├── models/                   # SQLAlchemy ORM models (Task, Creator, Quota, etc.)
│   ├── schemas/                  # Pydantic validation schemas
│   ├── core/                     # Celery broker configuration & SSE broadcaster
│   ├── services/
│   │   ├── extraction/           # yt-dlp + TikWM fallback + FFmpeg
│   │   ├── verification/         # Bio regex + Chromaprint + TF-IDF risk score
│   │   ├── ai/                   # Gemini 1.5 Flash + Ollama Qwen 2.5 fallback
│   │   └── youtube/              # Resumable 5MB uploader + Quota tracker
│   ├── tasks/                    # Celery workflow definitions
│   ├── web/                      # HTMX dashboard templates & routes
│   └── bot/                      # aiogram 3.x Telegram review bot
├── tests/                        # Comprehensive unit & integration test suites
│   ├── unit/
│   └── integration/
├── docker/                       # Multi-stage container definitions
│   ├── Dockerfile.app
│   ├── Dockerfile.worker
│   └── Dockerfile.bot
├── docker-compose.yml            # Multi-service local & cloud orchestration
└── requirements.txt
```

---

## ⚡ Quickstart Guide

### 1. Environment Configuration
Copy `.env.example` to `.env` and fill in your API credentials:
```bash
cp .env.example .env
```

### 2. Local Testing with Docker Compose
To run all microservices locally in Docker containers:
```bash
# Start all containers in the background
docker compose up -d --build

# Inspect service logs
docker compose logs -f web
docker compose logs -f celery_worker
docker compose logs -f telegram_bot

# Access the Web Dashboard
open http://localhost:8000
```

### 3. Local Development (Without Docker)
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the FastAPI Dashboard
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Run Celery Worker (In separate terminal)
celery -A app.core.celery_app worker --loglevel=info -P solo

# 4. Run Telegram Bot (In separate terminal)
python -m app.bot.main
```

---

## 🧪 Running Automated Tests

AutoShorts contains a 100% network-isolated test suite using `respx` and `unittest.mock`:

```bash
# Run all unit and integration tests
pytest tests/ -v

# Run with test coverage report
pytest --cov=app --cov-report=term-missing tests/
```


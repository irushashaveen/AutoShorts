# AutoShorts: Phased Development Plan & Implementation Roadmap

## 1. Executive Summary & Goals

**AutoShorts** is an autonomous TikTok to YouTube Shorts curation, optimization, and publishing system engineered for zero-cost, high-reliability operation. It is designed to run in a containerized environment (local Docker for testing, deployable to Oracle Cloud Free Tier ARM64 A1 4 OCPU / 24 GB RAM).

### Core Capabilities
1. **Dual Ingestion**: Asynchronous Telegram Bot (`aiogram 3.x`) and Web Dashboard (`FastAPI` + `HTMX` + `Tailwind CSS`).
2. **Resilient Extraction**: Primary `yt-dlp` scraping with automated fallback to `TikWM REST API`, followed by FFmpeg normalization (1080x1920 portrait H.264/AAC).
3. **Intellectual Property & Deduplication Guardrails**: Creator bio regex scanning for official YouTube channels; dual-layer deduplication combining Chromaprint perceptual acoustic hashing and TF-IDF + Levenshtein caption similarity ($R_{dup} > 0.75$).
4. **AI-Driven Metadata Optimization**: Google Gemini 1.5 Flash (free tier) with automated fallback to local Ollama (`qwen2.5:3b`) producing high-CTR titles (<60 chars), keyword-rich descriptions, and 3 tags.
5. **Smart Publishing & Scheduling**: Dynamic optimal upload window calculation via YouTube Analytics API, followed by 5 MB chunked resumable upload with exponential backoff and 10,000 unit daily quota tracking.

---

## 2. Project Directory Structure

```text
AutoShorts/
├── .agents/
│   └── skills/
│       ├── autoshorts-pipeline/SKILL.md
│       └── autoshorts-testing/SKILL.md
├── docs/
│   ├── DEVELOPMENT_PLAN.md
│   ├── TESTING_PLAN.md
│   ├── SYSTEM_ARCHITECTURE.md
│   └── DATABASE_SCHEMA.md
├── app/
│   ├── __init__.py
│   ├── config.py                 # Pydantic Settings & environment variables
│   ├── database.py               # SQLite engine, WAL mode PRAGMA, SessionLocal
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── task.py               # Video processing task state machine
│   │   ├── fingerprint.py        # Chromaprint audio fingerprints & hashes
│   │   ├── quota.py              # YouTube API quota consumption log
│   │   └── analytics.py          # Cached YouTube analytics engagement metrics
│   ├── schemas/                  # Pydantic data schemas & contracts
│   │   ├── __init__.py
│   │   ├── task.py
│   │   └── metadata.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── celery_app.py         # Celery configuration & Redis broker
│   │   ├── events.py             # Server-Sent Events (SSE) dispatcher
│   │   └── security.py           # Authentication, API keys, and session tokens
│   ├── services/
│   │   ├── __init__.py
│   │   ├── extraction/           # Phase 2: Media extraction
│   │   │   ├── ytdlp_extractor.py
│   │   │   ├── tikwm_client.py
│   │   │   └── ffmpeg_normalizer.py
│   │   ├── verification/         # Phase 3: Creator & Deduplication
│   │   │   ├── bio_scanner.py
│   │   │   ├── acoustic_hasher.py
│   │   │   ├── text_similarity.py
│   │   │   └── risk_evaluator.py
│   │   ├── ai/                   # Phase 4: Metadata Optimization
│   │   │   ├── gemini_client.py
│   │   │   ├── ollama_client.py
│   │   │   └── metadata_engine.py
│   │   └── youtube/              # Phase 5: Publisher & Analytics
│   │       ├── oauth_manager.py
│   │       ├── analytics_scheduler.py
│   │       ├── uploader.py
│   │       └── quota_tracker.py
│   ├── tasks/                    # Celery asynchronous task definitions
│   │   ├── __init__.py
│   │   └── pipeline.py           # Orchestrated pipeline workflow tasks
│   ├── web/                      # Phase 6: FastAPI Web App & HTMX Templates
│   │   ├── __init__.py
│   │   ├── router.py             # API endpoints & HTMX partial views
│   │   ├── static/               # CSS, JS, media thumbnails
│   │   └── templates/            # Jinja2 templates (Dark-mode Tailwind)
│   │       ├── base.html
│   │       ├── dashboard.html
│   │       └── partials/
│   │           ├── queue_card.html
│   │           ├── quota_gauge.html
│   │           └── metrics_bar.html
│   └── bot/                      # Phase 6: Telegram Bot
│       ├── __init__.py
│       ├── main.py               # aiogram 3.x bot launcher
│       ├── handlers/
│       │   ├── submission.py     # Link intake & validation
│       │   ├── review.py         # Inline callback buttons (Approve/Reject/Edit)
│       │   └── commands.py       # /queue, /stats, /pause, /resume
│       └── keyboards/
│           └── inline.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Pytest fixtures & mock environment
│   ├── unit/                     # Unit test suite
│   ├── integration/              # Component & integration tests
│   └── fixtures/                 # Sample video/audio files and JSON payloads
├── docker/
│   ├── Dockerfile.app            # Multi-stage ARM64/AMD64 Python container
│   ├── Dockerfile.worker         # Celery task worker container with FFmpeg
│   └── Dockerfile.bot            # Lightweight Telegram bot container
├── docker-compose.yml            # Multi-container orchestration (Redis, Ollama, App, Worker, Bot)
├── pyproject.toml / requirements.txt
├── .env.example
└── README.md
```

---

## 3. Step-by-Step Implementation Roadmap

```
Step 1: Project Scaffolding, Core Config, & SQLite WAL Database
  │
Step 2: Ingestion & URL Sanitization Subsystem
  │
Step 3: Extraction Subsystem (yt-dlp + TikWM Fallback + FFmpeg)
  │
Step 4: Verification Subsystem (Bio Scanning + Chromaprint + TF-IDF)
  │
Step 5: AI Metadata Optimization Subsystem (Gemini 1.5 + Ollama Fallback)
  │
Step 6: YouTube Publisher & Analytics Scheduler (Chunked Resumable Upload)
  │
Step 7: Task Pipeline Orchestration (Celery + Redis + SQLite State)
  │
Step 8: FastAPI + HTMX Web Dashboard & Real-Time SSE
  │
Step 9: Telegram Review Bot (aiogram 3.x + Inline Keyboards)
  │
Step 10: Local Docker Orchestration & Multi-Container Integration Testing
```

### Detailed Phase Specifications

#### Step 1: Project Scaffolding, Core Config, & SQLite WAL Database
- **Objective**: Establish modular foundation, environment configuration, database engine, and ORM models.
- **Deliverables**:
  - `app/config.py`: Pydantic `BaseSettings` reading environment variables with sensible defaults.
  - `app/database.py`: SQLite engine with WAL mode PRAGMAs (`PRAGMA journal_mode=WAL;`, `PRAGMA synchronous=NORMAL;`, `PRAGMA busy_timeout=5000;`).
  - `app/models/`: Task, AudioFingerprint, QuotaLog, AnalyticsCache models.
  - `requirements.txt`: Curated, pinned dependencies.

#### Step 2: Ingestion & URL Sanitization Subsystem
- **Objective**: Normalize and sanitize input TikTok URLs, validate domains, and create staged task records.
- **Deliverables**:
  - Strip tracking parameters (`?_t=...`, `&_r=...`, `&is_from_webapp=...`).
  - Resolve shortened links (`vm.tiktok.com`, `vt.tiktok.com`).
  - Validate URL syntax against domain whitelist.

#### Step 3: Resilient Extraction Subsystem
- **Objective**: Download watermark-free 1080x1920 MP4 video streams and author profile metadata.
- **Deliverables**:
  - `YtDlpExtractor`: Primary extraction using `yt-dlp` CLI / Python API.
  - `TikWMClient`: Asynchronous HTTP fallback calling `https://www.tikwm.com/api/` on 403/429/bot detection.
  - `FFmpegNormalizer`: Probe video resolution/aspect ratio; transcode to standard 1080x1920 H.264/AAC if needed.

#### Step 4: Verification & Deduplication Subsystem
- **Objective**: Prevent copyright infringement and duplicate uploads before metadata generation.
- **Deliverables**:
  - `BioScanner`: Regex parsing of creator bio for YouTube handles (`@channel`, `youtube.com/...`) + YouTube search check.
  - `AcousticHasher`: FFmpeg audio extraction to 16kHz WAV + `pyacoustid` Chromaprint perceptual hashing.
  - `TextSimilarity`: TF-IDF vector cosine similarity and Levenshtein edit distance between captions.
  - `RiskEvaluator`: Weighted risk formula $R_{dup} = 0.50 \cdot \text{Match}_{audio} + 0.30 \cdot S_{cos} + 0.20 \cdot L_{norm}$. Flagging if $R_{dup} > 0.75$.

#### Step 5: AI Metadata Optimization Subsystem
- **Objective**: Transform raw TikTok captions into high-CTR YouTube Shorts metadata.
- **Deliverables**:
  - `GeminiClient`: Primary Google Gemini 1.5 Flash client enforcing JSON schema (`response_mime_type="application/json"`).
  - `OllamaClient`: Fallback client connecting to local Ollama instance running `qwen2.5:3b`.
  - `MetadataEngine`: Orchestrator managing prompt injection, timeout fallback (8s), format validation, and original creator attribution formatting.

#### Step 6: YouTube Publisher & Analytics Scheduler
- **Objective**: Execute dynamic scheduling and resumable chunked video uploads within daily quota bounds.
- **Deliverables**:
  - `OAuthManager`: Headless OAuth 2.0 flow with offline refresh token persistence.
  - `QuotaTracker`: Atomic tracking against 10,000 units/day limit (1,600 units/upload); pauses publishing if ceiling reached.
  - `AnalyticsScheduler`: Query YouTube Analytics API for peak hourly viewership in past 30 days; select optimal publication time.
  - `ResumableUploader`: 5 MB chunk streaming via YouTube Data API v3 `videos().insert(part="snippet,status")` with exponential backoff ($2^n$ retry).

#### Step 7: Pipeline Orchestration & State Machine
- **Objective**: Wire all subsystems into Celery asynchronous workflows with SQLite persistence and atomic transitions.
- **Deliverables**:
  - Celery task definitions with exponential retry policies.
  - State machine transitions (`QUEUED` -> `EXTRACTING` -> `VERIFYING` -> `OPTIMIZING` -> `PENDING_REVIEW` -> `SCHEDULED` -> `UPLOADING` -> `PUBLISHED` / `FLAGGED` / `FAILED`).
  - Redis broker configuration.

#### Step 8: FastAPI + HTMX Web Dashboard & Real-Time SSE
- **Objective**: Provide a responsive, low-latency dark-mode control interface.
- **Deliverables**:
  - Top system health bar: Quota gauge, worker heartbeat, queue summary metrics.
  - Staged video cards: 9:16 vertical thumbnail, creator attribution, AI metadata preview, duplicate risk score meter, approve/edit/regenerate/discard buttons.
  - Server-Sent Events (SSE) `/api/events/stream`: Live upload byte percentage streaming, worker status pulses, dynamic queue updates.

#### Step 9: Telegram Mobile Review Bot
- **Objective**: Provide instantaneous mobile intake and interactive approval.
- **Deliverables**:
  - `aiogram 3.x` bot handlers for receiving TikTok links directly from mobile share sheet.
  - Interactive inline review cards (`[Approve & Auto-Schedule]`, `[Edit Title]`, `[Reject]`).
  - Warning alerts for duplicate suspects and creator channel matches.
  - Commands: `/queue`, `/stats`, `/pause`, `/resume`.

#### Step 10: Local Docker Testing & Orchestration
- **Objective**: Multi-container dockerized deployment ready for local testing and ARM64 cloud rollout.
- **Deliverables**:
  - `docker-compose.yml` defining `redis`, `ollama`, `web`, `celery_worker`, and `telegram_bot`.
  - Memory caps and resource constraints matching ARM64 budget (4 OCPU, 24 GB RAM).
  - Health checks and persistent volume mappings for staging media, SQLite database, and Ollama weights.


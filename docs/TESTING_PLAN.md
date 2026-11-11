# AutoShorts: Master Testing Plan & Verification Strategy

## 1. Testing Philosophy & Guiding Principles

The **AutoShorts** testing framework guarantees that all subsystems operate deterministically, safely, and without incurring unexpected external costs or quota depletion.

### Core Testing Directives
1. **Zero External API Leaks in Tests**: Unit and integration test suites must never make unmocked calls to the live YouTube Data API, Google Gemini API, or live TikTok endpoints. All network traffic is intercepted using `respx` and `unittest.mock`.
2. **Deterministic Deduplication Verification**: Use fixed, pre-computed Chromaprint audio fingerprints and standardized text strings to test scoring thresholds ($R_{dup} = 0.75$).
3. **Database Isolation**: Tests execute against isolated SQLite instances configured with WAL mode or temporary memory databases (`sqlite:///:memory:`).
4. **Resilience & Fallback Validation**: Every primary-to-fallback transition (`yt-dlp` -> TikWM; Gemini -> Ollama) must have dedicated test cases verifying seamless recovery.
5. **Local Docker Validation**: Containerized integration tests confirm memory caps, inter-container networking, Redis queuing, and volume bindings.

---

## 2. Test Architecture & Structure

```text
tests/
├── conftest.py                   # Global fixtures (DB session, mock clients, test settings)
├── fixtures/
│   ├── payloads/
│   │   ├── tikwm_response.json   # Sample TikWM API payload
│   │   ├── gemini_response.json  # Sample Gemini JSON completion
│   │   ├── ollama_response.json  # Sample Ollama completion
│   │   └── youtube_channel.json  # Sample YouTube API channel response
│   └── media/
│       ├── test_sample.wav       # 5-second 16kHz mono audio fixture
│       └── sample_fingerprint.txt # Known Chromaprint hash string
├── unit/
│   ├── test_config.py            # Settings validation & default fallbacks
│   ├── test_url_sanitizer.py     # Regex sanitization & redirect resolver
│   ├── test_bio_scanner.py       # Creator YouTube handle regex extraction
│   ├── test_text_similarity.py   # TF-IDF cosine similarity & Levenshtein distance
│   ├── test_acoustic_hasher.py   # Audio fingerprint generation & bit distance
│   ├── test_risk_evaluator.py    # Composite duplicate risk score math
│   ├── test_metadata_engine.py   # AI prompt parsing, schema validation, length rules
│   └── test_quota_tracker.py     # YouTube daily quota calculation and freeze logic
├── integration/
│   ├── test_extraction_fallback.py # yt-dlp failure simulation -> TikWM fallback
│   ├── test_ai_fallback.py       # Gemini 429/timeout -> Ollama fallback
│   ├── test_resumable_upload.py  # 5MB chunk streaming & exponential backoff retry
│   ├── test_db_concurrency.py    # SQLite WAL mode concurrent read/write transactions
│   └── test_api_endpoints.py     # FastAPI endpoints & HTMX partial HTML responses
└── docker/
    └── test_containers.py        # Docker service healthchecks & redis connectivity
```

---

## 3. Detailed Test Matrix by Subsystem

### 3.1 Subsystem 1: URL Sanitization & Ingestion

| Test ID | Test Scenario | Expected Outcome |
| :--- | :--- | :--- |
| `ING-01` | Clean desktop URL (`tiktok.com/@user/video/12345`) | Normalized URL without modification. |
| `ING-02` | Mobile share URL with query params (`?_t=8abc&_r=1`) | Tracking parameters stripped cleanly. |
| `ING-03` | Shortened mobile URL (`vm.tiktok.com/XYZ/`) | Resolved to canonical video URL. |
| `ING-04` | Non-TikTok domain (e.g. `instagram.com`, `phishing.site`) | Rejected with `InvalidSourceURLError`. |

### 3.2 Subsystem 2: Watermark-Free Extraction Engine

| Test ID | Test Scenario | Expected Outcome |
| :--- | :--- | :--- |
| `EXT-01` | `yt-dlp` returns exit code 0 | Saves 1080x1920 MP4 to staging path. |
| `EXT-02` | `yt-dlp` fails with HTTP 403 / 429 block | Automatically invokes TikWM REST API client. |
| `EXT-03` | TikWM returns valid payload | Downloads raw CDN stream and parses author bio. |
| `EXT-04` | Extracted video has non-standard aspect ratio | FFmpeg normalizes to 1080x1920 with letterboxing/padding. |
| `EXT-05` | Both `yt-dlp` and TikWM fail | Task marked as `FAILED_EXTRACTION` with retry scheduled. |

### 3.3 Subsystem 3: Creator & Deduplication Verification

| Test ID | Test Scenario | Expected Outcome |
| :--- | :--- | :--- |
| `VER-01` | TikTok bio contains `youtube.com/@CreatorHandle` | Extracted handle `@CreatorHandle` matches regex. |
| `VER-02` | TikTok bio contains shorthand `yt: creator_name` | Shorthand handle correctly extracted. |
| `VER-03` | Extracted handle matches verified channel via YouTube API | Task flagged as `FLAGGED_CREATOR_CHANNEL`, halts auto-schedule. |
| `VER-04` | Audio fingerprint match against existing database record | `Match_audio = 1.0`, contributing to $R_{dup}$. |
| `VER-05` | Identical captions tested with TF-IDF and Levenshtein | $S_{cos} \approx 1.0$, $L_{norm} \approx 1.0$. |
| `VER-06` | Composite Risk Calculation: High audio (1.0), high text (0.9) | $R_{dup} = 0.5(1.0) + 0.3(0.9) + 0.2(0.9) = 0.95 > 0.75$ -> `DUPLICATE_SUSPECT`. |
| `VER-07` | Completely novel video (Clean audio, novel caption) | $R_{dup} < 0.25$, pipeline proceeds to AI optimization. |

### 3.4 Subsystem 4: AI Metadata Optimization Engine

| Test ID | Test Scenario | Expected Outcome |
| :--- | :--- | :--- |
| `AIM-01` | Gemini returns valid JSON matching schema | Title < 60 chars, 2-sentence description, 3 tags parsed. |
| `AIM-02` | Gemini output contains title > 60 chars | Title truncated safely at boundary, logged warning. |
| `AIM-03` | Gemini returns HTTP 429 (Rate Limit) | Immediately switches to Ollama Qwen 2.5 3B local endpoint. |
| `AIM-04` | Gemini request times out (> 8.0s) | Request cancelled, Ollama fallback activated. |
| `AIM-05` | Description formatting check | Creator attribution appended at bottom of description. |

### 3.5 Subsystem 5: YouTube Resumable Upload & Scheduling

| Test ID | Test Scenario | Expected Outcome |
| :--- | :--- | :--- |
| `PUB-01` | Resumable upload chunk streaming (5MB intervals) | Each chunk uploaded with valid `Range` headers. |
| `PUB-02` | Chunk upload encounters transient HTTP 502/503 | Retries chunk with exponential backoff ($2^n$ seconds, up to 5x). |
| `PUB-03` | Daily quota tracker at 9,200 units (1,600 units would exceed 10,000) | Publishing paused; task queued for 00:00 PST reset. |
| `PUB-04` | Analytics scheduler queries past 30 days hourly view counts | Optimal hour identified; publication scheduled at peak window. |
| `PUB-05` | Insufficient analytics data available | Defaults publication to 15:00 UTC. |

### 3.6 Subsystem 6: Web Dashboard & Telegram Bot

| Test ID | Test Scenario | Expected Outcome |
| :--- | :--- | :--- |
| `UI-01` | User visits `/` dashboard | Renders dark-mode HTML with queue volume and quota gauge. |
| `UI-02` | Staged video card approval via HTMX (`POST /api/queue/{id}/approve`) | Returns updated HTML card fragment in approved state. |
| `UI-03` | Real-time SSE endpoint (`/api/events/stream`) | Emits task status and upload percentage progress events. |
| `BOT-01` | Telegram `/queue` command | Returns formatted queue summary message with inline buttons. |
| `BOT-02` | Telegram link submission | Validates URL, creates task, dispatches immediate acknowledgment. |
| `BOT-03` | Telegram duplicate suspect alert | Dispatches warning card with similarity breakdown and override buttons. |

---

## 4. Local Docker Testing Strategy

When running services locally inside Docker:

### 4.1 Prerequisites Verification
- Verify Docker daemon is responsive (`docker compose version`).
- Validate `.env` file configuration against `.env.example`.

### 4.2 Step-by-Step Container Validation
```powershell
# 1. Build and start containers
docker compose up -d --build

# 2. Check health of all services
docker compose ps

# 3. Test Redis connectivity
docker compose exec redis redis-cli ping
# Expected: PONG

# 4. Test Web API healthcheck
docker compose exec web curl -s http://localhost:8000/api/health
# Expected: {"status": "ok", "database": "connected", "redis": "connected"}

# 5. Test Ollama connectivity
docker compose exec ollama ollama list
# Expected: Displays qwen2.5:3b model

# 6. Test Celery worker status
docker compose exec celery_worker celery -A app.core.celery_app inspect ping
# Expected: {"celery@worker": {"ok": "pong"}}
```

---

## 5. Automated Test Execution Commands

```powershell
# Run the entire test suite with coverage report
pytest --cov=app --cov-report=term-missing --cov-report=html tests/

# Run unit tests only (fast execution, no I/O)
pytest tests/unit -v

# Run integration tests (with simulated services)
pytest tests/integration -v

# Run with fail-fast flag
pytest -x tests/
```

## 6. Definition of Done (DoD) & Acceptance Criteria

A feature or subsystem is considered complete when:
1. 100% of corresponding unit tests pass.
2. Network failure, rate limiting, and fallback scenarios are explicitly verified.
3. Code strictly adheres to typed Python 3.11+ with Pydantic schemas.
4. Memory usage remains well within the 4 OCPU / 24 GB RAM ceiling.
5. SQLite write operations utilize WAL mode without locking errors under concurrency.


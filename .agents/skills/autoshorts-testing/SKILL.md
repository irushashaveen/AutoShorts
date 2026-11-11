---
name: autoshorts-testing
description: >-
  Use this skill to execute unit tests, integration tests, mock external APIs (TikTok, YouTube, Gemini, Ollama), run test suites with Pytest, and validate AutoShorts services in local Docker containers.
---

# AutoShorts Testing & Validation Skill

This skill provides testing procedures, fixture guidelines, and automated validation steps for the AutoShorts project.

## 1. Test Suite Categories

| Category | Target Scope | Key Tools / Fixtures |
| :--- | :--- | :--- |
| **Unit Tests** | URL parsing, TF-IDF calculation, Levenshtein distance, regex bio matching, JSON schema validation | `pytest`, `unittest.mock` |
| **Pipeline Extraction Tests** | `yt-dlp` mocking, TikWM fallback handling, FFmpeg aspect ratio checks | `respx`, `pytest-asyncio` |
| **Deduplication Tests** | Chromaprint hashing, bit distance, composite $R_{dup}$ scoring | Synthetic audio samples, known test hashes |
| **AI Fallback Tests** | Gemini 1.5 Flash mock response, 429 rate limit trigger, Ollama fallback switch | `httpx.MockTransport`, `respx` |
| **YouTube Publisher Tests** | 5MB resumable chunk stream mock, quota tracking, exponential backoff | Google API Client mocks |
| **Container & Docker Tests** | Service healthchecks, Redis ping, SQLite WAL lock concurrency | `docker compose`, `curl` |

---

## 2. Test Execution Commands

### Local Pytest Execution
```powershell
# Run all unit tests
pytest tests/unit -v

# Run with code coverage
pytest --cov=app --cov-report=term-missing tests/

# Run specific subsystem test
pytest tests/unit/test_deduplication.py -v
pytest tests/unit/test_extraction.py -v
pytest tests/unit/test_metadata_ai.py -v
```

### Docker Integration Testing
```powershell
# Verify service health within docker
docker compose ps
docker compose exec web curl -f http://localhost:8000/api/health
docker compose exec redis redis-cli ping
```

---

## 3. Mocking Conventions & Fixtures

1. **Network Isolation**: Never make real network calls to YouTube Data API or TikTok CDN in unit tests. Always mock through `respx` or `unittest.mock.patch`.
2. **Audio Fingerprints**: Store fixture audio files under `tests/fixtures/audio/` (5-10 second short samples).
3. **Database Isolation**: Unit and integration tests must run against an in-memory SQLite database or a temporary test database file with WAL mode enabled (`sqlite:///:memory:`).


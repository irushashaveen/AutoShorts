# AutoShorts: Database Schema & State Machine Specification

## 1. Storage Engine Architecture

The persistence layer runs on **SQLite 3** operating in **Write-Ahead Logging (WAL)** mode. WAL mode enables concurrent read transactions while write operations execute, eliminating `database is locked` errors under concurrent FastAPI and Celery worker workloads.

### WAL Mode Engine Configuration
Every database connection executes the following PRAGMAs upon initialization:
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;
PRAGMA cache_size = -64000; -- 64MB cache
```

---

## 2. Entity-Relationship Diagram

```mermaid
erDiagram
    TASK ||--o{ AUDIO_FINGERPRINT : has
    TASK ||--o{ TASK_LOG : generates
    TASK }|--|| CREATOR : belongs_to
    YOUTUBE_QUOTA_LOG }|..|| TASK : consumes
    ANALYTICS_CACHE

    TASK {
        string id PK "UUID4"
        string source_url
        string normalized_url
        string status "State enum"
        string tiktok_video_id
        string creator_id FK
        string raw_caption
        string media_path
        string thumbnail_path
        float duration
        int width
        int height
        float duplicate_risk_score
        string ai_title
        string ai_description
        string ai_tags "JSON array"
        string youtube_video_id
        datetime scheduled_publish_at
        datetime published_at
        datetime created_at
        datetime updated_at
    }

    CREATOR {
        string id PK "TikTok Unique ID"
        string nickname
        string bio
        string youtube_handle
        string youtube_channel_id
        boolean has_verified_yt_channel
        datetime created_at
    }

    AUDIO_FINGERPRINT {
        string id PK "UUID4"
        string task_id FK
        string fingerprint_hash "Chromaprint perceptual hash"
        datetime created_at
    }

    YOUTUBE_QUOTA_LOG {
        int id PK
        string task_id FK
        string endpoint_called
        int quota_units "e.g. 1600 for upload"
        datetime created_at
    }

    ANALYTICS_CACHE {
        int id PK
        int peak_hour_utc "0-23"
        float avg_view_duration
        int total_views_30d
        datetime calculated_at
    }

    TASK_LOG {
        int id PK
        string task_id FK
        string level "INFO, WARNING, ERROR"
        string stage "EXTRACTION, VERIFICATION, AI, UPLOAD"
        string message
        datetime created_at
    }
```

---

## 3. Task State Machine Transitions

```mermaid
stateDiagram-v2
    [*] --> QUEUED : Link Submitted
    QUEUED --> EXTRACTING : Worker picks task
    EXTRACTING --> EXTRACTED : Media & Bio Saved
    EXTRACTING --> FAILED_EXTRACTION : Both yt-dlp & TikWM fail

    EXTRACTED --> VERIFYING : Fingerprint & Bio Check
    VERIFYING --> FLAGGED_CREATOR_CHANNEL : Official YT Channel Found
    VERIFYING --> DUPLICATE_SUSPECT : R_dup > 0.75
    VERIFYING --> OPTIMIZING : Verification Clean (R_dup <= 0.75)

    FLAGGED_CREATOR_CHANNEL --> OPTIMIZING : Human Manual Override
    FLAGGED_CREATOR_CHANNEL --> REJECTED : Operator Rejects
    DUPLICATE_SUSPECT --> OPTIMIZING : Human Force Upload
    DUPLICATE_SUSPECT --> REJECTED : Operator Discards

    OPTIMIZING --> READY_FOR_REVIEW : AI Metadata Generated
    OPTIMIZING --> FAILED_OPTIMIZATION : Both Gemini & Ollama fail

    READY_FOR_REVIEW --> SCHEDULED : Operator / Auto Approval
    READY_FOR_REVIEW --> REJECTED : Operator Rejection

    SCHEDULED --> UPLOADING : Optimal Hour Triggered
    UPLOADING --> PUBLISHED : Resumable Upload Success
    UPLOADING --> FAILED_UPLOAD : Quota Exceeded / Error
    UPLOADING --> PAUSED_QUOTA : Daily Quota Ceiling Reached

    PUBLISHED --> [*]
    REJECTED --> [*]
```

---

## 4. SQL Table Definitions

### 4.1 `tasks` Table
```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    tiktok_video_id TEXT,
    creator_id TEXT,
    raw_caption TEXT,
    media_path TEXT,
    thumbnail_path TEXT,
    duration REAL,
    width INTEGER,
    height INTEGER,
    duplicate_risk_score REAL DEFAULT 0.0,
    ai_title TEXT,
    ai_description TEXT,
    ai_tags TEXT, -- JSON array of strings
    youtube_video_id TEXT,
    scheduled_publish_at TIMESTAMP,
    published_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_id) REFERENCES creators(id)
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_scheduled ON tasks(scheduled_publish_at);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
```

### 4.2 `creators` Table
```sql
CREATE TABLE creators (
    id TEXT PRIMARY KEY, -- tiktok unique_id
    nickname TEXT,
    bio TEXT,
    youtube_handle TEXT,
    youtube_channel_id TEXT,
    has_verified_yt_channel BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_creators_yt_handle ON creators(youtube_handle);
```

### 4.3 `audio_fingerprints` Table
```sql
CREATE TABLE audio_fingerprints (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    fingerprint_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX idx_fingerprints_task_id ON audio_fingerprints(task_id);
```

### 4.4 `youtube_quota_log` Table
```sql
CREATE TABLE youtube_quota_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    endpoint_called TEXT NOT NULL,
    quota_units INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX idx_quota_created_at ON youtube_quota_log(created_at);
```

### 4.5 `analytics_cache` Table
```sql
CREATE TABLE analytics_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    peak_hour_utc INTEGER NOT NULL DEFAULT 15,
    avg_view_duration REAL DEFAULT 0.0,
    total_views_30d INTEGER DEFAULT 0,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.6 `task_logs` Table
```sql
CREATE TABLE task_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'INFO',
    stage TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX idx_task_logs_task_id ON task_logs(task_id);
```


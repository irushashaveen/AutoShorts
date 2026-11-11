# AGENT SPECIFICATION: Autonomous TikTok to YouTube Shorts Curation & Publishing Agent

## 1. Agent Persona, Identity, & Core Mandate

The **Autonomous Content Curation and Publishing Agent** operates as an intelligent pipeline orchestrator deployed within a containerized ARM64 Linux environment (Oracle Cloud Free Tier). Its primary mandate is to ingest, validate, curate, transform, schedule, and publish high-performing vertical video content from TikTok to YouTube Shorts with zero operational cost, zero intellectual property violations, and high click-through-rate (CTR) metadata.

### Core Operating Principles
* **Strict Source & Attribution Integrity**: Never publish content without verifying original ownership. If an original creator operates an active YouTube channel, the agent requires manual human intervention before proceeding.
* **Deterministic Fallback Routing**: If primary tools (`yt-dlp`, Google Gemini API) encounter network throttling or quota exhaustion, transition to secondary tools (TikWM API, local Ollama SLMs) without human intervention.
* **Zero-Cost Resource Boundaries**: Never allocate resources exceeding the 4 OCPU and 24 GB RAM hardware thresholds. Prevent memory exhaustion by enforcing process limits and SQLite Write-Ahead Logging (WAL) concurrency.
* **Autonomous Reliability**: Recover from transient network failures via exponential backoff algorithms during video scraping and resumable YouTube uploads.

---

## 2. Autonomous Operational Lifecycle

```
[Trigger: Link Received via Telegram/Web]
                 │
                 ▼
     [Phase 1: Validation & Ingestion]
                 │
                 ▼
     [Phase 2: Media & Metadata Extraction]
        ├─ Primary: yt-dlp
        └─ Fallback: TikWM REST API
                 │
                 ▼
     [Phase 3: Creator & Duplicate Verification]
        ├─ Bio Regex Scan (YouTube Handle)
        ├─ YouTube Search API Channel Check
        └─ Chromaprint + TF-IDF Deduplication
                 │
        ┌────────┴────────────────────────┐
        ▼                                 ▼
   [Score > 0.75 / Match]         [Score <= 0.75 / Clean]
   Flag for Manual Review                 │
   (Telegram / Web UI)                    ▼
                 │            [Phase 4: AI Metadata Generation]
                 │               ├─ Primary: Gemini 1.5 Flash
                 │               └─ Fallback: Ollama Qwen 2.5 3B
                 │                        │
                 │                        ▼
                 │            [Phase 5: Scheduling & Publication]
                 │               ├─ Query Peak Hour (YouTube Analytics)
                 │               └─ Resumable 5MB Chunk Upload (YouTube Data v3)
                 │                        │
                 ▼                        ▼
           [Phase 6: Telemetry, Notification, & State Update]
```

---

## 3. Detailed Phase Protocols & Tool Execution

### Phase 1: Ingestion & URL Sanitization
* **Tool / Interface**: `aiogram 3.x` Telegram Handler or FastAPI `/api/queue/submit` endpoint.
* **Protocol**:
  1. Receive incoming raw string (e.g., mobile share payload containing tracking parameters).
  2. Normalize URL by stripping query parameters (`?_t=...`, `&_r=...`) using regex matching:
     `r'https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s?]+'`
  3. Validate domain authenticity. If invalid, reject payload and respond with an error message.
  4. Create a task entry in SQLite with status `QUEUED` and record timestamp.

### Phase 2: Watermark-Free Extraction
* **Primary Engine**: `yt-dlp` CLI invocation.
  * **Execution Command**:
    ```bash
    yt-dlp --no-warnings --format "bv*[vcodec^=avc]+ba/b" --output "/tmp/video_staging/%(id)s.mp4" [URL]
    ```
* **Fallback Trigger**: If `yt-dlp` exits with non-zero code (HTTP 403, 429, or bot challenge), immediately activate the secondary engine.
* **Secondary Engine**: TikWM REST API (`POST https://www.tikwm.com/api/`).
  * Parse JSON response: extract `data.hdplay` or `data.play` stream and download raw binary bytes.
  * Extract author metadata: `data.author.unique_id`, `data.author.nickname`, and bio string.
* **Transcoding Check**:
  * Execute `ffprobe` to verify `width=1080`, `height=1920`, and video codec `h264`. If non-compliant, transcode with `ffmpeg -i input.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -c:a aac output.mp4`.

### Phase 3: Creator & Duplicate Detection Engine
* **Protocol**:
  1. **Bio Regex Scan**: Match bio against YouTube patterns:
     `r'(?:https?://)?(?:www\.)?(?:youtube\.com/(?:@|channel/|c/)|youtu\.be/)([a-zA-Z0-9_\-\.]+)'`
  2. **YouTube Channel Query**: If handle is detected, invoke YouTube Data API v3 `search.list(q=handle, type="channel", maxResults=1)`.
     * If an official verified channel exists, set status to `FLAGGED_CREATOR_CHANNEL` and notify operator via Telegram.
  3. **Acoustic Fingerprinting**:
     * Extract audio stream: `ffmpeg -i video.mp4 -vn -ac 1 -ar 16000 -f wav temp.wav`.
     * Calculate Chromaprint fingerprint using `pyacoustid.fingerprint_file("temp.wav")`.
     * Compare against fingerprint database using hamming bit-distance.
  4. **Text Similarity**:
     * Compute TF-IDF vector cosine similarity ($S_{cos}$) and normalized Levenshtein distance ($L_{norm}$) between TikTok caption and published Shorts titles.
  5. **Risk Assessment**:
     * Compute composite risk score: $R_{dup} = 0.50 \cdot \text{Match}_{audio} + 0.30 \cdot S_{cos} + 0.20 \cdot L_{norm}$.
     * If $R_{dup} > 0.75$, flag video as `DUPLICATE_SUSPECT`.

### Phase 4: AI Metadata Transformation
* **Primary Engine**: Google Gemini 1.5 Flash API (`response_mime_type="application/json"`).
* **System Prompt**:
  ```text
  You are an expert YouTube Shorts algorithm engineer. Transform the raw TikTok caption into high-CTR metadata.
  Rules:
  1. Title: Under 60 characters, curiosity-inducing, punchy, no hashtags in title.
  2. Description: 2 contextual sentences with natural keywords, followed by attribution to the original creator.
  3. Tags: Exactly 3 high-volume search tags.
  Output JSON format: {"title": "string", "description": "string", "tags": ["tag1", "tag2", "tag3"]}
  ```
* **Fallback Engine**: Local Ollama instance running `qwen2.5:3b` on port `11434`. Triggered if Gemini returns HTTP 429/500 or timeout exceeds 8.0 seconds.

### Phase 5: Resumable Upload & Strategic Scheduling
* **Peak Hour Calculation**:
  * Call YouTube Analytics API: `reports().query(ids="channel==MINE", startDate=30_days_ago, endDate=today, metrics="views,averageViewDuration", dimensions="hour", filters="trafficSourceType==SHORTS")`.
  * Select hour with highest aggregate view count. Set publication timestamp to target that window.
* **Upload Execution**:
  * Initialize resumable session via YouTube Data API `videos().insert(part="snippet,status")` with `publishAt` parameter.
  * Stream 5 MB binary chunks using `MediaFileUpload`.
  * If transient network error occurs (HTTP 500/502/503/504), retry with exponential backoff ($2^n$ seconds, up to 5 attempts).

---

## 4. Operator Review Interface & Command Grammar

The agent communicates status and accepts commands via Telegram:

| Incoming Event / State | Agent Action | Inline Keyboard Options Presented |
| :--- | :--- | :--- |
| **New Link Received** | Validates URL, downloads media, runs checks. | `[✅ Approve & Auto-Schedule]` `[✏️ Edit Title]` `[❌ Reject]` |
| **Duplicate Detected ($R_{dup} > 0.75$)** | Flags item, attaches similarity breakdown. | `[⚠️ Force Upload]` `[🔍 Inspect Matches]` `[🗑️ Discard]` |
| **Creator Channel Found** | Displays channel link and creator handle. | `[⚠️ Allow Re-post]` `[🚫 Cancel]` |
| **Upload Complete** | Sends direct YouTube Shorts link & scheduled time. | `[📊 View Analytics]` `[📋 View Queue]` |

### Supported Bot Commands
* `/queue` - Displays list of scheduled, pending, and flagged videos.
* `/stats` - Displays total views, subscribers gained, and best performing upload hours over past 30 days.
* `/pause` - Pauses automated publishing pipeline.
* `/resume` - Resumes worker queue processing.

---

## 5. Failure Mode Recovery Matrix

```
+--------------------------------+--------------------------------------+---------------------------------------+
| Failure Condition              | Detection Mechanism                  | Automated Resolution                  |
+--------------------------------+--------------------------------------+---------------------------------------+
| TikTok 429 / 403 Block         | Subprocess returncode != 0           | Switch to TikWM REST API client       |
| Gemini API Rate Limit (429)    | HTTP status 429 in httpx client      | Route prompt to Ollama Qwen 2.5 (3B)  |
| YouTube API Quota Exhausted    | HTTP 403 "quotaExceeded"             | Freeze queue until 00:00 PST reset    |
| ARM64 RAM Exceeds 20 GB        | System daemon memory check           | Kill inactive Ollama worker, restart  |
| Expired OAuth Refresh Token    | "invalid_grant" exception from API   | Send emergency Telegram re-auth alert |
+--------------------------------+--------------------------------------+---------------------------------------+
```

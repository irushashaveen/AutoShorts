# Automated TikTok to YouTube Shorts Curation Architecture: Technical Specification

The automated content curation and cross-publishing pipeline is an enterprise-grade, zero-cost media distribution system engineered specifically for deployment on an Oracle Cloud Free Tier ARM Ampere A1 compute instance operating with 4 OCPUs, 24 GB of RAM, and native ARM64 architecture. The system automates the ingestion, extraction, cross-platform copyright verification, metadata transformation, scheduling, and distribution of short-form media while operating strictly within zero-cost resource bounds.

## 1. System Overview & Core Objectives

The architecture resolves three operational challenges inherent to short-form video repurposing: manual operational friction, platform anti-scraping countermeasures, and platform copyright or reused-content enforcement.

* **Elimination of Ingestion Friction**: Rather than requiring manual video downloads and re-uploads via desktop interfaces, operators can curate content directly from mobile devices or tablets while browsing TikTok by dispatching links directly to an asynchronous Telegram bot, with secondary oversight handled by a lightweight web control dashboard.
* **Reliable Watermark-Free Extraction**: Short-form vertical video distribution on YouTube Shorts demands clean 1080x1920 MP4 streams without platform watermarks. The pipeline implements a primary-secondary fallback mechanism that combines local scraping with remote REST decoding to ensure resilience against platform changes and datacenter IP blocks.
* **Cross-Platform Rights and Deduplication Verification**: Indiscriminate content mirroring creates substantial risks of copyright infringement and reused-content penalties. The architecture introduces automated heuristics that extract creator metadata to identify existing official YouTube channels, alongside perceptual acoustic fingerprinting and text similarity algorithms to prevent uploading content that already exists on the destination platform.
* **Algorithmic Repurposing and Optimized Scheduling**: Raw TikTok captions contain platform-specific hashtags and informal syntax that hinder discoverability on YouTube Shorts. The system utilizes zero-cost generative models to re-engineer titles and descriptions for high click-through rates (CTR) and mobile display constraints, subsequently calculating dynamic upload times based on historical channel retention data.

---

## 2. Core Features & End-to-End Workflow Lifecycle

The workflow operates across six discrete, interconnected pipeline stages coordinated by an asynchronous task queue.

* **Dual Command Ingestion**: Operators submit TikTok video links via an asynchronous Telegram bot built with `aiogram 3.x` or manage tasks via a lightweight FastAPI, HTMX, and Tailwind CSS control dashboard.
* **Resilient Media Extraction**: Extracts 1080x1920 portrait MP4 files stripped of watermarks using local `yt-dlp` binary execution with automatic fallback to the remote TikWM REST API, followed by FFmpeg normalization to standard H.264 video and AAC audio codecs.
* **Creator Rights & Duplicate Verification**: Evaluates TikTok creator biographies using regular expressions to identify official YouTube channel links, while computing Chromaprint acoustic fingerprints (`pyacoustid`) and TF-IDF cosine similarity scores to prevent duplicate uploads.
* **AI-Powered Metadata Optimization**: Converts raw captions and hashtags into high-CTR titles strictly under 60 characters, search-optimized descriptions, and targeted tags using the Google Gemini 1.5 Flash Free API, backed by a local Ollama Qwen 2.5 3B instance.
* **Dynamic Scheduling**: Queries the YouTube Analytics API to evaluate historical viewer retention and engagement by hour, dynamically assigning upload slots during peak audience activity windows.
* **Resumable Publication**: Uploads videos to YouTube Shorts using the YouTube Data API v3 Resumable Upload Protocol in 5 MB chunks, actively managing the 10,000 daily quota limit.

---

## 3. Technology Stack & ARM64 Resource Budgeting

The platform is designed to operate continuously on an Oracle Cloud Always Free compute shape (VM.Standard.A1.Flex) provisioned with 4 OCPUs and 24 GB of RAM. The resource allocation strategy distributes compute and memory across microservices to prevent system exhaustion and ensure zero operating costs.

| Component Name | Primary Technology Stack | Resource Allocation (ARM64) | Operational Role & Mechanics |
| :--- | :--- | :--- | :--- |
| **Ingestion Bot** | `aiogram 3.x` / Python Asyncio | 0.1 OCPU / 128 MB RAM | Captures URLs asynchronously, validates payloads, presents inline interactive controls. |
| **Control Dashboard** | FastAPI / HTMX / Tailwind CSS | 0.2 OCPU / 256 MB RAM | Provides real-time queue visualization, analytics displays, and manual override capabilities. |
| **Task Broker** | Redis 7.x / Celery 5.x | 0.2 OCPU / 256 MB RAM | Coordinates distributed task queues, manages retry intervals, and enforces concurrency limits. |
| **Extraction Engine** | `yt-dlp` / TikWM API / FFmpeg | 1.0 OCPU / 1.5 GB RAM | Extracts watermark-free 1080x1920 MP4 video streams and raw author profile metadata. |
| **Detection Engine** | `pyacoustid` / `scikit-learn` | 0.5 OCPU / 512 MB RAM | Executes Chromaprint perceptual acoustic hashing and TF-IDF vector similarity matching. |
| **AI Inference** | Gemini 1.5 Flash / Ollama Qwen 2.5 | 1.5 OCPU / 2.5 GB RAM | Generates high-CTR metadata via zero-RAM cloud API with local 4-bit SLM fallback. |
| **Publisher Engine** | YouTube Data v3 & Analytics API | 0.2 OCPU / 256 MB RAM | Manages OAuth 2.0 refresh, 5MB chunked resumable uploads, and dynamic schedule logic. |
| **Persistence Layer** | SQLite 3 (WAL Mode) | 0.3 OCPU / Shared Storage | Stores structured task states, OAuth credentials, and acoustic fingerprint hashes. |

---

## 4. Content Verification & Deduplication Heuristics

To ensure ethical content curation and safeguard the channel against YouTube reused-content penalties, the pipeline enforces strict mathematical and programmatic verification rules.

### TikTok Bio Regular Expression Analysis
Upon extracting author metadata, the system executes regular expression matching across the creator's profile biography to isolate candidate YouTube handles:

$$\text{Patterns} = \begin{cases}
\text{\texttt{youtube\.com/@([a-zA-Z0-9_\-\.]{3,30})}} \\
\text{\texttt{youtube\.com/channel/([a-zA-Z0-9_\-]{24})}} \\
\text{\texttt{(?:yt|youtube):\s*@?([a-zA-Z0-9_\-\.]{3,30})}}
\end{cases}$$

When a valid handle pattern is detected, the system queries the YouTube Data API v3 `search.list` endpoint (`q={handle}&type=channel`). If an active, verified channel is identified, the task is automatically reassigned to a flagged review status, notifying the administrator before any media is scheduled.

### Acoustic Fingerprinting & Vector Text Matching
To identify videos that have already been uploaded to YouTube Shorts by third-party channels, the deduplication engine applies a dual-layer acoustic and textual scoring algorithm:

1. **Acoustic Fingerprinting**: FFmpeg isolates audio from the video container, downsampling it to a single-channel 16kHz WAV format. The `pyacoustid` library (interfacing with Chromaprint) analyzes spectral peaks across time to produce a perceptual audio hash string. This hash is compared against the database of processed media, yielding a binary or probabilistic acoustic match factor ($\text{Match}_{audio} \in [0, 1]$).
2. **Text Vector Similarity**: Raw captions and titles are transformed into Term Frequency-Inverse Document Frequency (TF-IDF) sparse vector representations. String proximity is calculated via Cosine Similarity ($S_{cos}$) alongside normalized Levenshtein Edit Distance ($L_{norm}$):

$$S_{cos}(A, B) = \frac{\mathbf{A} \cdot \mathbf{B}}{\|\mathbf{A}\| \|\mathbf{B}\|}$$

$$L_{norm}(T_1, T_2) = 1 - \frac{\text{LevenshteinDistance}(T_1, T_2)}{\max(|T_1|, |T_2|)}$$

3. **Composite Duplication Risk Score ($R_{dup}$)**:
The final duplication coefficient is calculated as a weighted linear combination:

$$R_{dup} = 0.50 \cdot \text{Match}_{audio} + 0.30 \cdot S_{cos} + 0.20 \cdot L_{norm}$$

When $R_{dup} > 0.75$, the pipeline terminates automated execution, logs the item as a probable duplicate, and triggers a Telegram notification to prevent redundant publication.

---

## 5. Subsystem Implementation Architecture

The core operational logic of the pipeline is implemented across four focused subsystems:

### Subsystem 1: Watermark-Free Extraction Engine
The extraction subsystem orchestrates primary video extraction through native CLI invocation of `yt-dlp` and automatically falls back to the TikWM REST API when anti-scraping barriers arise.

* **Primary Pipeline (`yt-dlp`)**: Executes with format selection `--format "bv*[vcodec^=avc]+ba/b"` to retrieve the highest-quality H.264 video and AAC audio stream directly from TikTok CDN servers without visual overlays.
* **Secondary Fallback (TikWM API)**: Sends an asynchronous POST request to the TikWM endpoint with the video URL and HD parameter (`hd=1`). The API returns a parsed JSON payload containing direct media CDN links (`hdplay` or `play`) and author attributes (`unique_id`, `nickname`, `title`, `duration`).
* **Standardization via FFmpeg**: Verifies the video container matches the 9:16 vertical aspect ratio (1080x1920) and transcodes non-standard codecs to ensure compatibility with YouTube Shorts ingestion requirements.

### Subsystem 2: Duplication & Cross-Platform Detector
This module performs regular expression handle extraction from creator bios, converts video audio into Chromaprint hashes, and computes textual similarity matrices.

* **Profile Analysis**: Utilizes compiled regular expressions to parse YouTube handles, custom channel URLs, and shorthand aliases from the TikTok author's bio. If a handle is discovered, the YouTube Data API v3 `search.list` endpoint verifies whether an official verified channel exists.
* **Perceptual Acoustic Fingerprinting**: Isolates the primary audio track, downsampling to 16kHz mono WAV format. Passes the PCM stream to `pyacoustid` (interfacing with Chromaprint) to compute spectral peak hashes across time. Hashes are cross-referenced against the SQLite persistence database.
* **Text Vector Similarity**: Processes raw captions through scikit-learn's `TfidfVectorizer` to produce TF-IDF sparse vectors, calculating Cosine Similarity alongside normalized Levenshtein Edit Distance. If the composite Duplication Risk Score exceeds 0.75, the task is automatically aborted and flagged for manual review.

### Subsystem 3: AI Metadata Transformation Engine
This component transforms unstructured, hashtag-laden TikTok captions into structured JSON metadata optimized for YouTube Shorts, with graceful fallback from cloud to local inference.

* **Optimization Objectives**: Produces high-CTR titles strictly under 60 characters to avoid mobile display truncation, creates a concise 2-sentence description with high-relevance search keywords, and appends three targeted tags while stripping all platform artifacts (`#fyp`, `#foryou`, `#tiktok`, `@usernames`).
* **Primary Cloud Inference**: Calls Google Gemini 1.5 Flash Free Tier API using structured JSON schema output enforcement (`response_mime_type="application/json"`). This operates with zero host RAM overhead and high throughput.
* **Local Fallback Inference**: Automatically routes requests to a local Ollama instance running `qwen2.5:3b` (4-bit quantized `Q4_K_M`) on the ARM64 VPS host if network partitions or cloud API rate limits occur.

### Subsystem 4: YouTube Publisher & Analytics Scheduler
This module manages Google OAuth 2.0 credentials, queries the YouTube Analytics API for channel-specific peak viewership windows, and executes chunked resumable video uploads.

* **Headless OAuth 2.0 Management**: Handles authentication on headless Linux instances via an encrypted SSH tunnel (`ssh -L 8080:127.0.0.1:8080`), capturing the redirect code and storing offline refresh tokens for automated background token renewal.
* **Resumable Chunked Ingestion**: Uploads video payloads via Google's Resumable Upload Protocol in 5 MB (`5242880` bytes) binary chunks with exponential backoff retry logic (retrying HTTP 500, 502, 503, 504 status codes up to 5 times).
* **Dynamic Engagement Scheduling**: Queries the YouTube Analytics API `reports.query` endpoint for metrics `views` and `averageViewDuration` grouped by dimension `hour` and filtered for `trafficSourceType==SHORTS`. Analyzes 30-day historical trends to identify the optimal peak viewership hour, defaulting to 15:00 UTC if insufficient data exists.

---

## 6. Containerized Deployment & High-Availability Operations

The entire pipeline is containerized and orchestrated via Docker Compose on Oracle Linux ARM64, enforcing strict CPU core usage limits, memory boundaries, and restart behaviors.

### Service Architecture & Container Allocation

* **Redis Task Broker (`redis:7-alpine`)**: Configured with a 256 MB memory cap and `allkeys-lru` eviction policy, managing Celery asynchronous worker message queues.
* **Local Ollama Host (`ollama/ollama`)**: Provisioned with a hard memory limit of 3000 MB and 2.0 OCPU allocation, hosting the quantized Qwen 2.5 3B fallback model.
* **FastAPI Backend & HTMX Dashboard**: Operates with Uvicorn workers behind a local port binding, serving dynamic DOM updates with minimal host memory.
* **Celery Task Worker**: Limited to 2000 MB RAM and 1.5 OCPUs with a worker concurrency of 2, executing download, extraction, deduplication, and upload workflows.
* **Telegram Bot (`aiogram`)**: Connects to the Telegram Bot API to process user-shared links asynchronously.

### Fault Tolerance & Recovery Architecture

| Potential Failure Point | System Detection Metric | Preventive & Automated Recovery Architecture |
| :--- | :--- | :--- |
| **TikTok Datacenter IP Block** | HTTP 403 Forbidden / 429 Too Many Requests | Automatically switch request traffic to the secondary TikWM REST API; route `yt-dlp` through residential/rotating proxies with randomized sleep intervals. |
| **YouTube Quota Ceiling Exceeded** | HTTP 403 `quotaExceeded` API response | Intercept tasks in Redis; pause publishing queues until quota resets at 00:00 PST. Cap daily insertions at 4–5 videos. |
| **Host System Memory Exhaustion** | Kernel Out-Of-Memory (OOM) Killer execution | Hard-cap container memory limits via Docker Compose (`memory: 3000M`) and restrict Celery worker concurrency. |
| **Gemini API Outage / Quota Limit** | HTTP 429 / 5xx Server Errors | Fall back to local Ollama inference (`qwen2.5:3b`) running on ARM64. |
| **Invalid OAuth Refresh Credentials** | `invalid_grant` exception from Google OAuth | Send immediate alert via Telegram bot with a direct tunnel URL to re-authenticate. |

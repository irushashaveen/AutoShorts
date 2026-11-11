# DESIGN SPECIFICATION: Web Dashboard & Telegram UI/UX Architecture

## 1. Design System & Brand Identity

The interface design for the TikTok to YouTube Shorts Curation Dashboard and Ingestion System adheres to a high-density, low-latency dark-mode aesthetic. Designed specifically for cross-platform utility across desktop displays and mobile or tablet touchscreens, it maximizes information hierarchy while eliminating client-side JavaScript rendering overhead through FastAPI, HTMX, and Tailwind CSS.

### 1.1 Color Palette Tokens (Tailwind CSS Mappings)
* **Background Canvas**: `bg-slate-950` (`#020617`) - Deep black-blue providing contrast and reducing display power consumption on mobile tablets.
* **Surface Containers and Cards**: `bg-slate-900` (`#0f172a`) with subtle border `border-slate-800` (`#1e293b`).
* **Interactive Elements and Buttons**: `bg-slate-800 hover:bg-slate-700` (`#1e293b` to `#334155`).
* **Primary Accent and Actions**: `bg-indigo-600 hover:bg-indigo-500` (`#4f46e5`) - Used for active filters, upload triggers, and primary confirmation buttons.
* **Success and Approved State**: `text-emerald-400 bg-emerald-950/40 border-emerald-800` (`#34d399`).
* **Warning and Flagged Duplicate**: `text-amber-400 bg-amber-950/40 border-amber-800` (`#fbbf24`).
* **Danger and Rejection State**: `text-rose-400 bg-rose-950/40 border-rose-800` (`#f87171`).
* **Typography Stack**: Clean sans-serif system font stack (`Inter`, `system-ui`, `-apple-system`).

---

## 2. Information Architecture & Navigation

The application layout is structured around two synchronized control interfaces: a real-time web workspace and a mobile-first Telegram bot.

### 2.1 Navigation Layout
* **Top Navigation Bar**: Brand identity indicator, live YouTube API quota monitor, worker status indicators, and direct navigation links (Queue, Analytics, Settings).
* **Metrics Overview Bar**: High-level statistical cards providing immediate situational awareness.
* **Main Operational Workspace**: A two-column responsive grid dividing the live video staging queue from the dynamic scheduling timeline.

---

## 3. Web Dashboard Components

### 3.1 Header & System Health Bar
The top header provides operators with immediate insight into quota constraints and background worker health:
* **YouTube Data API Quota Gauge**: Tracks daily quota consumption against the 10,000 units limit (each video upload consumes 1,600 units).
* **Background Worker Heartbeat**: Live pulse indicator displaying Redis queue depth and Celery concurrency state.
* **Summary Metric Cards**:
  * **Queue Volume**: Active media count segmented by pending, approved, and flagged states.
  * **Shorts Published**: Cumulative successful uploads within the past 30-day window.
  * **Average View Duration (AVD)**: Sourced from YouTube Analytics API to evaluate audience retention.
  * **Peak Engagement Window**: Sourced dynamically from historical traffic metrics.

### 3.2 Staged Video Card Component
Each video item in the processing queue is rendered as an interactive card containing:
1. **Vertical Thumbnail Preview**: Rendered in 9:16 aspect ratio with original media duration overlay.
2. **Creator Attribution Header**: Original TikTok username, nickname, and account verification status.
3. **AI Metadata Preview**: Generated title (constrained to under 60 characters for mobile display), SEO description, and search tags.
4. **Duplication Risk Meter**: Visual score combining Chromaprint acoustic matching and caption TF-IDF similarity.
5. **Interactive Controls**:
   * **Approve and Schedule**: Submits an asynchronous request (`hx-post`) updating the queue state.
   * **Inline Metadata Editor**: Allows instant modification of titles and descriptions directly within the DOM.
   * **Regenerate AI**: Requests a new metadata completion from Google Gemini 1.5 Flash (or local Ollama fallback).
   * **Discard**: Clears the media container and updates database state.

---

## 4. Mobile & Tablet Touch Experience

Because content curation frequently occurs while reviewing media on mobile phones or tablets:
* **Touch Targets**: All interactive elements are configured with minimum dimensions of 48px by 48px.
* **Tablet Landscape View**: When accessed via tablet browsers in landscape orientation, the layout transitions to a two-column split view displaying the media player on the left and metadata controls on the right.
* **Low-Bandwidth Operation**: HTMX server-rendered partials eliminate heavy client-side JavaScript bundles, ensuring responsive interactions even over cellular data connections.

---

## 5. Telegram Bot Interface & Interaction Flow

The Telegram Bot serves as the primary intake mechanism for rapid mobile submissions:

### 5.1 Sharing Sequence
1. **User Submission**: The operator shares a TikTok video link directly from the mobile app to the Telegram bot.
2. **Immediate Acknowledgment**: The bot verifies URL syntax, initiates background extraction, and confirms task creation.
3. **Interactive Review Card**: Upon completing watermark-free extraction and duplicate checks, the bot delivers an inline message card containing:
   * Processed video title and creator details.
   * Duplicate risk rating and channel match verification.
   * Proposed YouTube Shorts title and peak engagement publishing slot.
   * Inline action buttons: Approve, Edit Title, Regenerate, or Reject.
4. **Alert Notifications**: If an existing official YouTube channel is identified in the creator's biography, the bot dispatches an alert requiring manual confirmation before publication.

---

## 6. Real-Time Telemetry & SSE Architecture

The Web Dashboard integrates Server-Sent Events (SSE) via the `/api/events/stream` endpoint to support real-time state synchronization without full-page reloads:
* **Upload Chunk Progress**: Streams real-time byte percentages during 5MB resumable chunk uploads.
* **Local Inference Resource Monitoring**: Visualizes CPU and RAM consumption when Ollama SLMs are active.
* **Queue Updates**: Automatically inserts newly scraped videos into the browser view when links are shared via Telegram.

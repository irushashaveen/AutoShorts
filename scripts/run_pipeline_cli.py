#!/usr/bin/env python3
"""
AutoShorts CLI Pipeline Runner
Allows executing and inspecting the 6-phase pipeline directly from the command line.
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.database import SessionLocal
from app.models import Task, Creator, TaskStatus
from app.services.extraction import URLSanitizer, MediaExtractor, TikWMClient, YtDlpExtractor
from app.services.verification import VerificationPipeline
from app.services.ai import MetadataEngine, GeminiClient, OllamaClient
from app.services.youtube import AnalyticsScheduler, QuotaTracker


def setup_logger(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")


def main():
    parser = argparse.ArgumentParser(description="AutoShorts CLI Pipeline Execution & Debugger")
    parser.add_argument("--url", required=True, help="TikTok video link or mobile share link")
    parser.add_argument("--dry-run", action="store_true", help="Run extraction, deduplication, and AI without publishing")
    parser.add_argument("--force-tikwm", action="store_true", help="Force TikWM fallback extraction")
    parser.add_argument("--force-ollama", action="store_true", help="Force local Ollama SLM metadata generation")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logs")

    args = parser.parse_args()
    setup_logger(args.verbose)

    print("\n" + "=" * 65)
    print("⚡ AutoShorts Pipeline Runner")
    print("=" * 65)

    # 1. URL Sanitization
    print(f"\n[Phase 1] Sanitizing URL: {args.url}")
    clean_url = URLSanitizer.normalize_url(args.url)
    print(f"  ➔ Canonical URL: {clean_url}")

    # 2. Media Extraction
    print(f"\n[Phase 2] Media Extraction (Staging: {settings.MEDIA_STAGING_DIR})")
    extractor = MediaExtractor()
    if args.force_tikwm:
        print("  [!] Forcing TikWM REST API client...")
        extraction_res = extractor.tikwm.extract(clean_url, settings.MEDIA_STAGING_DIR)
        # Normalize
        normalized_video = extractor.normalizer.normalize_video(extraction_res.video_path)
        extraction_res.video_path = normalized_video
        extraction_res.audio_path = extractor.normalizer.extract_audio_wav(normalized_video)
    else:
        extraction_res = extractor.extract_media(clean_url, settings.MEDIA_STAGING_DIR)

    print(f"  ➔ Video ID: {extraction_res.video_id}")
    print(f"  ➔ Creator: @{extraction_res.creator_id} ({extraction_res.creator_nickname})")
    print(f"  ➔ Duration: {extraction_res.duration:.1f}s | Resolution: {extraction_res.width}x{extraction_res.height}")
    print(f"  ➔ Engine Used: {extraction_res.engine_used}")
    print(f"  ➔ Media Path: {extraction_res.video_path}")

    # 3. Verification & Deduplication
    print(f"\n[Phase 3] Creator Rights & Deduplication Heuristics")
    db = SessionLocal()
    try:
        verifier = VerificationPipeline()
        audio_path = Path(extraction_res.audio_path) if extraction_res.audio_path else None
        ver_res = verifier.run_verification(
            creator_bio=extraction_res.creator_bio,
            candidate_caption=extraction_res.caption,
            audio_wav_path=audio_path,
            db=db
        )

        print(f"  ➔ Creator YouTube Channel Found: {ver_res.has_verified_yt_channel} ({ver_res.youtube_handle})")
        print(f"  ➔ Acoustic Match Score: {ver_res.audio_match_score:.2f}")
        print(f"  ➔ Caption Cosine Similarity: {ver_res.text_cosine_score:.2f}")
        print(f"  ➔ Composite Risk Score (R_dup): {ver_res.duplicate_risk_score:.2f}")
        print(f"  ➔ Recommended Pipeline State: {ver_res.recommended_status.value}")

        if ver_res.is_duplicate_suspect and not args.dry_run:
            print("\n  [!] FLAGGED AS DUPLICATE SUSPECT. Pipeline halted for safety.")
            return

        # 4. AI Metadata Optimization
        print(f"\n[Phase 4] AI Metadata Optimization")
        engine = MetadataEngine()
        if args.force_ollama:
            print("  [!] Forcing local Ollama SLM inference...")
            ai_meta = engine.ollama.generate_metadata(
                caption=extraction_res.caption,
                creator_username=extraction_res.creator_id,
                creator_nickname=extraction_res.creator_nickname,
                duration=extraction_res.duration
            )
            ai_engine = "ollama-qwen2.5:3b"
        else:
            ai_meta, ai_engine = engine.generate(
                caption=extraction_res.caption,
                creator_username=extraction_res.creator_id,
                creator_nickname=extraction_res.creator_nickname,
                duration=extraction_res.duration
            )

        print(f"  ➔ AI Engine: {ai_engine}")
        print(f"  ➔ YouTube Title: \"{ai_meta.title}\" ({len(ai_meta.title)} chars)")
        print(f"  ➔ SEO Description:\n{ai_meta.description}")
        print(f"  ➔ Tags: {ai_meta.tags}")

        # 5. Scheduling & Quota
        print(f"\n[Phase 5] Engagement Scheduling & Quota Verification")
        quota_used = QuotaTracker.get_today_consumption(db)
        can_upload = QuotaTracker.can_upload(db)
        peak_hour, _, _ = AnalyticsScheduler.query_peak_engagement_hour(None, db=db)
        scheduled_time = AnalyticsScheduler.calculate_publish_timestamp(peak_hour)

        print(f"  ➔ Daily Quota Status: {quota_used} / 10,000 units (Upload Allowed: {can_upload})")
        print(f"  ➔ Peak Audience Window: {peak_hour}:00 UTC")
        print(f"  ➔ Calculated Publish Slot: {scheduled_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        if args.dry_run:
            print("\n" + "=" * 65)
            print("DRY-RUN COMPLETE: Video validated and metadata generated successfully.")
            print("=" * 65 + "\n")
            return

    finally:
        db.close()


if __name__ == "__main__":
    main()


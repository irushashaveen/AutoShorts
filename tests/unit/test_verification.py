import pytest
from unittest.mock import MagicMock
from app.models import Task, Creator, AudioFingerprint, TaskStatus
from app.services.verification import (
    BioScanner,
    TextSimilarity,
    AcousticHasher,
    RiskEvaluator,
    VerificationPipeline,
    compute_levenshtein_distance,
    compute_normalized_levenshtein,
)


def test_bio_scanner_patterns():
    # Standard handle
    bio1 = "Follow my official YT: https://www.youtube.com/@creative_guru"
    handle, verified = BioScanner.scan_creator(bio1)
    assert handle == "@creative_guru"
    assert verified is True

    # Channel ID
    bio2 = "Sub to youtube.com/channel/UC1234567890123456789012 for more"
    handle2, verified2 = BioScanner.scan_creator(bio2)
    assert handle2 == "UC1234567890123456789012"
    assert verified2 is True

    # Shorthand
    bio3 = "Business inquiries: email@example.com | yt: @tech_insider"
    handle3, verified3 = BioScanner.scan_creator(bio3)
    assert handle3 == "@tech_insider"
    assert verified3 is True

    # No YouTube mention
    bio4 = "Just a dancer living life in NYC"
    handle4, verified4 = BioScanner.scan_creator(bio4)
    assert handle4 is None
    assert verified4 is False


def test_levenshtein_similarity():
    # Exact match
    assert compute_normalized_levenshtein("Hello World", "Hello World") == 1.0

    # Minor typo
    sim = compute_normalized_levenshtein("How to code fast", "How to code fest")
    assert sim > 0.90

    # Completely different
    sim_diff = compute_normalized_levenshtein("Python programming tutorial", "Cooking delicious pasta")
    assert sim_diff < 0.25


def test_tfidf_cosine_similarity():
    text1 = "Top 5 AI tools that will blow your mind in 2026"
    text2 = "Top 5 AI tools that will blow your mind"
    sim = TextSimilarity.compute_tfidf_cosine(text1, text2)
    assert sim >= 0.75

    text3 = "How to bake sourdough bread step by step"
    sim_unrelated = TextSimilarity.compute_tfidf_cosine(text1, text3)
    assert sim_unrelated == 0.0


def test_acoustic_hasher_comparison():
    # Identical hashes
    fp1 = "AQAAZEqUJUmSZEkSZk-WHE8e_BwePEceZEkSZk-WHE8e_BwePEce"
    assert AcousticHasher.compare_fingerprints(fp1, fp1) == 1.0

    # Empty comparison
    assert AcousticHasher.compare_fingerprints("", fp1) == 0.0


def test_risk_evaluator_composite_score():
    evaluator = RiskEvaluator(
        weight_audio=0.50,
        weight_tfidf=0.30,
        weight_levenshtein=0.20,
        risk_threshold=0.75
    )

    # 1. High risk duplicate
    res_dup = evaluator.evaluate(
        youtube_handle=None,
        has_verified_yt_channel=False,
        audio_match=1.0,
        tfidf_cosine=0.90,
        levenshtein_norm=0.90
    )
    # Expected: 0.5(1.0) + 0.3(0.9) + 0.2(0.9) = 0.50 + 0.27 + 0.18 = 0.95
    assert res_dup.duplicate_risk_score == 0.95
    assert res_dup.is_duplicate_suspect is True
    assert res_dup.recommended_status == TaskStatus.DUPLICATE_SUSPECT

    # 2. Clean novel video
    res_clean = evaluator.evaluate(
        youtube_handle=None,
        has_verified_yt_channel=False,
        audio_match=0.0,
        tfidf_cosine=0.10,
        levenshtein_norm=0.10
    )
    # Expected: 0.5(0) + 0.3(0.1) + 0.2(0.1) = 0.05
    assert res_clean.duplicate_risk_score == 0.05
    assert res_clean.is_duplicate_suspect is False
    assert res_clean.recommended_status == TaskStatus.OPTIMIZING

    # 3. Flagged creator channel (overrides duplicate status for safety)
    res_creator = evaluator.evaluate(
        youtube_handle="@official_creator",
        has_verified_yt_channel=True,
        audio_match=0.0,
        tfidf_cosine=0.0,
        levenshtein_norm=0.0
    )
    assert res_creator.recommended_status == TaskStatus.FLAGGED_CREATOR_CHANNEL


def test_verification_pipeline_integration(db_session):
    # Setup database with existing video & fingerprint
    existing_task = Task(
        source_url="https://www.tiktok.com/@old/video/1",
        normalized_url="https://www.tiktok.com/@old/video/1",
        raw_caption="Incredible magic card trick revealed",
        status=TaskStatus.PUBLISHED
    )
    db_session.add(existing_task)
    db_session.commit()

    fp = AudioFingerprint(
        task_id=existing_task.id,
        fingerprint_hash="AQAAZEqUJUmSZEkS"
    )
    db_session.add(fp)
    db_session.commit()

    pipeline = VerificationPipeline()

    # Candidate with near-identical caption
    res = pipeline.run_verification(
        creator_bio="Dancer & creator",
        candidate_caption="Incredible magic card trick revealed tutorial",
        audio_wav_path=None,  # No audio wav for this test
        db=db_session
    )

    assert res.text_cosine_score > 0.70
    assert res.has_verified_yt_channel is False

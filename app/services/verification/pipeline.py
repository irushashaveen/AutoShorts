import logging
from pathlib import Path
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models import AudioFingerprint, Task, TaskStatus
from app.services.verification.bio_scanner import BioScanner
from app.services.verification.acoustic_hasher import AcousticHasher
from app.services.verification.text_similarity import TextSimilarity
from app.services.verification.risk_evaluator import RiskEvaluator, VerificationResult

logger = logging.getLogger(__name__)


class VerificationPipeline:
    """Orchestrates Phase 3 copyright verification and acoustic/textual deduplication."""

    def __init__(
        self,
        bio_scanner: Optional[BioScanner] = None,
        hasher: Optional[AcousticHasher] = None,
        text_sim: Optional[TextSimilarity] = None,
        evaluator: Optional[RiskEvaluator] = None
    ):
        self.bio_scanner = bio_scanner or BioScanner()
        self.hasher = hasher or AcousticHasher()
        self.text_sim = text_sim or TextSimilarity()
        self.evaluator = evaluator or RiskEvaluator()

    def run_verification(
        self,
        creator_bio: Optional[str],
        candidate_caption: str,
        audio_wav_path: Optional[Path],
        db: Session,
        youtube_service: Optional[object] = None
    ) -> VerificationResult:
        """
        Executes full verification workflow:
        1. Scan creator bio for YouTube handles.
        2. Hash audio track and match against database acoustic fingerprints.
        3. Match caption against database published Shorts titles/captions using TF-IDF & Levenshtein.
        4. Calculate composite duplicate risk score R_dup.
        """
        # 1. Creator Bio Scan
        handle, has_verified_yt = self.bio_scanner.scan_creator(creator_bio, youtube_service)

        # 2. Acoustic Fingerprinting
        audio_match_score = 0.0
        candidate_fp: Optional[str] = None
        if audio_wav_path and audio_wav_path.exists():
            try:
                _, candidate_fp = self.hasher.fingerprint_file(audio_wav_path)
                # Query existing audio fingerprints from database
                existing_fps = [
                    row[0] for row in db.query(AudioFingerprint.fingerprint_hash).all()
                ]
                audio_match_score = self.hasher.find_max_match(candidate_fp, existing_fps)
            except Exception as e:
                logger.warning(f"Audio fingerprint matching encountered issue: {e}")

        # 3. Text Vector Proximity
        text_cos_score = 0.0
        lev_score = 0.0
        try:
            # Query existing captions / AI titles from database
            published_captions = [
                row[0] for row in db.query(Task.raw_caption).filter(Task.raw_caption.isnot(None)).all()
            ] + [
                row[0] for row in db.query(Task.ai_title).filter(Task.ai_title.isnot(None)).all()
            ]
            text_cos_score, lev_score = self.text_sim.evaluate_against_corpus(
                candidate_caption,
                published_captions
            )
        except Exception as e:
            logger.warning(f"Text similarity evaluation encountered issue: {e}")

        # 4. Composite Risk Evaluation
        result = self.evaluator.evaluate(
            youtube_handle=handle,
            has_verified_yt_channel=has_verified_yt,
            audio_match=audio_match_score,
            tfidf_cosine=text_cos_score,
            levenshtein_norm=lev_score
        )

        return result


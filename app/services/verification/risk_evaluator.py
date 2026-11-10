from dataclasses import dataclass
from typing import Optional, List
from app.config import settings
from app.models.task import TaskStatus


@dataclass
class VerificationResult:
    """Summary of intellectual property & deduplication heuristics."""
    youtube_handle: Optional[str]
    has_verified_yt_channel: bool
    audio_match_score: float
    text_cosine_score: float
    levenshtein_score: float
    duplicate_risk_score: float
    is_duplicate_suspect: bool
    recommended_status: TaskStatus


class RiskEvaluator:
    """Calculates weighted composite duplicate risk score and maps state machine status."""

    def __init__(
        self,
        weight_audio: float = settings.WEIGHT_AUDIO_MATCH,
        weight_tfidf: float = settings.WEIGHT_TFIDF_COSINE,
        weight_levenshtein: float = settings.WEIGHT_LEVENSHTEIN,
        risk_threshold: float = settings.DUP_RISK_THRESHOLD,
    ):
        self.w_audio = weight_audio
        self.w_tfidf = weight_tfidf
        self.w_lev = weight_levenshtein
        self.threshold = risk_threshold

    def calculate_risk(
        self,
        audio_match: float,
        tfidf_cosine: float,
        levenshtein_norm: float
    ) -> float:
        """
        R_dup = 0.50 * Match_audio + 0.30 * S_cos + 0.20 * L_norm
        """
        raw_score = (
            (self.w_audio * audio_match) +
            (self.w_tfidf * tfidf_cosine) +
            (self.w_lev * levenshtein_norm)
        )
        return float(max(0.0, min(1.0, round(raw_score, 4))))

    def evaluate(
        self,
        youtube_handle: Optional[str],
        has_verified_yt_channel: bool,
        audio_match: float,
        tfidf_cosine: float,
        levenshtein_norm: float
    ) -> VerificationResult:
        """Determine whether item is flagged for creator channel or duplicate suspicion."""
        risk_score = self.calculate_risk(audio_match, tfidf_cosine, levenshtein_norm)
        is_duplicate = risk_score > self.threshold

        # Determine target task state
        if has_verified_yt_channel:
            target_status = TaskStatus.FLAGGED_CREATOR_CHANNEL
        elif is_duplicate:
            target_status = TaskStatus.DUPLICATE_SUSPECT
        else:
            target_status = TaskStatus.OPTIMIZING

        return VerificationResult(
            youtube_handle=youtube_handle,
            has_verified_yt_channel=has_verified_yt_channel,
            audio_match_score=audio_match,
            text_cosine_score=tfidf_cosine,
            levenshtein_score=levenshtein_norm,
            duplicate_risk_score=risk_score,
            is_duplicate_suspect=is_duplicate,
            recommended_status=target_status
        )


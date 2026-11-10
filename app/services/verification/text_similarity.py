import re
import logging
from typing import List, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)


def compute_levenshtein_distance(s1: str, s2: str) -> int:
    """Compute standard Levenshtein edit distance using dynamic programming."""
    if len(s1) < len(s2):
        return compute_levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def compute_normalized_levenshtein(s1: str, s2: str) -> float:
    """
    Computes normalized Levenshtein similarity:
    L_norm = 1 - (distance / max(len(s1), len(s2)))
    Returns a float in [0.0, 1.0].
    """
    s1_clean = re.sub(r"\s+", " ", s1.strip().lower())
    s2_clean = re.sub(r"\s+", " ", s2.strip().lower())

    if not s1_clean and not s2_clean:
        return 1.0
    if not s1_clean or not s2_clean:
        return 0.0

    max_len = max(len(s1_clean), len(s2_clean))
    distance = compute_levenshtein_distance(s1_clean, s2_clean)
    similarity = 1.0 - (distance / max_len)
    return max(0.0, min(1.0, similarity))


class TextSimilarity:
    """Calculates TF-IDF vector cosine similarity and Levenshtein string distance."""

    @staticmethod
    def clean_text(text: Optional[str]) -> str:
        """Strip emojis, hashtags, and excess punctuation for cleaner comparison."""
        if not text:
            return ""
        # Remove hashtags and leading symbols
        cleaned = re.sub(r"#\S+", "", text)
        cleaned = re.sub(r"[^\w\s]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
        return cleaned

    @classmethod
    def compute_tfidf_cosine(cls, text1: str, text2: str) -> float:
        """Compute cosine similarity of TF-IDF sparse vector representations."""
        c1 = cls.clean_text(text1)
        c2 = cls.clean_text(text2)

        if not c1 or not c2:
            return 0.0
        if c1 == c2:
            return 1.0

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
            tfidf_matrix = vectorizer.fit_transform([c1, c2])
            sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(max(0.0, min(1.0, sim)))
        except Exception as e:
            logger.warning(f"TF-IDF calculation fallback to word overlap: {e}")
            # Fallback to Jaccard word set similarity if vocab is too small
            words1 = set(c1.split())
            words2 = set(c2.split())
            if not words1 or not words2:
                return 0.0
            return len(words1 & words2) / len(words1 | words2)

    @classmethod
    def evaluate_against_corpus(
        cls,
        candidate_text: str,
        corpus_texts: List[str]
    ) -> Tuple[float, float]:
        """
        Compare candidate against list of existing captions.
        Returns: (max_cosine_similarity, max_normalized_levenshtein)
        """
        if not candidate_text or not corpus_texts:
            return 0.0, 0.0

        max_cos = 0.0
        max_lev = 0.0

        for existing in corpus_texts:
            if not existing:
                continue
            cos = cls.compute_tfidf_cosine(candidate_text, existing)
            lev = compute_normalized_levenshtein(candidate_text, existing)
            if cos > max_cos:
                max_cos = cos
            if lev > max_lev:
                max_lev = lev

        return max_cos, max_lev


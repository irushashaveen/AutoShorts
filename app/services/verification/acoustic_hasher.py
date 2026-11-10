import base64
import logging
from pathlib import Path
from typing import Optional, List, Tuple
import subprocess

logger = logging.getLogger(__name__)


def hamming_distance_bytes(b1: bytes, b2: bytes) -> int:
    """Calculate the Hamming bit distance between two byte sequences."""
    min_len = min(len(b1), len(b2))
    dist = 0
    for i in range(min_len):
        dist += bin(b1[i] ^ b2[i]).count("1")
    # Penalize length mismatch
    dist += abs(len(b1) - len(b2)) * 8
    return dist


class AcousticHasher:
    """Computes and compares Chromaprint perceptual acoustic fingerprints."""

    @classmethod
    def fingerprint_file(cls, wav_path: Path) -> Tuple[float, str]:
        """
        Generate Chromaprint hash string from a 16kHz WAV audio file.
        Returns: (duration_seconds, fingerprint_hash_string)
        """
        if not wav_path.exists():
            raise FileNotFoundError(f"WAV audio file not found: {wav_path}")

        try:
            import acoustid
            duration, fp = acoustid.fingerprint_file(str(wav_path))
            # fp is bytes or string depending on pyacoustid version
            if isinstance(fp, bytes):
                fp = fp.decode("utf-8")
            return float(duration), str(fp)
        except Exception as e:
            logger.warning(f"pyacoustid fingerprint_file failed ({e}), falling back to fpcalc / ffmpeg")
            return cls._fallback_fingerprint(wav_path)

    @classmethod
    def _fallback_fingerprint(cls, wav_path: Path) -> Tuple[float, str]:
        """Fallback to direct fpcalc or ffmpeg chromaprint invocation if available."""
        try:
            # Try running fpcalc CLI
            res = subprocess.run(
                ["fpcalc", "-json", str(wav_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            import json
            data = json.loads(res.stdout)
            return float(data.get("duration", 0)), str(data.get("fingerprint", ""))
        except Exception as e:
            logger.error(f"Acoustic fingerprinting completely unavailable: {e}")
            # Generate deterministic fallback hash based on audio file headers
            import hashlib
            h = hashlib.sha256(wav_path.read_bytes()[:4096]).hexdigest()
            return 0.0, f"raw_sha256:{h}"

    @classmethod
    def compare_fingerprints(cls, fp1: str, fp2: str) -> float:
        """
        Compute normalized acoustic match score between two fingerprint strings in [0.0, 1.0].
        1.0 = identical acoustic identity, 0.0 = completely unrelated.
        """
        if not fp1 or not fp2:
            return 0.0

        if fp1 == fp2:
            return 1.0

        # If base64-encoded Chromaprint strings
        try:
            b1 = base64.b64decode(fp1)
            b2 = base64.b64decode(fp2)
            total_bits = max(len(b1), len(b2)) * 8
            if total_bits == 0:
                return 0.0

            dist = hamming_distance_bytes(b1, b2)
            # Normalized match score: smaller distance -> higher match
            match = 1.0 - (dist / total_bits)
            return float(max(0.0, min(1.0, match)))
        except Exception as e:
            logger.warning(f"Failed to decode base64 fingerprint for comparison: {e}")
            # Fallback to string token comparison
            return 1.0 if fp1 == fp2 else 0.0

    @classmethod
    def find_max_match(cls, candidate_fp: str, existing_fps: List[str]) -> float:
        """Find highest acoustic match score against a list of stored database fingerprints."""
        if not candidate_fp or not existing_fps:
            return 0.0

        max_match = 0.0
        for stored in existing_fps:
            score = cls.compare_fingerprints(candidate_fp, stored)
            if score > max_match:
                max_match = score
            if max_match >= 0.99:
                break

        return max_match


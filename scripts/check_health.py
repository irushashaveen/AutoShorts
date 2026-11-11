#!/usr/bin/env python3
"""
AutoShorts Diagnostic & Health Check Utility
Tests local dependencies: Python, FFmpeg, ffprobe, Chromaprint, Redis, SQLite, and Ollama.
"""

import sys
import subprocess
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.database import engine
from sqlalchemy import text


def check_python():
    print(f"[✓] Python: {sys.version.split()[0]} ({sys.executable})")


def check_ffmpeg():
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if ffmpeg_path and ffprobe_path:
        try:
            res = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, text=True, check=True)
            has_chromaprint = "chromaprint" in res.stdout
            chroma_flag = "with Chromaprint" if has_chromaprint else "without Chromaprint"
            print(f"[✓] FFmpeg: Found at {ffmpeg_path} ({chroma_flag})")
            print(f"[✓] FFprobe: Found at {ffprobe_path}")
        except Exception as e:
            print(f"[!] FFmpeg error: {e}")
    else:
        print("[✗] FFmpeg/FFprobe: NOT found in system PATH.")


def check_sqlite():
    try:
        with engine.connect() as conn:
            mode = conn.execute(text("PRAGMA journal_mode;")).scalar()
            timeout = conn.execute(text("PRAGMA busy_timeout;")).scalar()
            print(f"[✓] SQLite Engine: Connected successfully (journal_mode={mode}, busy_timeout={timeout}ms)")
    except Exception as e:
        print(f"[✗] SQLite Engine error: {e}")


def check_redis():
    try:
        import redis
        client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2.0)
        client.ping()
        print(f"[✓] Redis: Connected to {settings.REDIS_URL}")
    except Exception as e:
        print(f"[-] Redis: Not running or unreachable at {settings.REDIS_URL} ({e})")


def check_ollama():
    try:
        import httpx
        res = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2.0)
        if res.status_code == 200:
            models = [m.get("name") for m in res.json().get("models", [])]
            print(f"[✓] Ollama: Connected to {settings.OLLAMA_BASE_URL} (available models: {models})")
        else:
            print(f"[-] Ollama: Returned status {res.status_code}")
    except Exception:
        print(f"[-] Ollama: Offline or unreachable at {settings.OLLAMA_BASE_URL} (Normal if local Docker Ollama is stopped)")


def main():
    print("=" * 60)
    print(f"AutoShorts System Diagnostics ({settings.APP_ENV} mode)")
    print("=" * 60)
    check_python()
    check_ffmpeg()
    check_sqlite()
    check_redis()
    check_ollama()
    print("=" * 60)
    print("Diagnostics complete.")


if __name__ == "__main__":
    main()


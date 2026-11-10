import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)


class FFmpegError(Exception):
    """Raised when an FFmpeg or FFprobe command execution fails."""
    pass


class FFmpegNormalizer:
    """Handles video inspection, aspect ratio transcoding to 1080x1920, and audio extraction."""

    @staticmethod
    def probe_video(video_path: Path) -> Dict[str, Any]:
        """Query video metadata (width, height, codec, duration) via ffprobe."""
        if not video_path.exists():
            raise FileNotFoundError(f"Media file not found: {video_path}")

        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,codec_name:format=duration",
            "-of", "json",
            str(video_path)
        ]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            probe_data = json.loads(result.stdout)
            streams = probe_data.get("streams", [])
            format_info = probe_data.get("format", {})

            width = 0
            height = 0
            codec_name = "unknown"
            if streams:
                width = int(streams[0].get("width", 0))
                height = int(streams[0].get("height", 0))
                codec_name = streams[0].get("codec_name", "unknown")

            duration = float(format_info.get("duration", 0.0))

            return {
                "width": width,
                "height": height,
                "codec": codec_name,
                "duration": duration
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe failed on {video_path}: {e.stderr}")
            raise FFmpegError(f"ffprobe failed: {e.stderr}")
        except Exception as e:
            logger.error(f"Failed to parse ffprobe output: {e}")
            raise FFmpegError(f"Failed to parse ffprobe output: {e}")

    @classmethod
    def normalize_video(cls, input_path: Path, output_path: Optional[Path] = None) -> Path:
        """
        Verify video conforms to 1080x1920 H.264 standard for YouTube Shorts.
        Transcodes if resolution or codec diverges.
        """
        probe = cls.probe_video(input_path)
        is_compliant = (
            probe["width"] == 1080 and
            probe["height"] == 1920 and
            "h264" in probe["codec"].lower()
        )

        if is_compliant and output_path is None:
            return input_path

        if output_path is None:
            output_path = input_path.parent / f"{input_path.stem}_normalized.mp4"

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path)
        ]

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg transcoding failed on {input_path}: {e.stderr}")
            raise FFmpegError(f"FFmpeg transcoding failed: {e.stderr}")

    @staticmethod
    def extract_audio_wav(input_path: Path, output_wav_path: Optional[Path] = None) -> Path:
        """Extract audio track as 16kHz mono WAV for Chromaprint acoustic fingerprinting."""
        if output_wav_path is None:
            output_wav_path = input_path.parent / f"{input_path.stem}_audio.wav"

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            "-f", "wav",
            str(output_wav_path)
        ]

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return output_wav_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg audio extraction failed on {input_path}: {e.stderr}")
            raise FFmpegError(f"FFmpeg audio extraction failed: {e.stderr}")

    @staticmethod
    def extract_thumbnail_frame(input_path: Path, output_thumb_path: Optional[Path] = None) -> Path:
        """Extract a clear frame at 1-second mark as JPG thumbnail."""
        if output_thumb_path is None:
            output_thumb_path = input_path.parent / f"{input_path.stem}_thumb.jpg"

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", "00:00:01",
            "-i", str(input_path),
            "-vframes", "1",
            "-q:v", "2",
            str(output_thumb_path)
        ]

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return output_thumb_path
        except subprocess.CalledProcessError as e:
            # Try at 00:00:00 if video is shorter than 1 second
            cmd[2] = "00:00:00"
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return output_thumb_path


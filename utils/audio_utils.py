"""
utils/audio_utils.py
Handles audio format conversion using ffmpeg.
Whisper needs: 16kHz, mono, WAV format.
"""
import os
import tempfile
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioUtils:

    @staticmethod
    def preprocess(input_path: str, output_path: str = None) -> str:
        """Convert any audio format → 16kHz mono WAV for Whisper."""
        if output_path is None:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            output_path = tmp.name
            tmp.close()

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-ar", "16000",   # 16kHz sample rate
            "-ac", "1",       # mono channel
            "-f", "wav",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"ffmpeg error: {result.stderr}")
            raise RuntimeError(f"Audio preprocessing failed: {result.stderr[:200]}")

        return output_path

    @staticmethod
    def save_upload(file_obj, directory: str = "audio/input") -> str:
        """Save uploaded file to disk, return path."""
        os.makedirs(directory, exist_ok=True)
        suffix = Path(file_obj.filename).suffix if hasattr(file_obj, "filename") else ".wav"
        tmp = tempfile.NamedTemporaryFile(dir=directory, suffix=suffix, delete=False)
        if hasattr(file_obj, "save"):
            file_obj.save(tmp.name)
        else:
            tmp.write(file_obj.read())
        tmp.close()
        return tmp.name

    @staticmethod
    def ffmpeg_available() -> bool:
        """Check if ffmpeg is installed."""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True)
            return True
        except FileNotFoundError:
            return False

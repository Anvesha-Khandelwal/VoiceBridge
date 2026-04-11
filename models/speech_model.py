"""
models/speech_model.py
CONCEPT: Automatic Speech Recognition (ASR)

Whisper is a neural network trained by OpenAI on 680,000 hours of audio.
It converts spoken audio → text in 99 languages.

HOW IT WORKS:
1. Audio is converted to a mel spectrogram (visual representation of sound)
2. An encoder (Transformer) processes the spectrogram → feature vectors
3. A decoder generates text tokens from those features
4. Output: transcribed text with optional timestamps
"""
import os
import tempfile
import logging
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


class SpeechModel:
    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None  # lazy load — only loads when first used
        logger.info(f"SpeechModel ready (size={model_size}, lazy-load enabled)")

    def transcribe(self, audio_input, language: Optional[str] = None) -> str:
        """
        Convert audio to text.
        audio_input: file path (str) | Flask FileStorage | numpy array
        language: ISO-639-1 code like 'hi', 'en' — helps accuracy
        """
        model = self._load()
        options = {"fp16": False}  # fp16=False ensures CPU compatibility
        if language:
            options["language"] = language

        # Handle numpy arrays directly
        if isinstance(audio_input, np.ndarray):
            result = model.transcribe(audio_input, **options)
            return result["text"].strip()

        # Handle file paths
        if isinstance(audio_input, str):
            if not os.path.exists(audio_input):
                raise FileNotFoundError(f"Audio file not found: {audio_input}")
            result = model.transcribe(audio_input, **options)
            return result["text"].strip()

        # Handle file-like objects (Flask FileStorage)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            if hasattr(audio_input, "save"):
                audio_input.save(tmp_path)
            else:
                tmp.write(audio_input.read())

        try:
            from utils.audio_utils import AudioUtils
            processed = AudioUtils.preprocess(tmp_path)
            result = model.transcribe(processed, **options)
            return result["text"].strip()
        finally:
            for p in [tmp_path]:
                try:
                    os.remove(p)
                except Exception:
                    pass

    def _load(self):
        """Load Whisper model — only runs once, cached after first load."""
        if self._model is None:
            import whisper
            logger.info(f"Loading Whisper '{self.model_size}' model (first time only)...")
            self._model = whisper.load_model(self.model_size)
            logger.info("Whisper model loaded successfully.")
        return self._model

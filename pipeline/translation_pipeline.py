"""
pipeline/translation_pipeline.py
Orchestrates: Audio → Whisper ASR → Groq Translation
"""
import logging
from typing import Optional
from models.speech_model import SpeechModel
from models.translation_model import GroqTranslator

logger = logging.getLogger(__name__)


class TranslationPipeline:
    def __init__(self, config):
        self.config = config
        self.speech_model = SpeechModel(model_size=config.WHISPER_MODEL_SIZE)
        self.translator = GroqTranslator(
            api_key=config.GROQ_API_KEY,
            model=config.GROQ_MODEL
        )

    def speech_to_text(self, audio_input, language: Optional[str] = None) -> str:
        return self.speech_model.transcribe(audio_input, language=language)

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text.strip():
            return ""
        return self.translator.translate(text, source_lang, target_lang)

    def run(self, audio_input, source_lang=None, target_lang="en") -> dict:
        """Full pipeline: audio → transcript → translation"""
        original_text = self.speech_to_text(audio_input, language=source_lang)
        if not original_text:
            return {"error": "No speech detected", "original_text": "", "translated_text": ""}

        translated_text = self.translate(original_text, source_lang or "auto", target_lang)
        return {
            "original_text": original_text,
            "translated_text": translated_text,
            "source_lang": source_lang or "auto",
            "target_lang": target_lang,
            "word_count": len(original_text.split())
        }

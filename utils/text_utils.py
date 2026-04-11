"""utils/text_utils.py — Text cleaning helpers"""
import re
import unicodedata


class TextUtils:

    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""
        text = unicodedata.normalize("NFC", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def word_count(text: str) -> int:
        return len(text.split()) if text else 0

    @staticmethod
    def estimated_read_time(text: str) -> str:
        words = TextUtils.word_count(text)
        minutes = max(1, round(words / 200))  # avg 200 wpm
        return f"{minutes} min read"

    @staticmethod
    def truncate(text: str, max_chars: int = 500) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "…"

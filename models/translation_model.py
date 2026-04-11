"""
models/translation_model.py
Uses Groq API (free) with LLaMA3 for translation.
THIS FILE FIXES the translation not working bug.
"""
import logging
logger = logging.getLogger(__name__)

LANG_NAMES = {
    "en":"English", "hi":"Hindi", "es":"Spanish", "fr":"French",
    "de":"German",  "ta":"Tamil", "te":"Telugu",  "bn":"Bengali",
    "mr":"Marathi", "ja":"Japanese","zh":"Chinese","ar":"Arabic",
    "pt":"Portuguese","ru":"Russian","ko":"Korean",
    "auto":"the detected language",
}


class GroqTranslator:
    def __init__(self, api_key: str, model: str = "llama3-8b-8192"):
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY missing. "
                "Get free key at console.groq.com → add to .env"
            )
        from groq import Groq
        self.client = Groq(api_key=api_key)
        self.model  = model
        logger.info(f"GroqTranslator ready (model={model})")

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        target = LANG_NAMES.get(target_lang, target_lang)
        source = LANG_NAMES.get(source_lang, "the source language")
        resp = self.client.chat.completions.create(
            model    = self.model,
            max_tokens = 2048,
            temperature = 0.1,
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"You are a professional translator. "
                        f"Translate from {source} to {target}. "
                        f"Return ONLY the translated text. "
                        f"No explanations, no quotes, no extra words."
                    )
                },
                {"role": "user", "content": text}
            ]
        )
        return resp.choices[0].message.content.strip()
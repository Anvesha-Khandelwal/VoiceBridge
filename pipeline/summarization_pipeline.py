import logging, json, re
logger = logging.getLogger(__name__)


class SummarizationPipeline:
    def __init__(self, config):
        if not config.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY missing in .env file")
        from groq import Groq
        self.client = Groq(api_key=config.GROQ_API_KEY)
        self.model  = config.GROQ_MODEL
        logger.info(f"SummarizationPipeline ready (model={self.model})")

    def summarize(self, text: str, style: str = "detailed") -> dict:
        if not text or len(text.strip()) < 20:
            return {"error": "Text too short to summarize"}
        wc = len(text.split())
        if style == "brief":   return self._brief(text, wc)
        if style == "bullets": return self._bullets(text, wc)
        return self._detailed(text, wc)

    def _detailed(self, text: str, wc: int) -> dict:
        system = (
            'You are a JSON generator. Return ONLY this exact JSON structure '
            'with no markdown, no explanation, no code blocks:\n'
            '{"overview":"summary here","key_points":["point1","point2"],'
            '"topics":["topic1"],"action_items":[],'
            '"sentiment":"neutral","speaker_intent":"intent here"}'
        )
        raw = self._call(system, f"Summarize this ({wc} words):\n\n{text}", 1024)
        try:
            clean  = re.sub(r"```[a-z]*|```", "", raw).strip()
            result = json.loads(clean)
            result["word_count"] = wc
            result["style"]      = "detailed"
            return result
        except json.JSONDecodeError:
            return {
                "overview":      raw,
                "key_points":    [],
                "topics":        [],
                "action_items":  [],
                "sentiment":     "neutral",
                "word_count":    wc,
                "style":         "detailed"
            }

    def _brief(self, text: str, wc: int) -> dict:
        raw = self._call("Summarize in 2-3 clear sentences.", text, 256)
        return {"overview": raw, "word_count": wc, "style": "brief"}

    def _bullets(self, text: str, wc: int) -> dict:
        raw = self._call(
            "List the key points as bullet points. Format: • point",
            text, 512
        )
        pts = [l.lstrip("•-* ").strip() for l in raw.split("\n") if l.strip()]
        return {"key_points": pts, "word_count": wc, "style": "bullets"}

    def _call(self, system: str, user: str, max_tokens: int) -> str:
        r = self.client.chat.completions.create(
            model       = self.model,
            max_tokens  = max_tokens,
            temperature = 0.3,
            messages    = [
                {"role": "system", "content": system},
                {"role": "user",   "content": user}
            ]
        )
        return r.choices[0].message.content.strip()
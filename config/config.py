import os
from dotenv import load_dotenv
load_dotenv()


class Config:
    # ── Groq ──────────────────────────────────────────────────────────────
    GROQ_API_KEY: str       = os.getenv("GROQ_API_KEY", "")
    # Updated model — llama3-8b-8192 is decommissioned
    GROQ_MODEL: str         = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    # ── Whisper ───────────────────────────────────────────────────────────
    WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "tiny")

    # ── Embeddings / RAG ──────────────────────────────────────────────────
    EMBEDDING_MODEL: str    = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    CHUNK_SIZE: int         = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int      = int(os.getenv("CHUNK_OVERLAP", "100"))

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str       = os.getenv("DATABASE_URL", "sqlite:///voicebridge.db")
    SECRET_KEY: str         = os.getenv("SECRET_KEY", "voicebridge-secret-key-2026")

    # ── Flask ─────────────────────────────────────────────────────────────
    PORT: int               = int(os.getenv("PORT", 5000))
    FLASK_DEBUG: bool       = os.getenv("FLASK_DEBUG", "false").lower() == "true"
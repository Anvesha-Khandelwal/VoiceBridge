"""config/config.py — All settings"""
import os
from dotenv import load_dotenv
load_dotenv()


class Config:
    GROQ_API_KEY: str       = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str         = os.getenv("GROQ_MODEL", "llama3-8b-8192")
    WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "base")
    EMBEDDING_MODEL: str    = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    CHUNK_SIZE: int         = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int      = int(os.getenv("CHUNK_OVERLAP", "100"))
    DATABASE_URL: str       = os.getenv("DATABASE_URL", "sqlite:///voicebridge.db")
    SECRET_KEY: str         = os.getenv("SECRET_KEY", "dev-change-in-production")
    PORT: int               = int(os.getenv("PORT", 5000))
    FLASK_DEBUG: bool       = os.getenv("FLASK_DEBUG", "false").lower() == "true"
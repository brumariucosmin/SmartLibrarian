import os
from dataclasses import dataclass

# Bază absolută: folderul rădăcină al proiectului (../ față de app/)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

def _abs(path_like: str) -> str:
    # Dacă utilizatorul a setat o cale absolută în env, o respectăm; altfel o facem absolută raportat la BASE_DIR
    return path_like if os.path.isabs(path_like) else os.path.abspath(os.path.join(BASE_DIR, path_like))

@dataclass(frozen=True)
class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-4.1-mini")
    EMBED_MODEL: str = os.getenv("EMBED_MODEL", "text-embedding-3-small")

    # Default-uri făcute ABSOLUTE din BASE_DIR
    CHROMA_PATH: str = _abs(os.getenv("CHROMA_PATH", "chroma"))
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "books")
    DATA_PATH: str = _abs(os.getenv("DATA_PATH", os.path.join("data", "book_summaries.jsonl")))

    TOP_K: int = int(os.getenv("TOP_K", "3"))
    SIMILARITY_MAX_DISTANCE: float = float(os.getenv("SIMILARITY_MAX_DISTANCE", "0.35"))

    # Image generation (optional)
    IMAGE_MODEL: str = os.getenv("IMAGE_MODEL", "gpt-image-1")
    IMAGE_SIZE: str = os.getenv("IMAGE_SIZE", "1024x1024")

settings = Settings()

def require_api_key():
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("Set OPENAI_API_KEY in your environment before running.")

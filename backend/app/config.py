import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path(os.getenv("DB_PATH", BACKEND_DIR / "data" / "shop.db"))
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    max_attempts: int = int(os.getenv("MAX_ATTEMPTS", "3"))        # generate -> run -> fix loop
    max_rows: int = int(os.getenv("MAX_ROWS", "200"))              # rows returned to the client
    query_timeout_ms: int = int(os.getenv("QUERY_TIMEOUT_MS", "3000"))
    summarize: bool = os.getenv("SUMMARIZE", "true").lower() in ("1", "true", "yes")  # plain-English answer
    cors_origins: tuple = tuple(
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
    )


settings = Settings()

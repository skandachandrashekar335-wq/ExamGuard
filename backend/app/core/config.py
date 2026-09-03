from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    APP_NAME: str = "ExamGuard"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-to-a-random-secret-key"

    DATABASE_URL: str = "postgresql://user:password@localhost:5432/examguard"

    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    NEXT_PUBLIC_API_URL: str = "http://localhost:8000"

    # Upload settings
    MAX_UPLOAD_SIZE_MB: int = 10
    UPLOAD_DIR: str = str(PROJECT_ROOT / "uploads")
    ALLOWED_DOCUMENT_TYPES: list[str] = ["HALL_TICKET"]

    # OCR settings
    TESSERACT_CMD: str | None = None
    POPPLER_PATH: str | None = None
    MAX_DOCUMENT_PAGES: int = 20
    OCR_LANGUAGE: str = "eng"

    # USN pattern (configurable per institution)
    USN_PATTERN: str | None = None

    # Verification settings
    MIN_OCR_CONFIDENCE: float = 60.0

    # Identity verification settings
    IDENTITY_VERIFICATION_MATCH_THRESHOLD: float = 0.85


@lru_cache
def get_settings() -> Settings:
    return Settings()

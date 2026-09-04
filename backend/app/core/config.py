from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
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

    # Identity verification decision policy
    # Threshold for similarity score: scores >= threshold → MATCH candidate
    IDENTITY_VERIFICATION_MATCH_THRESHOLD: float = 0.85
    # Near-threshold zone: scores >= threshold * NEAR_THRESHOLD_FACTOR → INCONCLUSIVE
    # Must be in range (0.0, 1.0]. Lower values widen the review zone.
    IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR: float = 0.7
    # Policy version identifier for audit trail
    IDENTITY_VERIFICATION_POLICY_VERSION: str = "1.0"

    # Face verification provider settings
    # Provider name: "deterministic" (test), "none" (disabled), or "uniface"
    FACE_VERIFICATION_PROVIDER: str = "deterministic"
    # Provider-specific settings (future use)
    FACE_VERIFICATION_PROVIDER_URL: str | None = None
    FACE_VERIFICATION_PROVIDER_API_KEY: str | None = None
    # Image constraints
    FACE_VERIFICATION_MAX_IMAGE_SIZE_MB: int = 5
    # Retention: how long to keep raw verification images (days). 0 = never store.
    FACE_VERIFICATION_IMAGE_RETENTION_DAYS: int = 0
    # Rate limiting: max verify-face calls per attempt (0 = unlimited)
    FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT: int = 5
    # Rate limiting: max verify-face calls per minute globally (0 = unlimited)
    FACE_VERIFICATION_MAX_CALLS_PER_MINUTE: int = 60

    # Proxy risk scoring settings
    PROXY_RISK_WEIGHTS: str = (
        "DUPLICATE_ENTRY:30,UNUSUAL_ENTRY_POINT:15,UNUSUAL_TIME:10,"
        "SEAT_MISMATCH:40,MULTIPLE_REGISTRATIONS:40,RAPID_ENTRY:20,"
        "DOCUMENT_ANOMALY:35,BEHAVIORAL_ANOMALY:25,IDENTITY_MISMATCH:45,"
        "MANUAL_FLAG:15"
    )
    PROXY_RISK_ELEVATED_THRESHOLD: float = 30.0
    PROXY_RISK_HIGH_THRESHOLD: float = 60.0
    PROXY_RISK_CRITICAL_THRESHOLD: float = 80.0
    PROXY_RISK_MAX_SCORE: float = 100.0
    PROXY_RISK_POLICY_VERSION: str = "1.0"

    @model_validator(mode="after")
    def validate_decision_policy(self) -> "Settings":
        """Validate decision policy configuration values."""
        if not (0.0 < self.IDENTITY_VERIFICATION_MATCH_THRESHOLD <= 1.0):
            raise ValueError(
                f"IDENTITY_VERIFICATION_MATCH_THRESHOLD must be in (0.0, 1.0], "
                f"got {self.IDENTITY_VERIFICATION_MATCH_THRESHOLD}"
            )
        if not (0.0 < self.IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR <= 1.0):
            raise ValueError(
                f"IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR must in (0.0, 1.0], "
                f"got {self.IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR}"
            )
        return self

    @model_validator(mode="after")
    def validate_proxy_risk_thresholds(self) -> "Settings":
        """Validate proxy risk threshold ordering and ranges."""
        if not (0.0 <= self.PROXY_RISK_ELEVATED_THRESHOLD < self.PROXY_RISK_HIGH_THRESHOLD < self.PROXY_RISK_CRITICAL_THRESHOLD):
            raise ValueError(
                f"Proxy risk thresholds must satisfy: 0 <= ELEVATED < HIGH < CRITICAL, "
                f"got ELEVATED={self.PROXY_RISK_ELEVATED_THRESHOLD}, "
                f"HIGH={self.PROXY_RISK_HIGH_THRESHOLD}, "
                f"CRITICAL={self.PROXY_RISK_CRITICAL_THRESHOLD}"
            )
        if not (self.PROXY_RISK_CRITICAL_THRESHOLD <= self.PROXY_RISK_MAX_SCORE):
            raise ValueError(
                f"PROXY_RISK_CRITICAL_THRESHOLD ({self.PROXY_RISK_CRITICAL_THRESHOLD}) "
                f"must be <= PROXY_RISK_MAX_SCORE ({self.PROXY_RISK_MAX_SCORE})"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

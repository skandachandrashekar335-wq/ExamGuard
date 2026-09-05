"""Schemas for proxy risk assessment API (Phase 11.4).

Response schemas for security signals and risk assessments.
No request body needed — all endpoints operate on existing EntryVerification.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Security Signal schemas
# ---------------------------------------------------------------------------


class SecuritySignalResponse(BaseModel):
    """Security signal record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_verification_id: int
    signal_type: str = Field(
        ...,
        description="Type of security signal detected",
    )
    strength: str = Field(
        ...,
        description="Strength classification (STRONG, MODERATE, WEAK, INFORMATIONAL)",
    )
    source: str = Field(
        ...,
        description="Source that produced this signal",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description of what was detected",
    )
    created_at: datetime


class SecuritySignalListResponse(BaseModel):
    """Paginated list of security signals."""

    items: list[SecuritySignalResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Risk Assessment schemas
# ---------------------------------------------------------------------------


class ProxyRiskAssessmentResponse(BaseModel):
    """Risk assessment record with audit fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_verification_id: int
    risk_level: str = Field(
        ...,
        description="Classified risk level (LOW, ELEVATED, HIGH, CRITICAL)",
    )
    risk_score: float = Field(
        ...,
        description="Internal numeric risk score (0.0 - max_score). "
        "This is an internal policy score, not a probability or confidence.",
    )
    signal_count: int | None = Field(
        default=None,
        description="Total signals evaluated in this assessment",
    )
    strong_signal_count: int | None = Field(
        default=None,
        description="Number of STRONG signals in this assessment",
    )
    explanation: str | None = Field(
        default=None,
        description="Deterministic human-readable explanation of the assessment",
    )
    policy_version: str | None = Field(
        default=None,
        description="Version of risk scoring policy used",
    )
    assessed_at: datetime


class ProxyRiskAssessmentListResponse(BaseModel):
    """Paginated list of risk assessments."""

    items: list[ProxyRiskAssessmentResponse]
    total: int
    page: int
    page_size: int

"""Proxy risk scoring and assessment.

Pure, deterministic risk-scoring engine that evaluates security signals
and produces risk assessments. No biometric data. No AI claims.

Architecture:
    SECURITY SIGNALS (from detection)
        ↓
    SCORING ENGINE (this module)
        ↓
    RISK ASSESSMENT (score + level + explanation)

The scoring engine:
- Is deterministic: same signals + same config → same assessment
- Is provider-independent: operates on SecuritySignal domain records
- Uses configurable weights from app.core.config
- Produces explainable reasoning for each assessment
- Does NOT contain authorization logic (that belongs to higher-level workflows)

Risk score is an internal prioritization value.
Risk level is the primary human-facing classification.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.proxy_risk import (
    ProxyRiskAssessment,
    RiskLevel,
    SecuritySignal,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskAssessmentResult:
    """Result of pure risk scoring.

    Attributes:
        risk_score: Numeric score (0.0 - max_score).
        risk_level: Classified risk level (LOW, ELEVATED, HIGH, CRITICAL).
        signal_count: Total signals evaluated.
        strong_signal_count: Number of STRONG signals.
        explanation: Deterministic human-readable explanation.
        signals_detail: Per-signal scoring breakdown (type, strength, weight).
    """

    risk_score: float
    risk_level: str
    signal_count: int
    strong_signal_count: int
    explanation: str
    signals_detail: list[dict[str, Any]] = field(default_factory=list)


def _parse_weights(raw: str) -> dict[str, float]:
    """Parse comma-separated weight string into a dict.

    Format: "TYPE:WEIGHT,TYPE:WEIGHT,..."
    Returns empty dict on empty input.
    """
    if not raw or not raw.strip():
        return {}
    weights: dict[str, float] = {}
    for part in raw.split(","):
        part = part.strip()
        if ":" not in part:
            continue
        key, val = part.split(":", 1)
        key = key.strip()
        val = val.strip()
        if key:
            try:
                weights[key] = float(val)
            except (ValueError, TypeError):
                logger.warning("Invalid weight value for %r: %r", key, val)
    return weights


def _classify_risk_level(score: float, settings: Any) -> str:
    """Classify a numeric score into a risk level using configured thresholds.

    LOW:     score < ELEVATED_THRESHOLD
    ELEVATED: ELEVATED_THRESHOLD <= score < HIGH_THRESHOLD
    HIGH:    HIGH_THRESHOLD <= score < CRITICAL_THRESHOLD
    CRITICAL: score >= CRITICAL_THRESHOLD
    """
    if score >= settings.PROXY_RISK_CRITICAL_THRESHOLD:
        return RiskLevel.CRITICAL.value
    if score >= settings.PROXY_RISK_HIGH_THRESHOLD:
        return RiskLevel.HIGH.value
    if score >= settings.PROXY_RISK_ELEVATED_THRESHOLD:
        return RiskLevel.ELEVATED.value
    return RiskLevel.LOW.value


def compute_risk_score(signals: list[SecuritySignal]) -> RiskAssessmentResult:
    """Pure, deterministic risk scoring.

    Evaluates a list of SecuritySignal records and produces a risk score,
    risk level, and explanation. No database side effects.

    Scoring algorithm:
    1. Look up each signal's weight from configured PROXY_RISK_WEIGHTS.
    2. For unknown signal types, default weight is 0 (informational only).
    3. Sum all weights, cap at PROXY_RISK_MAX_SCORE.
    4. Classify score into risk level via configured thresholds.
    5. Build deterministic explanation from signal types and strengths.

    Args:
        signals: List of SecuritySignal domain records.

    Returns:
        RiskAssessmentResult with score, level, counts, and explanation.
    """
    settings = get_settings()
    weights = _parse_weights(settings.PROXY_RISK_WEIGHTS)
    max_score = settings.PROXY_RISK_MAX_SCORE

    if not signals:
        return RiskAssessmentResult(
            risk_score=0.0,
            risk_level=RiskLevel.LOW.value,
            signal_count=0,
            strong_signal_count=0,
            explanation="No security signals detected",
            signals_detail=[],
        )

    total_score = 0.0
    strong_count = 0
    signals_detail: list[dict[str, Any]] = []

    for sig in signals:
        signal_type = sig.signal_type
        strength = sig.strength

        if strength == "STRONG":
            strong_count += 1

        weight = weights.get(signal_type, 0.0)
        total_score += weight

        signals_detail.append(
            {
                "type": signal_type,
                "strength": strength,
                "weight": weight,
            }
        )

    capped_score = min(total_score, max_score)
    risk_level = _classify_risk_level(capped_score, settings)

    # Build deterministic explanation
    explanation = _build_explanation(
        signal_count=len(signals),
        strong_count=strong_count,
        total_score=total_score,
        capped_score=capped_score,
        risk_level=risk_level,
        signals_detail=signals_detail,
    )

    return RiskAssessmentResult(
        risk_score=capped_score,
        risk_level=risk_level,
        signal_count=len(signals),
        strong_signal_count=strong_count,
        explanation=explanation,
        signals_detail=signals_detail,
    )


def _build_explanation(
    signal_count: int,
    strong_count: int,
    total_score: float,
    capped_score: float,
    risk_level: str,
    signals_detail: list[dict[str, Any]],
) -> str:
    """Build a deterministic, reproducible explanation string.

    Uses signal type labels and strengths. No biometric data.
    No AI claims. Purely factual.
    """
    parts: list[str] = []

    parts.append(
        f"Risk assessment based on {signal_count} signal"
        f"{'s' if signal_count != 1 else ''}"
    )

    # Count by strength
    strength_counts: dict[str, int] = {}
    for sig in signals_detail:
        s = sig["strength"]
        strength_counts[s] = strength_counts.get(s, 0) + 1

    strength_summary = []
    for s in ("STRONG", "MODERATE", "WEAK", "INFORMATIONAL"):
        if s in strength_counts:
            strength_summary.append(
                f"{strength_counts[s]} {s.lower()}"
            )
    if strength_summary:
        parts[0] += f" ({', '.join(strength_summary)})"

    # Scoring details
    if total_score != capped_score:
        parts.append(
            f"Raw score {total_score:.1f} capped to {capped_score:.1f}"
        )
    else:
        parts.append(f"Computed score {capped_score:.1f}")

    parts.append(f"Classified as {risk_level}")

    # List contributing signals with positive weight
    positive_signals = [
        s for s in signals_detail if s["weight"] > 0
    ]
    if positive_signals:
        labels = [
            f"{s['type']} ({s['strength'].lower()}, +{s['weight']:.0f})"
            for s in positive_signals
        ]
        parts.append("Contributing: " + ", ".join(labels))

    return ". ".join(parts) + "."


def _build_signals_summary(
    result: RiskAssessmentResult,
) -> str:
    """Build the signals_summary_json content for ProxyRiskAssessment.

    Stores: signal_count, strong_signal_count, explanation,
    and per-signal detail.
    """
    summary = {
        "signal_count": result.signal_count,
        "strong_signal_count": result.strong_signal_count,
        "explanation": result.explanation,
        "signals": result.signals_detail,
    }
    return json.dumps(summary, sort_keys=True)


def assess_entry_verification(
    db: Session,
    entry_verification_id: int,
) -> ProxyRiskAssessment:
    """Create a ProxyRiskAssessment for an entry verification.

    Loads all SecuritySignal records for the given entry verification,
    computes a risk score, persists a new ProxyRiskAssessment, and
    returns it.

    This function:
    - Does NOT modify the EntryVerification record.
    - Creates a NEW ProxyRiskAssessment (historical, append-only).
    - Is safe to call multiple times for the same entry verification.

    Args:
        db: Database session.
        entry_verification_id: ID of the entry verification to assess.

    Returns:
        Newly created ProxyRiskAssessment record.

    Raises:
        ValueError: If entry_verification_id is invalid or not found.
    """
    # Validate entry verification exists
    from app.models.entry_verification import EntryVerification

    ev = db.query(EntryVerification).filter(
        EntryVerification.id == entry_verification_id
    ).first()
    if ev is None:
        raise ValueError(
            f"Entry verification {entry_verification_id} not found"
        )

    # Load all signals for this entry verification
    signals = (
        db.query(SecuritySignal)
        .filter(
            SecuritySignal.entry_verification_id == entry_verification_id
        )
        .order_by(SecuritySignal.id)
        .all()
    )

    # Compute risk score (pure function, no DB side effects)
    result = compute_risk_score(signals)

    # Build summary JSON
    signals_summary_json = _build_signals_summary(result)

    # Create and persist assessment (historical, append-only)
    settings = get_settings()
    assessment = ProxyRiskAssessment(
        entry_verification_id=entry_verification_id,
        risk_level=result.risk_level,
        risk_score=result.risk_score,
        signals_summary_json=signals_summary_json,
        policy_version=settings.PROXY_RISK_POLICY_VERSION,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    logger.info(
        "Created risk assessment for entry_verification %d: "
        "level=%s score=%.1f signals=%d",
        entry_verification_id,
        result.risk_level,
        result.risk_score,
        result.signal_count,
    )

    return assessment

"""Identity verification decision engine.

Evaluates evidence records and produces decisions (MATCH / NO_MATCH / INCONCLUSIVE).

This is a provider-independent, deterministic decision engine. It interprets
evidence signals produced by face verification providers — it does NOT produce
evidence itself.

Architecture:
    EVIDENCE (from provider)
        ↓
    DECISION POLICY (this module)
        ↓
    VERIFICATION DECISION (MATCH / NO_MATCH / INCONCLUSIVE)

The decision engine:
- Is deterministic: same evidence + same config → same decision
- Is provider-independent: operates on domain evidence, not provider identity
- Uses configurable thresholds from app.core.config
- Produces explainable reasoning for each decision
- Does NOT contain authorization logic (that belongs to higher-level workflows)

Policy decisions are NOT biometric outputs. They are business logic.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.models.identity_verification import IdentityVerificationEvidence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DecisionResult:
    """Result of evidence evaluation.

    Attributes:
        decision: MATCH, NO_MATCH, or INCONCLUSIVE.
        reasoning: Human-readable explanation of the decision.
        policy_version: Version of the decision policy applied.
        metadata: Audit-friendly metadata (signals used, thresholds, etc.).
    """

    decision: str
    reasoning: str
    policy_version: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def evaluate_evidence(
    evidence_records: list[IdentityVerificationEvidence],
) -> tuple[str, str]:
    """Evaluate evidence records and produce a decision.

    Returns (decision, reasoning) where decision is one of:
    MATCH, NO_MATCH, INCONCLUSIVE

    This is a provider-independent decision engine.
    It interprets evidence signals — it does NOT produce evidence.

    Decision Policy:
    1. No evidence → INCONCLUSIVE
    2. Liveness FAIL → NO_MATCH (possible spoof attempt)
    3. Similarity >= threshold → MATCH (unless quality degraded → INCONCLUSIVE)
    4. Similarity >= threshold * near_threshold_factor → INCONCLUSIVE (near zone)
    5. Similarity < near zone → NO_MATCH
    6. Liveness PASS without similarity → INCONCLUSIVE
    7. Insufficient evidence → INCONCLUSIVE

    Missing evidence is NEVER silently treated as PASS or NO_MATCH.
    Provider failure is NEVER silently converted to identity mismatch.
    """
    result = evaluate_evidence_detailed(evidence_records)
    return result.decision, result.reasoning


def evaluate_evidence_detailed(
    evidence_records: list[IdentityVerificationEvidence],
) -> DecisionResult:
    """Evaluate evidence records and produce a detailed decision result.

    Like evaluate_evidence() but returns a DecisionResult with audit metadata.

    Args:
        evidence_records: List of IdentityVerificationEvidence records.

    Returns:
        DecisionResult with decision, reasoning, policy version, and metadata.
    """
    settings = get_settings()
    threshold = settings.IDENTITY_VERIFICATION_MATCH_THRESHOLD
    near_factor = settings.IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR
    policy_version = settings.IDENTITY_VERIFICATION_POLICY_VERSION
    near_threshold = threshold * near_factor

    # Collect signals from evidence
    similarity_scores: list[float] = []
    liveness_signals: list[str] = []
    quality_signals: list[str] = []
    providers_used: set[str] = set()

    for e in evidence_records:
        if e.provider_name:
            providers_used.add(e.provider_name)

        if e.signal_type == "similarity_score":
            score = _extract_numeric_signal(e)
            if score is not None:
                similarity_scores.append(score)
        elif e.signal_type == "liveness":
            if e.signal_value is not None:
                liveness_signals.append(e.signal_value)
        elif e.signal_type == "image_quality":
            if e.signal_value is not None:
                quality_signals.append(e.signal_value)

    # Build metadata for audit trail
    metadata: dict[str, Any] = {
        "threshold": threshold,
        "near_threshold_factor": near_factor,
        "near_threshold": near_threshold,
        "policy_version": policy_version,
        "similarity_scores_count": len(similarity_scores),
        "liveness_signals_count": len(liveness_signals),
        "quality_signals_count": len(quality_signals),
        "providers_used": sorted(providers_used),
    }

    if similarity_scores:
        metadata["max_similarity"] = max(similarity_scores)
        metadata["avg_similarity"] = sum(similarity_scores) / len(similarity_scores)

    # --- Decision Logic ---

    # No evidence at all
    if not evidence_records:
        return DecisionResult(
            decision="INCONCLUSIVE",
            reasoning="No evidence records available",
            policy_version=policy_version,
            metadata=metadata,
        )

    # Check liveness failure (highest priority — possible spoof)
    has_liveness_failure = any(
        s in ("FAIL", "fail", "false", "spoof_detected")
        for s in liveness_signals
    )
    if has_liveness_failure:
        metadata["decision_reason"] = "liveness_failure"
        return DecisionResult(
            decision="NO_MATCH",
            reasoning="Liveness check failed — possible spoof attempt",
            policy_version=policy_version,
            metadata=metadata,
        )

    # Check image quality issues
    has_quality_issue = any(
        s in ("POOR", "poor", "LOW", "low", "UNACCEPTABLE")
        for s in quality_signals
    )

    # Evaluate similarity scores
    if similarity_scores:
        max_similarity = max(similarity_scores)
        avg_similarity = sum(similarity_scores) / len(similarity_scores)

        if max_similarity >= threshold:
            if has_quality_issue:
                metadata["decision_reason"] = "high_similarity_but_poor_quality"
                return DecisionResult(
                    decision="INCONCLUSIVE",
                    reasoning=(
                        f"Similarity {max_similarity:.3f} exceeds threshold "
                        f"{threshold:.3f} but image quality is degraded"
                    ),
                    policy_version=policy_version,
                    metadata=metadata,
                )
            metadata["decision_reason"] = "high_similarity"
            return DecisionResult(
                decision="MATCH",
                reasoning=(
                    f"Similarity score {max_similarity:.3f} exceeds "
                    f"threshold {threshold:.3f}"
                ),
                policy_version=policy_version,
                metadata=metadata,
            )

        if avg_similarity >= near_threshold:
            metadata["decision_reason"] = "near_threshold_zone"
            return DecisionResult(
                decision="INCONCLUSIVE",
                reasoning=(
                    f"Average similarity {avg_similarity:.3f} is near "
                    f"threshold {threshold:.3f} — manual review recommended"
                ),
                policy_version=policy_version,
                metadata=metadata,
            )

        metadata["decision_reason"] = "low_similarity"
        return DecisionResult(
            decision="NO_MATCH",
            reasoning=(
                f"Similarity score {max_similarity:.3f} is below "
                f"threshold {threshold:.3f}"
            ),
            policy_version=policy_version,
            metadata=metadata,
        )

    # No similarity scores available
    if liveness_signals and not has_liveness_failure:
        metadata["decision_reason"] = "liveness_only_no_similarity"
        return DecisionResult(
            decision="INCONCLUSIVE",
            reasoning="Liveness passed but no similarity score available",
            policy_version=policy_version,
            metadata=metadata,
        )

    metadata["decision_reason"] = "insufficient_evidence"
    return DecisionResult(
        decision="INCONCLUSIVE",
        reasoning="Insufficient evidence to determine a decision",
        policy_version=policy_version,
        metadata=metadata,
    )


def _extract_numeric_signal(evidence: IdentityVerificationEvidence) -> float | None:
    """Extract a numeric value from an evidence record.

    Prefers confidence (provider-reported); falls back to signal_value string.
    """
    if evidence.confidence is not None:
        try:
            val = float(evidence.confidence)
            if 0.0 <= val <= 1.0:
                return val
        except (ValueError, TypeError):
            pass

    if evidence.signal_value is not None:
        try:
            val = float(evidence.signal_value)
            if 0.0 <= val <= 1.0:
                return val
        except (ValueError, TypeError):
            pass

    return None

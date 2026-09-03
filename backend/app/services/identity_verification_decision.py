import logging

from app.core.config import get_settings
from app.models.identity_verification import IdentityVerificationEvidence

logger = logging.getLogger(__name__)


def evaluate_evidence(
    evidence_records: list[IdentityVerificationEvidence],
) -> tuple[str, str]:
    """Evaluate evidence records and produce a decision.

    Returns (decision, reasoning) where decision is one of:
    MATCH, NO_MATCH, INCONCLUSIVE

    This is a provider-independent decision engine.
    It interprets evidence signals — it does NOT produce evidence.
    """
    settings = get_settings()
    threshold = settings.IDENTITY_VERIFICATION_MATCH_THRESHOLD

    if not evidence_records:
        return "INCONCLUSIVE", "No evidence records available"

    similarity_scores = []
    liveness_signals = []
    quality_signals = []

    for e in evidence_records:
        if e.signal_type == "similarity_score" and e.confidence is not None:
            similarity_scores.append(e.confidence)
        elif e.signal_type == "similarity_score" and e.signal_value is not None:
            try:
                similarity_scores.append(float(e.signal_value))
            except (ValueError, TypeError):
                pass
        elif e.signal_type == "liveness":
            liveness_signals.append(e.signal_value)
        elif e.signal_type == "image_quality":
            quality_signals.append(e.signal_value)

    has_liveness_failure = any(
        s in ("FAIL", "fail", "false", "spoof_detected")
        for s in liveness_signals
    )
    if has_liveness_failure:
        return "NO_MATCH", "Liveness check failed — possible spoof attempt"

    has_quality_issue = any(
        s in ("POOR", "poor", "LOW", "low", "UNACCEPTABLE")
        for s in quality_signals
    )

    if similarity_scores:
        avg_similarity = sum(similarity_scores) / len(similarity_scores)
        max_similarity = max(similarity_scores)

        if max_similarity >= threshold:
            if has_quality_issue:
                return (
                    "INCONCLUSIVE",
                    f"Similarity {max_similarity:.3f} exceeds threshold "
                    f"{threshold:.3f} but image quality is degraded",
                )
            return (
                "MATCH",
                f"Similarity score {max_similarity:.3f} exceeds "
                f"threshold {threshold:.3f}",
            )

        if avg_similarity >= threshold * 0.7:
            return (
                "INCONCLUSIVE",
                f"Average similarity {avg_similarity:.3f} is near "
                f"threshold {threshold:.3f} — manual review recommended",
            )

        return (
            "NO_MATCH",
            f"Similarity score {max_similarity:.3f} is below "
            f"threshold {threshold:.3f}",
        )

    if liveness_signals and not has_liveness_failure:
        return (
            "INCONCLUSIVE",
            "Liveness passed but no similarity score available",
        )

    return "INCONCLUSIVE", "Insufficient evidence to determine a decision"

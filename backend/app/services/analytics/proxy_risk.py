"""Proxy-risk analytics service.

Read-only aggregation over SecuritySignal and ProxyRiskAssessment domain models.
All functions use SQL-level aggregation. No business logic mutations.
Observational/reporting only. No AI claims. Pure signal aggregation.

Uses the existing RiskAssessmentResult and SecuritySignal domain models.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.proxy_risk import (
    SecuritySignal,
    ProxyRiskAssessment,
    RiskLevel,
    SIGNAL_STRENGTH_DEFAULTS,
)
from app.services.proxy_risk import (
    compute_risk_score,
    RiskAssessmentResult,
    _build_signals_summary,
)


# ---------------------------------------------------------------------------
# 1. Signal type counts across an exam
# ---------------------------------------------------------------------------


def get_signal_type_counts(db: Session, exam_id: int) -> dict:
    """Count SecuritySignal records by type for an exam.

    Args:
        db: Database session.
        exam_id: Exam ID.

    Returns:
        Dict mapping signal_type -> count.
    """
    # Join through entry_verifications to filter by exam
    from app.models.entry_verification import EntryVerification

    signal_rows = (
        db.query(SecuritySignal.signal_type,
                 func.count(SecuritySignal.id))
        .join(EntryVerification,
              SecuritySignal.entry_verification_id == EntryVerification.id)
        .filter(EntryVerification.exam_id == exam_id)
        .group_by(SecuritySignal.signal_type)
        .all()
    )

    distribution = {}
    for sig_type, count in signal_rows:
        distribution[sig_type] = count

    return {
        "exam_id": exam_id,
        "signal_type_counts": distribution,
    }


# ---------------------------------------------------------------------------
# 2. Signal strength distribution
# ---------------------------------------------------------------------------


def get_signal_strength_distribution(db: Session, exam_id: int) -> dict:
    """Count SecuritySignal records by strength for an exam.

    Args:
        db: Database session.
        exam_id: Exam ID.

    Returns:
        Dict mapping strength -> count.
    """
    from app.models.entry_verification import EntryVerification

    strength_rows = (
        db.query(SecuritySignal.strength,
                 func.count(SecuritySignal.id))
        .join(EntryVerification,
              SecuritySignal.entry_verification_id == EntryVerification.id)
        .filter(EntryVerification.exam_id == exam_id)
        .group_by(SecuritySignal.strength)
        .all()
    )

    distribution = {}
    for strength, count in strength_rows:
        distribution[strength] = count

    return {
        "exam_id": exam_id,
        "signal_strength_distribution": distribution,
    }


# ---------------------------------------------------------------------------
# 3. Risk level distribution from assessments
# ---------------------------------------------------------------------------


def get_risk_level_distribution(db: Session, exam_id: int) -> dict:
    """Count ProxyRiskAssessment records by risk level for an exam.

    Args:
        db: Database session.
        exam_id: Exam ID.

    Returns:
        Dict mapping risk_level -> count.
    """
    from app.models.entry_verification import EntryVerification

    assessment_rows = (
        db.query(ProxyRiskAssessment.risk_level,
                 func.count(ProxyRiskAssessment.id))
        .join(EntryVerification,
              ProxyRiskAssessment.entry_verification_id == EntryVerification.id)
        .filter(EntryVerification.exam_id == exam_id)
        .group_by(ProxyRiskAssessment.risk_level)
        .all()
    )

    distribution = {}
    for level, count in assessment_rows:
        distribution[str(level)] = count

    return {
        "exam_id": exam_id,
        "risk_level_distribution": distribution,
    }


# ---------------------------------------------------------------------------
# 4. Average risk score per exam
# ---------------------------------------------------------------------------


def get_average_risk_score(db: Session, exam_id: int) -> dict:
    """Get average risk score and signal counts for an exam.

    Args:
        db: Database session.
        exam_id: Exam ID.

    Returns:
        Dict with average score, total signals, assessments count.
    """
    from app.models.entry_verification import EntryVerification

    # Average risk score from assessments
    avg_result = (
        db.query(func.avg(ProxyRiskAssessment.risk_score))
        .join(EntryVerification,
              ProxyRiskAssessment.entry_verification_id == EntryVerification.id)
        .filter(EntryVerification.exam_id == exam_id)
        .scalar()
    )

    # Total signals
    total_signals = (
        db.query(func.count(SecuritySignal.id))
        .join(EntryVerification,
              SecuritySignal.entry_verification_id == EntryVerification.id)
        .filter(EntryVerification.exam_id == exam_id)
        .scalar()
    )

    # Assessment count
    assessment_count = (
        db.query(func.count(ProxyRiskAssessment.id))
        .join(EntryVerification,
              ProxyRiskAssessment.entry_verification_id == EntryVerification.id)
        .filter(EntryVerification.exam_id == exam_id)
        .scalar()
    )

    # Most common risk level
    most_common_level = (
        db.query(ProxyRiskAssessment.risk_level,
                 func.count(ProxyRiskAssessment.id))
        .join(EntryVerification,
              ProxyRiskAssessment.entry_verification_id == EntryVerification.id)
        .filter(EntryVerification.exam_id == exam_id)
        .group_by(ProxyRiskAssessment.risk_level)
        .order_by(func.count(ProxyRiskAssessment.id).desc())
        .first()
    )

    return {
        "exam_id": exam_id,
        "average_risk_score": round(float(avg_result), 2) if avg_result else 0.0,
        "total_signals": total_signals,
        "assessment_count": assessment_count,
        "most_common_risk_level": most_common_level[0] if most_common_level else None,
    }


# ---------------------------------------------------------------------------
# 5. Signal type breakdown with weights
# ---------------------------------------------------------------------------


def get_signal_breakdown_by_type(db: Session, exam_id: int) -> dict:
    """Get per-signal-type breakdown with strength counts for an exam.

    Args:
        db: Database session.
        exam_id: Exam ID.

    Returns:
        Dict mapping signal_type -> {strength_counts, total}.
    """
    from app.models.entry_verification import EntryVerification

    signal_rows = (
        db.query(SecuritySignal.signal_type,
                 SecuritySignal.strength,
                 func.count(SecuritySignal.id))
        .join(EntryVerification,
              SecuritySignal.entry_verification_id == EntryVerification.id)
        .filter(EntryVerification.exam_id == exam_id)
        .group_by(SecuritySignal.signal_type, SecuritySignal.strength)
        .all()
    )

    by_type = {}
    for sig_type, strength, count in signal_rows:
        if sig_type not in by_type:
            by_type[sig_type] = {"total": 0, "strength_counts": {}}
        by_type[sig_type]["total"] += count
        by_type[sig_type]["strength_counts"][strength] = (
            by_type[sig_type]["strength_counts"].get(strength, 0) + 1
        )

    return {
        "exam_id": exam_id,
        "signal_type_breakdown": by_type,
    }


# ---------------------------------------------------------------------------
# 6. Export: proxy risk data as dict for reporting
# ---------------------------------------------------------------------------


def export_exam_proxy_risk(db: Session, exam_id: int) -> dict:
    """Export proxy risk data for an exam as a dict suitable for reporting.

    Args:
        db: Database session.
        exam_id: Exam ID.

    Returns:
        Dict with signal counts, risk levels, and aggregation.
    """
    signal_counts = get_signal_type_counts(db, exam_id)
    strength_dist = get_signal_strength_distribution(db, exam_id)
    risk_dist = get_risk_level_distribution(db, exam_id)
    avg_score = get_average_risk_score(db, exam_id)

    return {
        "exam_id": exam_id,
        "signal_type_counts": signal_counts.get("signal_type_counts", {}),
        "signal_strength_distribution": strength_dist.get(
            "signal_strength_distribution", {}),
        "risk_level_distribution": risk_dist.get("risk_level_distribution", {}),
        "average_risk_score": avg_score.get("average_risk_score"),
        "total_signals": avg_score.get("total_signals"),
        "assessment_count": avg_score.get("assessment_count"),
        "most_common_risk_level": avg_score.get("most_common_risk_level"),
    }
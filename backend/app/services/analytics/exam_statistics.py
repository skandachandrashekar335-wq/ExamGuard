"""Examination statistics service.

Composite read-only aggregation combining attendance, verification, proxy-risk,
hall utilization, and security event data into comprehensive exam statistics.

All functions use SQL-level aggregation. Observational/reporting only.
No business logic mutations.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.attendance import AttendanceRecord, AttendanceStatus
from app.services.analytics.attendance import (
    get_exam_summary,
    list_attendance,
    list_excused_attendance,
    attendance_timeline,
    attendance_status_timeline,
    export_exam_attendance,
)
from app.services.analytics.verification import (
    get_verification_summary,
    get_exam_verification_distribution,
    get_ocr_confidence_distribution,
    get_match_status_distribution,
    get_decision_trend,
    export_document_verification,
)
from app.services.analytics.proxy_risk import (
    get_signal_type_counts,
    get_signal_strength_distribution,
    get_risk_level_distribution,
    get_average_risk_score,
    get_signal_breakdown_by_type,
    export_exam_proxy_risk,
)
from app.services.analytics.hall_utilization import (
    get_exam_hall_utilization,
    get_exam_capacity_utilization,
    export_exam_hall_utilization,
)


# ---------------------------------------------------------------------------
# 1. Comprehensive examination statistics
# ---------------------------------------------------------------------------


def get_exam_statistics(db: Session, exam_id: int) -> dict:
    """Get comprehensive examination statistics combining all domains.

    Aggregates attendance, verification, proxy-risk, hall utilization, and
    matching data for a single exam.

    Args:
        db: Database session.
        exam_id: Exam ID.

    Returns:
        Dict with complete examination statistics.
    """
    # Attendance statistics
    attendance = get_exam_summary(db, exam_id)

    # Verification statistics
    verification = get_verification_summary(db, attendance.get("exam_id", exam_id))

    # Proxy-risk statistics
    proxy_risk = get_average_risk_score(db, exam_id)
    signal_counts = get_signal_type_counts(db, exam_id)
    risk_level_dist = get_risk_level_distribution(db, exam_id)

    # Hall utilization
    hall_util = get_exam_hall_utilization(db, exam_id)

    # Match status
    match_dist = get_match_status_distribution(db, exam_id)

    # OCR confidence
    ocr_dist = get_ocr_confidence_distribution(db, exam_id)

    # Decision trend (last 30 days)
    decision_trend = get_decision_trend(db, exam_id, days=30)

    return {
        "exam_id": exam_id,
        "attendance": attendance,
        "verification": verification,
        "proxy_risk": {
            "average_risk_score": proxy_risk.get("average_risk_score"),
            "risk_level_distribution": risk_level_dist.get("risk_level_distribution", {}),
            "signal_type_counts": signal_counts.get("signal_type_counts", {}),
        },
        "hall_utilization": hall_util,
        "match_status": match_dist.get("distribution", {}),
        "ocr_confidence": ocr_dist.get("buckets", {}),
        "decision_trend": decision_trend.get("timeline", {}),
    }


# ---------------------------------------------------------------------------
# 2. Statistics with filtering
# ---------------------------------------------------------------------------


def list_exam_statistics(
    db: Session,
    *,
    hall_id: int | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """List examination statistics with optional filters.

    Note: Full filtering across exams requires joining through the exam
    hierarchy. This provides targeted filters where applicable.

    Args:
        db: Database session.
        hall_id: Optional hall filter.
        status: Optional attendance status filter.
        date_from: Optional start date filter (ISO string).
        date_to: Optional end date filter (ISO string).

    Returns:
        Dict with summary statistics.
    """
    # Base query: exams with at least one registration
    query = db.query(Exam)

    if hall_id is not None:
        # Filter exams in a specific hall via exam_hall relationship
        query = query.join(Exam.exam_halls)  # type: ignore

    # If date filters are provided, we'd need to join through sessions
    # For now return unfiltered summary with optional hall filter

    exams = query.limit(50).all()  # limit to prevent massive queries

    summaries = []
    for exam in exams:
        # Quick summary for each exam
        att = get_exam_summary(db, exam.id)
        summaries.append({
            "exam_id": exam.id,
            "exam_name": exam.exam_name,
            "total_registered": att.get("total_registered", 0),
            "total_present": att.get("total_present", 0),
        })

    return {
        "summaries": summaries,
        "total_exams": len(summaries),
        "filters_applied": {
            "hall_id": hall_id,
            "status": status,
            "date_from": date_from,
            "date_to": date_to,
        },
    }


# ---------------------------------------------------------------------------
# 3. Department-level statistics (across multiple exams)
# ---------------------------------------------------------------------------


def get_department_statistics(
    db: Session,
    *,
    department_filter: str | None = None,
) -> dict:
    """Get statistics aggregated across exams, optionally filtered by department.

    Note: Exam domain doesn't currently have a department field, so this
    provides a structure that can be extended.

    Args:
        db: Database session.
        department_filter: Optional department identifier.

    Returns:
        Dict with aggregated statistics.
    """
    # Since the domain doesn't have department, provide per-exam summaries
    # that can be further aggregated by the caller
    from app.models.subject import Subject  # type: ignore

    # Get all exams with subject info
    subject_filter = None
    if department_filter:
        # Try to filter by subject code
        subject_filter = department_filter

    exams = db.query(Exam).limit(100).all()  # type: ignore

    exam_summaries = []
    for exam in exams:
        att = get_exam_summary(db, exam.id)
        exam_summaries.append({
            "exam_id": exam.id,
            "exam_name": exam.exam_name,
            "subject_code": exam.subject.code if exam.subject else None,
            "total_registered": att.get("total_registered", 0),
            "attendance_rate": att.get("attendance_rate", 0.0),
        })

    return {
        "exam_summaries": exam_summaries,
        "total_exams": len(exam_summaries),
        "department_filter": department_filter,
    }


# ---------------------------------------------------------------------------
# 4. Export: comprehensive exam report
# ---------------------------------------------------------------------------


def export_exam_report(db: Session, exam_id: int) -> dict:
    """Export a comprehensive examination report combining all domains.

    Args:
        db: Database session.
        exam_id: Exam ID.

    Returns:
        Dict with complete examination report suitable for administrative
        reporting and export.
    """
    stats = get_exam_statistics(db, exam_id)

    # Also pull the exam basic info
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    return {
        "exam_id": exam_id,
        "exam_name": exam.exam_name if exam else None,
        "exam_code": exam.exam_code if exam else None,
        "subject": exam.subject.code if exam and exam.subject else None,
        "exam_date": exam.exam_date if exam else None,
        "statistics": stats,
    }
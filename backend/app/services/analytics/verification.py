"""Verification analytics service.

Read-only aggregation over verification domain models (Document, ExtractionResult,
HallTicketMatchResult, VerificationOutcome). All functions use SQL-level aggregation.
No business logic mutations. Observational/reporting only.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.models.extraction import ExtractionResult, ExtractionStatus
from app.models.hall_ticket_match import HallTicketMatchResult
from app.models.verification import VerificationDecision, VerificationOutcome
from app.models.exam import Exam


# ---------------------------------------------------------------------------
# 1. Expanded verification summary for a document
# ---------------------------------------------------------------------------


def get_verification_summary(db: Session, document_id: int) -> dict:
    """Get comprehensive verification summary for a document.

    Returns dict with extraction status, match status, review status,
    decision, OCR confidence, blocking reasons, and timestamps.

    Raises:
        LookupError: If document not found.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise LookupError(f"Document {document_id} not found")

    extraction_result = (
        db.query(ExtractionResult)
        .filter(ExtractionResult.document_id == document_id)
        .order_by(ExtractionResult.id.desc())
        .first()
    )

    match_result = (
        db.query(HallTicketMatchResult)
        .filter(HallTicketMatchResult.document_id == document_id)
        .order_by(HallTicketMatchResult.id.desc())
        .first()
    )

    from app.services.verification import (
        _check_extraction,
        _check_match,
        _check_review,
    )

    extraction_check, extraction_reason = _check_extraction(extraction_result)
    match_check, match_status, match_reason = _check_match(match_result)
    review_completed, review_status = _check_review(extraction_result)

    blocking_reasons = []
    if extraction_reason:
        blocking_reasons.append(extraction_reason)
    if match_reason:
        blocking_reasons.append(match_reason)

    can_verify = (
        extraction_check == "PASSED"
        and match_check == "PASSED"
        and not blocking_reasons
    )

    # Count related verification outcomes
    total_outcomes = db.query(func.count(VerificationOutcome.id)).filter(
        VerificationOutcome.document_id == document_id
    ).scalar()

    latest_outcome = db.query(VerificationOutcome).filter(
        VerificationOutcome.document_id == document_id
    ).order_by(VerificationOutcome.id.desc()).first()

    decision_distribution = (
        db.query(VerificationOutcome.decision, func.count(VerificationOutcome.id))
        .filter(VerificationOutcome.document_id == document_id)
        .group_by(VerificationOutcome.decision)
        .all()
    )

    decision_map = {}
    for dec, count in decision_distribution:
        decision_map[dec] = count

    return {
        "document_id": document_id,
        "exam_id": document.exam_id if document else None,
        "has_extraction": extraction_result is not None,
        "has_match": match_result is not None,
        "extraction_check": extraction_check,
        "extraction_reason": extraction_reason,
        "match_check": match_check,
        "match_status": match_status,
        "match_reason": match_reason,
        "review_status": review_status,
        "review_completed": review_completed,
        "ocr_avg_confidence": extraction_result.ocr_avg_confidence if extraction_result else None,
        "match_overall_status": match_result.overall_status if match_result else None,
        "can_verify": can_verify,
        "blocking_reasons": blocking_reasons,
        "total_verification_outcomes": total_outcomes,
        "latest_decision": latest_outcome.decision if latest_outcome else None,
        "decision_distribution": decision_map,
        "document_status": document.status.value if document else None,
    }


# ---------------------------------------------------------------------------
# 2. Verification status distribution across an exam
# ---------------------------------------------------------------------------


def get_exam_verification_distribution(db: Session, exam_id: int) -> dict:
    """Get verification decision distribution across all documents in an exam.

    Args:
        db: Database session.
        exam_id: Exam ID.

    Returns:
        Dict with decision counts and percentages.
    """
    total = db.query(func.count(Document.id)).filter(Document.exam_id == exam_id).scalar()

    decision_rows = (
        db.query(VerificationOutcome.decision, func.count(VerificationOutcome.id))
        .join(Document, VerificationOutcome.document_id == Document.id)
        .filter(Document.exam_id == exam_id)
        .group_by(VerificationOutcome.decision)
        .all()
    )

    decision_map = {}
    for dec, count in decision_rows:
        decision_map[dec] = count

    # Calculate percentages
    distribution = {}
    for decision in [VerificationDecision.VERIFIED.value,
                     VerificationDecision.REVIEW_REQUIRED.value,
                     VerificationDecision.FAILED.value,
                     VerificationDecision.INCOMPLETE.value]:
        count = decision_map.get(decision, 0)
        pct = round(count / total * 100, 1) if total > 0 else 0.0
        distribution[decision] = {"count": count, "percentage": pct}

    return {
        "exam_id": exam_id,
        "total_documents": total,
        "distribution": distribution,
    }


# ---------------------------------------------------------------------------
# 2b. OCR confidence distribution
# ---------------------------------------------------------------------------


def get_ocr_confidence_distribution(db: Session, exam_id: int) -> dict:
    """Get OCR confidence score distribution for an exam.

    Args:
        db: Database session.
        exam_id: Exam ID.

    Returns:
        Dict with confidence range buckets and counts.
    """
    # Pull latest extraction result per document
    latest_extraction = (
        db.query(ExtractionResult.document_id,
                 func.max(ExtractionResult.id).label("max_id"))
        .filter(ExtractionResult.exam_id == exam_id)
        .group_by(ExtractionResult.document_id)
        .subquery()
    )

    # Join to get confidence scores
    rows = (
        db.query(ExtractionResult.ocr_avg_confidence,
                 ExtractionResult.document_id)
        .join(latest_extraction,
              ExtractionResult.id == latest_extraction.c.max_id)
        .filter(ExtractionResult.exam_id == exam_id)
        .filter(ExtractionResult.ocr_avg_confidence.isnot(None))
        .all()
    )

    # Bucket confidences
    buckets = {
        "90-100": 0,
        "80-89": 0,
        "70-79": 0,
        "60-69": 0,
        "below-60": 0,
    }

    for conf, doc_id in rows:
        if conf >= 90:
            buckets["90-100"] += 1
        elif conf >= 80:
            buckets["80-89"] += 1
        elif conf >= 70:
            buckets["70-79"] += 1
        elif conf >= 60:
            buckets["60-69"] += 1
        else:
            buckets["below-60"] += 1

    return {
        "exam_id": exam_id,
        "buckets": buckets,
        "total_documents_with_ocr": len(buckets),
    }


# ---------------------------------------------------------------------------
# 3. Match status distribution
# ---------------------------------------------------------------------------


def get_match_status_distribution(db: Session, exam_id: int) -> dict:
    """Get hall-ticket match status distribution for an exam.

    Args:
        db: Database session.
        exam_id: Exam ID.

    Returns:
        Dict with match status counts.
    """
    rows = (
        db.query(HallTicketMatchResult.overall_status,
                 func.count(HallTicketMatchResult.id))
        .filter(HallTicketMatchResult.exam_id == exam_id)
        .group_by(HallTicketMatchResult.overall_status)
        .all()
    )

    distribution = {}
    for status, count in rows:
        distribution[status] = count

    return {
        "exam_id": exam_id,
        "distribution": distribution,
    }


# ---------------------------------------------------------------------------
# 4. Decision trend across time (for an exam or across exams)
# ---------------------------------------------------------------------------


def get_decision_trend(db: Session, exam_id: int | None = None,
                      *,
                      days: int = 30) -> dict:
    """Get verification decision trend over time.

    Args:
        db: Database session.
        exam_id: Optional exam filter. If None, aggregates across all exams.
        days: Look-back window in days.

    Returns:
        Dict with daily decision counts.
    """
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    if exam_id:
        query = db.query(
            func.date(VerificationOutcome.created_at).label("date"),
            VerificationOutcome.decision,
            func.count(VerificationOutcome.id).label("count"),
        ).filter(
            VerificationOutcome.exam_id == exam_id,
            VerificationOutcome.created_at >= cutoff,
        )
    else:
        query = db.query(
            func.date(VerificationOutcome.created_at).label("date"),
            VerificationOutcome.decision,
            func.count(VerificationOutcome.id).label("count"),
        ).filter(
            VerificationOutcome.created_at >= cutoff,
        )

    rows = query.group_by(func.date(VerificationOutcome.created_at),
                         VerificationOutcome.decision).all()

    by_day = {}
    for row in rows:
        date_str = str(row.date)
        if date_str not in by_day:
            by_day[date_str] = {}
        by_day[date_str][row.decision] = row.count

    return {
        "exam_id": exam_id,
        "window_days": days,
        "timeline": by_day,
    }


# ---------------------------------------------------------------------------
# 5. Export: verification data as dict for reporting
# ---------------------------------------------------------------------------


def export_document_verification(
    db: Session,
    document_id: int,
) -> dict:
    """Export verification data for a document as a dict suitable for reporting.

    Args:
        db: Database session.
        document_id: Document ID.

    Returns:
        Dict with full verification state.
    """
    from app.services.verification import get_verification_summary

    summary = get_verification_summary(db, document_id)

    # Also pull the document info
    from app.models.document import Document
    document = db.query(Document).filter(Document.id == document_id).first()

    return {
        "document_id": document_id,
        "exam_id": document.exam_id if document else None,
        "document_status": document.status.value if document else None,
        "verification": summary,
    }
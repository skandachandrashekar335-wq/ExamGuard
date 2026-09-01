import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document, DocumentStatus
from app.models.extraction import ExtractionResult, ExtractionStatus
from app.models.hall_ticket_match import HallTicketMatchResult
from app.models.verification import VerificationDecision, VerificationOutcome

logger = logging.getLogger(__name__)

settings = get_settings()


def _check_extraction(extraction_result: ExtractionResult | None) -> tuple[str, str | None]:
    if extraction_result is None:
        return "NOT_AVAILABLE", "No extraction result found"

    if extraction_result.status == ExtractionStatus.FAILED.value:
        return "FAILED", "Extraction processing failed"

    if extraction_result.status == ExtractionStatus.PENDING.value:
        return "NOT_AVAILABLE", "Extraction not yet processed"

    if extraction_result.status == ExtractionStatus.REVIEW_REQUIRED.value:
        return "NEEDS_REVIEW", "Extraction has fields requiring review"

    return "PASSED", None


def _check_match(
    match_result: HallTicketMatchResult | None,
) -> tuple[str, str | None, str | None]:
    if match_result is None:
        return "NOT_AVAILABLE", None, "No match result found"

    status = match_result.overall_status

    if status == "MATCHED":
        return "PASSED", status, None
    elif status == "PARTIAL_MATCH":
        return "NEEDS_REVIEW", status, "Partial match — some fields did not match"
    elif status == "NOT_FOUND":
        return "FAILED", status, "Student or exam records not found"
    elif status == "MISMATCH":
        return "FAILED", status, "Critical field mismatch"
    else:
        return "NEEDS_REVIEW", status, f"Match status: {status}"


def _check_review(extraction_result: ExtractionResult | None) -> tuple[bool, str]:
    if extraction_result is None:
        return False, "NOT_AVAILABLE"

    if extraction_result.status == ExtractionStatus.REVIEW_REQUIRED.value:
        return False, "REVIEW_REQUIRED"

    if extraction_result.reviewed_at is not None:
        return True, "COMPLETED"

    return False, "NOT_STARTED"


def _determine_decision(
    extraction_check: str,
    match_check: str,
    review_completed: bool,
    ocr_avg_confidence: float | None,
) -> tuple[str, str]:
    if extraction_check == "NOT_AVAILABLE":
        return VerificationDecision.INCOMPLETE.value, "Extraction not available"

    if extraction_check == "FAILED":
        return VerificationDecision.FAILED.value, "Extraction failed"

    if match_check == "NOT_AVAILABLE":
        return VerificationDecision.INCOMPLETE.value, "Match result not available"

    if match_check == "FAILED":
        return VerificationDecision.FAILED.value, "Domain matching failed"

    if match_check == "NEEDS_REVIEW" or extraction_check == "NEEDS_REVIEW":
        return (
            VerificationDecision.REVIEW_REQUIRED.value,
            "Matching or extraction produced uncertain results requiring review",
        )

    if ocr_avg_confidence is not None and ocr_avg_confidence < settings.MIN_OCR_CONFIDENCE:
        return (
            VerificationDecision.REVIEW_REQUIRED.value,
            f"OCR confidence {ocr_avg_confidence:.1f}% is below threshold "
            f"{settings.MIN_OCR_CONFIDENCE:.1f}%",
        )

    if match_check == "PASSED" and extraction_check == "PASSED":
        return VerificationDecision.VERIFIED.value, "All checks passed"

    return VerificationDecision.REVIEW_REQUIRED.value, "Unable to determine verification status"


def get_verification_summary(db: Session, document_id: int) -> dict:
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

    return {
        "document_id": document_id,
        "has_extraction": extraction_result is not None,
        "has_match": match_result is not None,
        "extraction_check": extraction_check,
        "match_check": match_check,
        "review_check": review_status,
        "ocr_avg_confidence": extraction_result.ocr_avg_confidence if extraction_result else None,
        "match_status": match_result.overall_status if match_result else None,
        "review_completed": review_completed,
        "can_verify": can_verify,
        "blocking_reasons": blocking_reasons,
    }


def run_verification(db: Session, document_id: int) -> VerificationOutcome:
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

    extraction_check, extraction_reason = _check_extraction(extraction_result)
    match_check, match_status, match_reason = _check_match(match_result)
    review_completed, review_status = _check_review(extraction_result)

    decision, reasoning = _determine_decision(
        extraction_check,
        match_check,
        review_completed,
        extraction_result.ocr_avg_confidence if extraction_result else None,
    )

    outcome = VerificationOutcome(
        document_id=document_id,
        extraction_result_id=extraction_result.id if extraction_result else None,
        match_result_id=match_result.id if match_result else None,
        student_id=match_result.student_id if match_result else None,
        exam_id=match_result.exam_id if match_result else None,
        decision=decision,
        extraction_check=extraction_check,
        match_check=match_check,
        review_check=review_status,
        ocr_avg_confidence=extraction_result.ocr_avg_confidence if extraction_result else None,
        match_status=match_result.overall_status if match_result else None,
        review_completed=review_completed,
        reasoning=reasoning,
    )
    db.add(outcome)
    db.commit()
    db.refresh(outcome)
    return outcome


def get_latest_outcome(db: Session, document_id: int) -> VerificationOutcome | None:
    return (
        db.query(VerificationOutcome)
        .filter(VerificationOutcome.document_id == document_id)
        .order_by(VerificationOutcome.id.desc())
        .first()
    )


def get_outcome(db: Session, outcome_id: int) -> VerificationOutcome | None:
    return (
        db.query(VerificationOutcome)
        .filter(VerificationOutcome.id == outcome_id)
        .first()
    )

import logging

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.models.extraction import ExtractionResult, ExtractionStatus
from app.models.hall_ticket_match import HallTicketMatchResult
from app.models.verification import VerificationDecision, VerificationOutcome

logger = logging.getLogger(__name__)


def _process_single(db: Session, document: Document) -> dict:
    from app.services.processing import process_document

    try:
        result = process_document(db, document.id)
        return {
            "document_id": document.id,
            "step": "extraction",
            "status": "completed",
            "extraction_result_id": result.id,
            "ocr_avg_confidence": result.ocr_avg_confidence,
        }
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        return {
            "document_id": document.id,
            "step": "extraction",
            "status": "failed",
            "error": str(e),
        }


def _match_single(db: Session, document: Document) -> dict:
    from app.services.hall_ticket_matching import match_hall_ticket

    try:
        result = match_hall_ticket(db, document.id)
        return {
            "document_id": document.id,
            "step": "matching",
            "status": "completed",
            "match_result_id": result.id,
            "overall_status": result.overall_status,
        }
    except (LookupError, ValueError) as e:
        return {
            "document_id": document.id,
            "step": "matching",
            "status": "failed",
            "error": str(e),
        }


def _verify_single(db: Session, document: Document) -> dict:
    from app.services.verification import run_verification

    try:
        outcome = run_verification(db, document.id)
        return {
            "document_id": document.id,
            "step": "verification",
            "status": "completed",
            "outcome_id": outcome.id,
            "decision": outcome.decision,
        }
    except LookupError as e:
        return {
            "document_id": document.id,
            "step": "verification",
            "status": "failed",
            "error": str(e),
        }


def batch_verify(db: Session, document_ids: list[int]) -> dict:
    results = []
    processed = 0
    matched = 0
    verified = 0
    failed = 0

    for doc_id in document_ids:
        document = db.query(Document).filter(Document.id == doc_id).first()
        if not document:
            results.append({
                "document_id": doc_id,
                "step": "lookup",
                "status": "failed",
                "error": f"Document {doc_id} not found",
            })
            failed += 1
            continue

        extraction_result = (
            db.query(ExtractionResult)
            .filter(ExtractionResult.document_id == doc_id)
            .order_by(ExtractionResult.id.desc())
            .first()
        )

        match_result = (
            db.query(HallTicketMatchResult)
            .filter(HallTicketMatchResult.document_id == doc_id)
            .order_by(HallTicketMatchResult.id.desc())
            .first()
        )

        existing_outcome = (
            db.query(VerificationOutcome)
            .filter(VerificationOutcome.document_id == doc_id)
            .order_by(VerificationOutcome.id.desc())
            .first()
        )

        if existing_outcome is not None:
            results.append({
                "document_id": doc_id,
                "step": "verification",
                "status": "completed",
                "outcome_id": existing_outcome.id,
                "decision": existing_outcome.decision,
            })
            continue

        step_result = None

        if extraction_result is None:
            step_result = _process_single(db, document)
            if step_result["status"] == "completed":
                processed += 1
            else:
                failed += 1
                results.append(step_result)
                continue

        if match_result is None:
            step_result = _match_single(db, document)
            if step_result["status"] == "completed":
                matched += 1
            else:
                failed += 1
                results.append(step_result)
                continue

        step_result = _verify_single(db, document)
        if step_result["status"] == "completed":
            verified += 1
        else:
            failed += 1

        results.append(step_result)

    return {
        "total": len(document_ids),
        "processed": processed,
        "matched": matched,
        "verified": verified,
        "failed": failed,
        "results": results,
    }

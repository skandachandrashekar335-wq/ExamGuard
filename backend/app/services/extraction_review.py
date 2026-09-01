import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.models.extraction import (
    ExtractedField,
    ExtractionResult,
    ExtractionStatus,
    ReviewStatus,
)

logger = logging.getLogger(__name__)


def get_review_data(db: Session, document_id: int) -> dict:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise LookupError(f"Document {document_id} not found")

    extraction_result = (
        db.query(ExtractionResult)
        .filter(ExtractionResult.document_id == document_id)
        .order_by(ExtractionResult.id.desc())
        .first()
    )
    if not extraction_result:
        raise LookupError(f"No extraction results found for document {document_id}")

    fields = (
        db.query(ExtractedField)
        .filter(ExtractedField.extraction_result_id == extraction_result.id)
        .order_by(ExtractedField.id)
        .all()
    )

    total_fields = len(fields)
    reviewed_count = sum(
        1 for f in fields if f.review_status == ReviewStatus.REVIEWED.value
    )
    review_required_count = sum(
        1 for f in fields if f.review_status == ReviewStatus.REVIEW_REQUIRED.value
    )

    return {
        "extraction_result": extraction_result,
        "fields": fields,
        "progress": {
            "total_fields": total_fields,
            "reviewed_count": reviewed_count,
            "review_required_count": review_required_count,
        },
    }


def correct_field(
    db: Session,
    document_id: int,
    field_id: int,
    corrected_value: str,
    review_status: str = ReviewStatus.REVIEWED.value,
) -> ExtractedField:
    extraction_result = (
        db.query(ExtractionResult)
        .filter(ExtractionResult.document_id == document_id)
        .order_by(ExtractionResult.id.desc())
        .first()
    )
    if not extraction_result:
        raise LookupError(f"No extraction results found for document {document_id}")

    field = (
        db.query(ExtractedField)
        .filter(
            ExtractedField.id == field_id,
            ExtractedField.extraction_result_id == extraction_result.id,
        )
        .first()
    )
    if not field:
        raise LookupError(
            f"Field {field_id} not found in extraction result {extraction_result.id}"
        )

    valid_statuses = {s.value for s in ReviewStatus}
    if review_status not in valid_statuses:
        raise ValueError(
            f"Invalid review_status '{review_status}'. "
            f"Must be one of: {', '.join(sorted(valid_statuses))}"
        )

    field.corrected_value = corrected_value
    field.review_status = review_status
    db.commit()
    db.refresh(field)
    return field


def complete_review(db: Session, document_id: int) -> ExtractionResult:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise LookupError(f"Document {document_id} not found")

    extraction_result = (
        db.query(ExtractionResult)
        .filter(ExtractionResult.document_id == document_id)
        .order_by(ExtractionResult.id.desc())
        .first()
    )
    if not extraction_result:
        raise LookupError(f"No extraction results found for document {document_id}")

    fields = (
        db.query(ExtractedField)
        .filter(ExtractedField.extraction_result_id == extraction_result.id)
        .all()
    )

    remaining = sum(
        1 for f in fields if f.review_status == ReviewStatus.REVIEW_REQUIRED.value
    )
    if remaining > 0:
        raise ValueError(
            f"{remaining} field(s) still require review. "
            f"Review all fields before completing."
        )

    extraction_result.reviewed_at = datetime.now(timezone.utc)
    extraction_result.status = ExtractionStatus.COMPLETED.value

    document.status = DocumentStatus.PROCESSED

    db.commit()
    db.refresh(extraction_result)
    return extraction_result

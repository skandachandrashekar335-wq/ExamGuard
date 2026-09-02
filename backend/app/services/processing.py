import logging
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.base import DocumentProcessor
from app.ai.extraction_base import ExtractionOutput
from app.ai.rule_extractor import RuleBasedFieldExtractor
from app.ai.tesseract_processor import TesseractDocumentProcessor
from app.core.config import get_settings
from app.models.document import Document, DocumentStatus
from app.models.extraction import ExtractedField, ExtractionResult, ExtractionStatus, ReviewStatus
from app.storage.local import LocalStorage

logger = logging.getLogger(__name__)

settings = get_settings()


def get_processor() -> DocumentProcessor:
    return TesseractDocumentProcessor()


def process_document(db: Session, document_id: int) -> ExtractionResult:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise LookupError(f"Document {document_id} not found")

    if document.status not in (DocumentStatus.UPLOADED, DocumentStatus.READY_FOR_PROCESSING, DocumentStatus.FAILED):
        raise ValueError(f"Document {document_id} is not eligible for processing (status: {document.status})")

    document.status = DocumentStatus.PROCESSING
    db.commit()

    processor = get_processor()
    if not processor.is_available():
        document.status = DocumentStatus.FAILED
        db.commit()
        raise RuntimeError("OCR processor is not available. Check Tesseract installation and TESSERACT_CMD config.")

    storage = LocalStorage(settings.UPLOAD_DIR)
    try:
        file_path = storage.get_path(document.stored_key)
    except FileNotFoundError:
        document.status = DocumentStatus.FAILED
        db.commit()
        raise

    start_time = time.time()

    try:
        ocr_results = _run_ocr(processor, file_path, document.content_type)
    except Exception as e:
        logger.error("OCR failed for document %d: %s", document_id, e)
        document.status = DocumentStatus.FAILED
        db.commit()
        raise RuntimeError(f"OCR processing failed: {e}") from e

    extractor = RuleBasedFieldExtractor()
    extraction_output = extractor.extract(ocr_results)

    elapsed_ms = int((time.time() - start_time) * 1000)

    avg_ocr_conf = (
        sum(r.avg_confidence for r in ocr_results) / len(ocr_results)
        if ocr_results
        else 0.0
    )

    raw_text = "\n\n--- Page Break ---\n\n".join(r.text for r in ocr_results)

    extraction_result = ExtractionResult(
        document_id=document_id,
        raw_ocr_text=raw_text,
        ocr_engine=ocr_results[0].engine if ocr_results else "unknown",
        ocr_avg_confidence=avg_ocr_conf,
        processing_time_ms=elapsed_ms,
        status=ExtractionStatus.COMPLETED,
    )
    db.add(extraction_result)
    db.flush()

    for field_data in extraction_output.fields:
        review_status = ReviewStatus.AUTO_APPROVED
        if field_data.extracted_value is None or not field_data.label_found:
            review_status = ReviewStatus.REVIEW_REQUIRED

        extracted_field = ExtractedField(
            extraction_result_id=extraction_result.id,
            field_name=field_data.field_name,
            extracted_value=field_data.extracted_value,
            ocr_confidence=field_data.ocr_confidence,
            pattern_match=field_data.pattern_match,
            label_found=field_data.label_found,
            database_match=field_data.database_match,
            extraction_method=field_data.extraction_method,
            validation_status="VALID" if field_data.extracted_value else "MISSING",
            review_status=review_status.value,
        )
        db.add(extracted_field)

    has_uncertain = any(
        f.review_status == ReviewStatus.REVIEW_REQUIRED.value
        for f in db.query(ExtractedField).filter(
            ExtractedField.extraction_result_id == extraction_result.id
        ).all()
    )

    document.status = (
        DocumentStatus.REVIEW_REQUIRED if has_uncertain else DocumentStatus.PROCESSED
    )
    extraction_result.status = (
        ExtractionStatus.REVIEW_REQUIRED if has_uncertain else ExtractionStatus.COMPLETED
    )

    db.commit()
    db.refresh(extraction_result)

    from app.services import hall_ticket as ht_service
    ht_service.on_extraction_complete(db, document_id, extraction_result.id)

    return extraction_result


def _run_ocr(processor: DocumentProcessor, file_path: str, content_type: str):
    if content_type == "application/pdf":
        return processor.process_pdf(file_path)
    else:
        return [processor.process_image(file_path)]


def get_extraction_result(db: Session, document_id: int) -> ExtractionResult | None:
    return (
        db.query(ExtractionResult)
        .filter(ExtractionResult.document_id == document_id)
        .order_by(ExtractionResult.id.desc())
        .first()
    )


def get_extracted_fields(db: Session, extraction_result_id: int) -> list[ExtractedField]:
    return (
        db.query(ExtractedField)
        .filter(ExtractedField.extraction_result_id == extraction_result_id)
        .order_by(ExtractedField.id)
        .all()
    )

import pytest

from app.models.extraction import ExtractedField, ExtractionResult, ExtractionStatus, ReviewStatus


class TestExtractionStatus:
    def test_pending_value(self):
        assert ExtractionStatus.PENDING == "PENDING"

    def test_completed_value(self):
        assert ExtractionStatus.COMPLETED == "COMPLETED"

    def test_failed_value(self):
        assert ExtractionStatus.FAILED == "FAILED"

    def test_review_required_value(self):
        assert ExtractionStatus.REVIEW_REQUIRED == "REVIEW_REQUIRED"


class TestReviewStatus:
    def test_auto_approved_value(self):
        assert ReviewStatus.AUTO_APPROVED == "AUTO_APPROVED"

    def test_review_required_value(self):
        assert ReviewStatus.REVIEW_REQUIRED == "REVIEW_REQUIRED"

    def test_reviewed_value(self):
        assert ReviewStatus.REVIEWED == "REVIEWED"


class TestExtractionResultModel:
    def test_create_extraction_result(self, db_session):
        from app.models.document import Document
        from datetime import datetime

        doc = Document(
            original_filename="test.pdf",
            stored_key="documents/test.pdf",
            content_type="application/pdf",
            file_size=1024,
            document_type="HALL_TICKET",
            status="PROCESSED",
        )
        db_session.add(doc)
        db_session.flush()

        result = ExtractionResult(
            document_id=doc.id,
            raw_ocr_text="Sample OCR text",
            ocr_engine="tesseract5",
            ocr_avg_confidence=85.5,
            processing_time_ms=1200,
            status=ExtractionStatus.COMPLETED,
        )
        db_session.add(result)
        db_session.flush()

        assert result.id is not None
        assert result.document_id == doc.id
        assert result.ocr_engine == "tesseract5"
        assert result.ocr_avg_confidence == 85.5
        assert result.status == ExtractionStatus.COMPLETED

    def test_create_extracted_field(self, db_session):
        from app.models.document import Document
        from datetime import datetime

        doc = Document(
            original_filename="test.pdf",
            stored_key="documents/test.pdf",
            content_type="application/pdf",
            file_size=1024,
            document_type="HALL_TICKET",
            status="PROCESSED",
        )
        db_session.add(doc)
        db_session.flush()

        result = ExtractionResult(
            document_id=doc.id,
            raw_ocr_text="Sample OCR text",
            ocr_engine="tesseract5",
            ocr_avg_confidence=85.5,
            processing_time_ms=1200,
            status=ExtractionStatus.COMPLETED,
        )
        db_session.add(result)
        db_session.flush()

        field = ExtractedField(
            extraction_result_id=result.id,
            field_name="usn",
            extracted_value="1RV21CS001",
            ocr_confidence=92.0,
            pattern_match=True,
            label_found=True,
            extraction_method="labeled_regex",
            validation_status="VALID",
            review_status=ReviewStatus.AUTO_APPROVED,
        )
        db_session.add(field)
        db_session.flush()

        assert field.id is not None
        assert field.field_name == "usn"
        assert field.extracted_value == "1RV21CS001"
        assert field.ocr_confidence == 92.0
        assert field.pattern_match is True
        assert field.label_found is True
        assert field.validation_status == "VALID"
        assert field.review_status == ReviewStatus.AUTO_APPROVED

    def test_extraction_result_defaults(self, db_session):
        from app.models.document import Document

        doc = Document(
            original_filename="test.pdf",
            stored_key="documents/test.pdf",
            content_type="application/pdf",
            file_size=1024,
            document_type="HALL_TICKET",
            status="PROCESSED",
        )
        db_session.add(doc)
        db_session.flush()

        result = ExtractionResult(
            document_id=doc.id,
            ocr_engine="tesseract5",
            ocr_avg_confidence=0.0,
        )
        db_session.add(result)
        db_session.flush()

        assert result.status == ExtractionStatus.PENDING
        assert result.raw_ocr_text is None
        assert result.processing_time_ms is None

    def test_extracted_field_nullable_fields(self, db_session):
        from app.models.document import Document

        doc = Document(
            original_filename="test.pdf",
            stored_key="documents/test.pdf",
            content_type="application/pdf",
            file_size=1024,
            document_type="HALL_TICKET",
            status="PROCESSED",
        )
        db_session.add(doc)
        db_session.flush()

        result = ExtractionResult(
            document_id=doc.id,
            ocr_engine="tesseract5",
            ocr_avg_confidence=0.0,
        )
        db_session.add(result)
        db_session.flush()

        field = ExtractedField(
            extraction_result_id=result.id,
            field_name="unknown_field",
            validation_status="MISSING",
            review_status=ReviewStatus.REVIEW_REQUIRED,
        )
        db_session.add(field)
        db_session.flush()

        assert field.extracted_value is None
        assert field.corrected_value is None
        assert field.ocr_confidence is None
        assert field.pattern_match is None
        assert field.label_found is None
        assert field.database_match is None
        assert field.extraction_method is None

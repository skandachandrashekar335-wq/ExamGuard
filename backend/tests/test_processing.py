import os
import shutil
from unittest.mock import MagicMock, patch

import pytest

from app.ai.base import OCRResult, OCRWord
from app.models.document import Document
from app.models.extraction import ExtractedField, ExtractionResult, ExtractionStatus
from app.services import processing


@pytest.fixture(autouse=True)
def cleanup_documents(db_session):
    db_session.query(ExtractedField).delete()
    db_session.query(ExtractionResult).delete()
    db_session.query(Document).delete()
    db_session.commit()
    yield
    db_session.query(ExtractedField).delete()
    db_session.query(ExtractionResult).delete()
    db_session.query(Document).delete()
    db_session.commit()


class TestProcessDocument:
    def test_process_document_not_found(self, db_session):
        with pytest.raises(LookupError, match="not found"):
            processing.process_document(db_session, 999999)

    def test_process_document_wrong_status(self, db_session, tmp_path):
        doc = Document(
            original_filename="test.pdf",
            stored_key="documents/test.pdf",
            content_type="application/pdf",
            file_size=1024,
            document_type="HALL_TICKET",
            status="PROCESSING",
        )
        db_session.add(doc)
        db_session.flush()

        with pytest.raises(ValueError, match="not eligible"):
            processing.process_document(db_session, doc.id)

    def test_process_document_success(self, db_session, tmp_path):
        doc = Document(
            original_filename="test.pdf",
            stored_key="documents/test.pdf",
            content_type="application/pdf",
            file_size=1024,
            document_type="HALL_TICKET",
            status="READY_FOR_PROCESSING",
        )
        db_session.add(doc)
        db_session.flush()

        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake content")

        mock_result = OCRResult(
            text="Name: John Doe\nUSN: 1RV21CS001",
            words=[
                OCRWord(text="Name:", confidence=95.0, x=0, y=0, width=60, height=20, page=0),
                OCRWord(text="John", confidence=98.0, x=60, y=0, width=50, height=20, page=0),
                OCRWord(text="Doe", confidence=98.0, x=110, y=0, width=40, height=20, page=0),
                OCRWord(text="USN:", confidence=95.0, x=0, y=40, width=50, height=20, page=0),
                OCRWord(text="1RV21CS001", confidence=98.0, x=50, y=40, width=100, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
            avg_confidence=96.4,
        )

        mock_processor = MagicMock()
        mock_processor.is_available.return_value = True
        mock_processor.process_pdf.return_value = [mock_result]

        mock_storage = MagicMock()
        mock_storage.get_path.return_value = str(fake_pdf)

        with patch("app.services.processing.get_processor", return_value=mock_processor), \
             patch("app.services.processing.LocalStorage", return_value=mock_storage), \
             patch("app.services.processing.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = str(tmp_path)
            mock_settings.USN_PATTERN = None

            result = processing.process_document(db_session, doc.id)

        assert result.status == ExtractionStatus.REVIEW_REQUIRED
        assert result.ocr_engine == "tesseract5"
        assert result.ocr_avg_confidence == pytest.approx(96.4)
        assert result.processing_time_ms is not None

        fields = db_session.query(ExtractedField).filter(
            ExtractedField.extraction_result_id == result.id
        ).all()
        assert len(fields) > 0

        name_field = next((f for f in fields if f.field_name == "name"), None)
        assert name_field is not None
        assert name_field.extracted_value == "John Doe"
        assert name_field.label_found is True

        usn_field = next((f for f in fields if f.field_name == "usn"), None)
        assert usn_field is not None
        assert usn_field.extracted_value == "1RV21CS001"
        assert usn_field.label_found is True

        db_session.refresh(doc)
        assert doc.status == "REVIEW_REQUIRED"

    def test_process_document_ocr_unavailable(self, db_session, tmp_path):
        doc = Document(
            original_filename="test.pdf",
            stored_key="documents/test.pdf",
            content_type="application/pdf",
            file_size=1024,
            document_type="HALL_TICKET",
            status="READY_FOR_PROCESSING",
        )
        db_session.add(doc)
        db_session.flush()

        mock_processor = MagicMock()
        mock_processor.is_available.return_value = False

        with patch("app.services.processing.get_processor", return_value=mock_processor):
            with pytest.raises(RuntimeError, match="not available"):
                processing.process_document(db_session, doc.id)

        db_session.refresh(doc)
        assert doc.status == "FAILED"

    def test_process_document_image(self, db_session, tmp_path):
        doc = Document(
            original_filename="scan.jpg",
            stored_key="documents/scan.jpg",
            content_type="image/jpeg",
            file_size=512,
            document_type="HALL_TICKET",
            status="UPLOADED",
        )
        db_session.add(doc)
        db_session.flush()

        fake_img = tmp_path / "scan.jpg"
        fake_img.write_bytes(b"\xff\xd8\xff\xe0 fake jpeg")

        mock_result = OCRResult(
            text="Student Name: Jane Smith",
            words=[
                OCRWord(text="Student", confidence=90.0, x=0, y=0, width=80, height=20, page=0),
                OCRWord(text="Name:", confidence=90.0, x=80, y=0, width=60, height=20, page=0),
                OCRWord(text="Jane", confidence=95.0, x=140, y=0, width=50, height=20, page=0),
                OCRWord(text="Smith", confidence=95.0, x=190, y=0, width=60, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
            avg_confidence=92.5,
        )

        mock_processor = MagicMock()
        mock_processor.is_available.return_value = True
        mock_processor.process_image.return_value = mock_result

        mock_storage = MagicMock()
        mock_storage.get_path.return_value = str(fake_img)

        with patch("app.services.processing.get_processor", return_value=mock_processor), \
             patch("app.services.processing.LocalStorage", return_value=mock_storage), \
             patch("app.services.processing.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = str(tmp_path)
            mock_settings.USN_PATTERN = None

            result = processing.process_document(db_session, doc.id)

        assert result.status == ExtractionStatus.REVIEW_REQUIRED
        mock_processor.process_image.assert_called_once()


class TestGetExtractionResult:
    def test_get_extraction_result(self, db_session):
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
            raw_ocr_text="test",
            ocr_engine="tesseract5",
            ocr_avg_confidence=80.0,
            status=ExtractionStatus.COMPLETED,
        )
        db_session.add(result)
        db_session.flush()

        fetched = processing.get_extraction_result(db_session, doc.id)
        assert fetched is not None
        assert fetched.id == result.id

    def test_get_extraction_result_not_found(self, db_session):
        result = processing.get_extraction_result(db_session, 999999)
        assert result is None


class TestGetExtractedFields:
    def test_get_extracted_fields(self, db_session):
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
            ocr_avg_confidence=80.0,
            status=ExtractionStatus.COMPLETED,
        )
        db_session.add(result)
        db_session.flush()

        field1 = ExtractedField(
            extraction_result_id=result.id,
            field_name="name",
            extracted_value="John",
            validation_status="VALID",
            review_status="AUTO_APPROVED",
        )
        field2 = ExtractedField(
            extraction_result_id=result.id,
            field_name="usn",
            extracted_value="1RV21CS001",
            validation_status="VALID",
            review_status="AUTO_APPROVED",
        )
        db_session.add_all([field1, field2])
        db_session.flush()

        fields = processing.get_extracted_fields(db_session, result.id)
        assert len(fields) == 2
        assert fields[0].field_name == "name"
        assert fields[1].field_name == "usn"

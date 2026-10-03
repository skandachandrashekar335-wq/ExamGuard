import os
from unittest.mock import MagicMock, patch
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.exam import Exam
from app.models.extraction import ExtractedField, ExtractionResult
from app.models.hall_ticket import HallTicket
from app.models.hall_ticket_match import HallTicketMatchResult, HallTicketMatchSignal
from app.models.verification import VerificationOutcome
from app.models.subject import Subject
from app.ai.base import OCRResult, OCRWord

settings = get_settings()

PDF_CONTENT = b"%PDF-1.4 fake pdf content"
JPEG_CONTENT = b"\xff\xd8\xff\xe0 fake jpeg content"


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        db.execute(delete(VerificationOutcome))
        all_match_results = db.query(HallTicketMatchResult.id).subquery()
        db.execute(delete(HallTicketMatchSignal).where(
            HallTicketMatchSignal.match_result_id.in_(db.query(all_match_results))
        ))
        db.execute(delete(HallTicketMatchResult))
        db.execute(delete(HallTicket).where(
            HallTicket.document_id.in_(db.query(Document.id))
        ))
        db.execute(delete(ExtractedField))
        db.execute(delete(ExtractionResult))
        db.execute(delete(Document))
        db.execute(delete(Exam).where(Exam.exam_name == "DOCPROC Test Exam"))
        db.execute(delete(Subject).where(Subject.code == "DOCPROC"))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    db = SessionLocal()
    try:
        subject = Subject(
            code="DOCPROC", name="Document Processing Subject",
            department="DOCPROC", semester=1, credits=1,
        )
        db.add(subject)
        db.flush()
        exam = Exam(
            subject_id=subject.id,
            exam_name="DOCPROC Test Exam",
            exam_date=date(2026, 12, 1),
            start_time=time(9, 0),
            end_time=time(12, 0),
            semester=1,
            department="DOCPROC",
        )
        db.add(exam)
        db.commit()
        exam_id = exam.id
    finally:
        db.close()
    test_client = TestClient(app)
    test_client.exam_id = exam_id
    return test_client


def _create_document(client, filename="test.pdf", content=PDF_CONTENT, content_type="application/pdf"):
    response = client.post(
        f"/api/v1/documents?document_type=HALL_TICKET&exam_id={client.exam_id}",
        files={"file": (filename, content, content_type)},
    )
    return response.json()["id"]


class TestProcessEndpoint:
    def test_process_document(self, client, tmp_path):
        doc_id = _create_document(client)

        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(PDF_CONTENT)

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
            mock_settings.MIN_OCR_CONFIDENCE = 60.0

            response = client.post(f"/api/v1/documents/{doc_id}/process")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "REVIEW_REQUIRED"
        assert data["ocr_engine"] == "tesseract5"
        assert data["fields_count"] > 0
        assert data["review_required"] is True

    @pytest.mark.parametrize(
        ("text", "words", "missing_field"),
        [
            (
                "Name: Asha Candidate",
                [OCRWord(text="Asha", confidence=95.0, x=0, y=0, width=40, height=20, page=0)],
                "usn",
            ),
            (
                "USN: DOCPROC001",
                [OCRWord(text="DOCPROC001", confidence=95.0, x=0, y=0, width=80, height=20, page=0)],
                "name",
            ),
        ],
    )
    def test_missing_required_candidate_ocr_field_requires_review(
        self, client, tmp_path, text, words, missing_field
    ):
        doc_id = _create_document(client)
        mock_result = OCRResult(
            text=text,
            words=words,
            page=0,
            engine="tesseract5",
            avg_confidence=95.0,
        )
        mock_processor = MagicMock()
        mock_processor.is_available.return_value = True
        mock_processor.process_pdf.return_value = [mock_result]
        mock_storage = MagicMock()
        mock_storage.get_path.return_value = str(tmp_path / "test.pdf")

        with patch("app.services.processing.get_processor", return_value=mock_processor), \
             patch("app.services.processing.LocalStorage", return_value=mock_storage), \
             patch("app.services.processing.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = str(tmp_path)
            mock_settings.USN_PATTERN = None
            mock_settings.MIN_OCR_CONFIDENCE = 60.0
            processed = client.post(f"/api/v1/documents/{doc_id}/process")

        assert processed.status_code == 200, processed.text
        fields = client.get(f"/api/v1/documents/{doc_id}/extraction").json()["fields"]
        candidate_field = next(field for field in fields if field["field_name"] == missing_field)
        assert candidate_field["extracted_value"] is None
        assert candidate_field["review_status"] == "REVIEW_REQUIRED"

    def test_registration_number_alias_and_seat_number_extract(self, client, tmp_path):
        doc_id = _create_document(client)
        result = OCRResult(
            text=(
                "Candidate Name: Asha Candidate\n"
                "Registration Number: DOCPROC002\n"
                "Seat Number: B-12"
            ),
            words=[
                OCRWord(text="Candidate", confidence=95.0, x=0, y=0, width=60, height=20, page=0),
                OCRWord(text="Name:", confidence=95.0, x=60, y=0, width=40, height=20, page=0),
                OCRWord(text="Asha", confidence=95.0, x=100, y=0, width=40, height=20, page=0),
                OCRWord(text="Candidate", confidence=95.0, x=140, y=0, width=60, height=20, page=0),
                OCRWord(text="Registration", confidence=95.0, x=0, y=30, width=80, height=20, page=0),
                OCRWord(text="Number:", confidence=95.0, x=80, y=30, width=55, height=20, page=0),
                OCRWord(text="DOCPROC002", confidence=95.0, x=135, y=30, width=90, height=20, page=0),
                OCRWord(text="Seat", confidence=95.0, x=0, y=60, width=35, height=20, page=0),
                OCRWord(text="Number:", confidence=95.0, x=35, y=60, width=55, height=20, page=0),
                OCRWord(text="B-12", confidence=95.0, x=90, y=60, width=40, height=20, page=0),
            ],
            page=0,
            engine="tesseract5",
            avg_confidence=95.0,
        )
        processor = MagicMock()
        processor.is_available.return_value = True
        processor.process_pdf.return_value = [result]
        storage = MagicMock()
        storage.get_path.return_value = str(tmp_path / "test.pdf")

        with patch("app.services.processing.get_processor", return_value=processor), \
             patch("app.services.processing.LocalStorage", return_value=storage), \
             patch("app.services.processing.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = str(tmp_path)
            mock_settings.USN_PATTERN = None
            mock_settings.MIN_OCR_CONFIDENCE = 60.0
            response = client.post(f"/api/v1/documents/{doc_id}/process")

        assert response.status_code == 200, response.text
        fields = client.get(f"/api/v1/documents/{doc_id}/extraction").json()["fields"]
        extracted = {field["field_name"]: field["extracted_value"] for field in fields}
        assert extracted["usn"] == "DOCPROC002"
        assert extracted["seat_number"] == "B-12"

    def test_low_confidence_required_identifier_requires_review(self, client, tmp_path):
        doc_id = _create_document(client)
        result = OCRResult(
            text="USN: DOCPROC004",
            words=[OCRWord(
                text="DOCPROC004", confidence=35.0, x=0, y=0,
                width=80, height=20, page=0,
            )],
            page=0,
            engine="tesseract5",
            avg_confidence=35.0,
        )
        processor = MagicMock()
        processor.is_available.return_value = True
        processor.process_pdf.return_value = [result]
        storage = MagicMock()
        storage.get_path.return_value = str(tmp_path / "test.pdf")

        with patch("app.services.processing.get_processor", return_value=processor), \
             patch("app.services.processing.LocalStorage", return_value=storage), \
             patch("app.services.processing.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = str(tmp_path)
            mock_settings.USN_PATTERN = None
            mock_settings.MIN_OCR_CONFIDENCE = 60.0
            processed = client.post(f"/api/v1/documents/{doc_id}/process")

        assert processed.status_code == 200, processed.text
        fields = client.get(f"/api/v1/documents/{doc_id}/extraction").json()["fields"]
        usn = next(field for field in fields if field["field_name"] == "usn")
        assert usn["review_status"] == "REVIEW_REQUIRED"

    def test_specific_exam_and_subject_labels_do_not_leak_into_values(self):
        from app.ai.rule_extractor import RuleBasedFieldExtractor

        result = RuleBasedFieldExtractor().extract([
            OCRResult(
                text=(
                    "Exam Name: Physics Final\n"
                    "Subject Name: Applied Physics\n"
                    "Registration Number: DOCPROC003\n"
                    "Seat Number: C-14"
                ),
                words=[],
                page=0,
                engine="tesseract5",
                avg_confidence=90.0,
            )
        ])
        values = {field.field_name: field.extracted_value for field in result.fields}
        assert values["exam_name"] == "Physics Final"
        assert values["subject"] == "Applied Physics"
        assert values["usn"] == "DOCPROC003"
        assert values["seat_number"] == "C-14"

    def test_process_document_not_found(self, client):
        response = client.post("/api/v1/documents/999999/process")
        assert response.status_code == 404

    def test_process_document_wrong_status(self, client, tmp_path):
        doc_id = _create_document(client)

        db = SessionLocal()
        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            doc.status = "PROCESSING"
            db.commit()
        finally:
            db.close()

        response = client.post(f"/api/v1/documents/{doc_id}/process")
        assert response.status_code == 422


class TestExtractionEndpoint:
    def test_get_extraction(self, client, tmp_path):
        doc_id = _create_document(client)

        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(PDF_CONTENT)

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
            mock_settings.MIN_OCR_CONFIDENCE = 60.0
            client.post(f"/api/v1/documents/{doc_id}/process")

        response = client.get(f"/api/v1/documents/{doc_id}/extraction")
        assert response.status_code == 200
        data = response.json()
        assert data["ocr_engine"] == "tesseract5"
        assert len(data["fields"]) > 0

        name_field = next((f for f in data["fields"] if f["field_name"] == "name"), None)
        assert name_field is not None
        assert name_field["extracted_value"] == "John Doe"
        assert name_field["label_found"] is True

    def test_get_extraction_not_found(self, client):
        response = client.get("/api/v1/documents/999999/extraction")
        assert response.status_code == 404

    def test_get_extraction_before_processing(self, client):
        doc_id = _create_document(client)
        response = client.get(f"/api/v1/documents/{doc_id}/extraction")
        assert response.status_code == 404

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.extraction import ExtractedField, ExtractionResult
from app.models.hall_ticket_match import HallTicketMatchResult, HallTicketMatchSignal
from app.ai.base import OCRResult, OCRWord

settings = get_settings()

PDF_CONTENT = b"%PDF-1.4 fake pdf content"
JPEG_CONTENT = b"\xff\xd8\xff\xe0 fake jpeg content"


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        all_match_results = db.query(HallTicketMatchResult.id).subquery()
        db.execute(delete(HallTicketMatchSignal).where(
            HallTicketMatchSignal.match_result_id.in_(db.query(all_match_results))
        ))
        db.execute(delete(HallTicketMatchResult))
        db.execute(delete(ExtractedField))
        db.execute(delete(ExtractionResult))
        db.execute(delete(Document))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    return TestClient(app)


def _create_document(client, filename="test.pdf", content=PDF_CONTENT, content_type="application/pdf"):
    response = client.post(
        "/api/v1/documents?document_type=HALL_TICKET",
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

            response = client.post(f"/api/v1/documents/{doc_id}/process")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "REVIEW_REQUIRED"
        assert data["ocr_engine"] == "tesseract5"
        assert data["fields_count"] > 0
        assert data["review_required"] is True

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

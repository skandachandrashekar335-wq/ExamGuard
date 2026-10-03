import io
import os
import shutil
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

settings = get_settings()

TEST_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "_test_uploads")

# Synthetic file content with correct magic bytes
PDF_CONTENT = b"%PDF-1.4 fake pdf content"
JPEG_CONTENT = b"\xff\xd8\xff\xe0 fake jpeg content"
PNG_CONTENT = b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a fake png content"


@pytest.fixture(autouse=True)
def clean_test_uploads():
    """Clean test uploads and document records before each test."""
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
        all_extractions = db.query(ExtractionResult.id).subquery()
        db.execute(delete(ExtractedField).where(
            ExtractedField.extraction_result_id.in_(db.query(all_extractions))
        ))
        db.execute(delete(ExtractionResult))
        db.execute(delete(Document))
        db.execute(delete(Exam).where(Exam.exam_name == "DOCAPI Test Exam"))
        db.execute(delete(Subject).where(Subject.code == "DOCAPI"))
        db.commit()
    finally:
        db.close()
    if os.path.exists(TEST_UPLOAD_DIR):
        shutil.rmtree(TEST_UPLOAD_DIR)
    yield
    if os.path.exists(TEST_UPLOAD_DIR):
        shutil.rmtree(TEST_UPLOAD_DIR)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    db = SessionLocal()
    try:
        subject = Subject(
            code="DOCAPI", name="Document API Subject",
            department="DOCAPI", semester=1, credits=1,
        )
        db.add(subject)
        db.flush()
        exam = Exam(
            subject_id=subject.id,
            exam_name="DOCAPI Test Exam",
            exam_date=date(2026, 12, 1),
            start_time=time(9, 0),
            end_time=time(12, 0),
            semester=1,
            department="DOCAPI",
        )
        db.add(exam)
        db.commit()
        exam_id = exam.id
    finally:
        db.close()
    test_client = TestClient(app)
    test_client.exam_id = exam_id
    return test_client


def _hall_ticket_upload_url(client):
    return f"/api/v1/documents?document_type=HALL_TICKET&exam_id={client.exam_id}"


class TestDocumentUpload:
    def test_hall_ticket_upload_requires_exam_context(self, client):
        response = client.post(
            "/api/v1/documents?document_type=HALL_TICKET",
            files={"file": ("unscoped.pdf", PDF_CONTENT, "application/pdf")},
        )
        assert response.status_code == 422
        assert "exam_id is required" in response.json()["detail"]

    def test_upload_pdf(self, client):
        response = client.post(
            _hall_ticket_upload_url(client),
            files={"file": ("test.pdf", PDF_CONTENT, "application/pdf")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["original_filename"] == "test.pdf"
        assert data["document_type"] == "HALL_TICKET"
        assert data["status"] == "READY_FOR_PROCESSING"
        assert data["content_type"] == "application/pdf"
        assert data["exam_id"] == client.exam_id
        assert "stored_key" in data

    def test_upload_jpeg(self, client):
        response = client.post(
            _hall_ticket_upload_url(client),
            files={"file": ("photo.jpg", JPEG_CONTENT, "image/jpeg")},
        )
        assert response.status_code == 201
        assert response.json()["original_filename"] == "photo.jpg"

    def test_upload_png(self, client):
        response = client.post(
            _hall_ticket_upload_url(client),
            files={"file": ("scan.png", PNG_CONTENT, "image/png")},
        )
        assert response.status_code == 201
        assert response.json()["original_filename"] == "scan.png"

    def test_empty_file_rejected(self, client):
        response = client.post(
            _hall_ticket_upload_url(client),
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert response.status_code == 422
        assert "empty" in response.json()["detail"].lower()

    def test_unsupported_extension_rejected(self, client):
        response = client.post(
            _hall_ticket_upload_url(client),
            files={"file": ("file.exe", b"MZ\x90\x00", "application/octet-stream")},
        )
        assert response.status_code == 422
        assert "extension" in response.json()["detail"].lower()

    def test_unsupported_content_type_rejected(self, client):
        response = client.post(
            _hall_ticket_upload_url(client),
            files={"file": ("file.pdf", b"not-a-real-pdf", "application/pdf")},
        )
        assert response.status_code == 422
        assert "content" in response.json()["detail"].lower() or "format" in response.json()["detail"].lower()

    def test_oversized_file_rejected(self, client):
        big_content = b"\x25\x50\x44\x46" + b"\x00" * (11 * 1024 * 1024)
        response = client.post(
            _hall_ticket_upload_url(client),
            files={"file": ("big.pdf", big_content, "application/pdf")},
        )
        assert response.status_code == 422
        assert "size" in response.json()["detail"].lower() or "exceeds" in response.json()["detail"].lower()

    def test_unsafe_filename_stored_safely(self, client):
        response = client.post(
            _hall_ticket_upload_url(client),
            files={"file": ("../../../etc/passwd.pdf", PDF_CONTENT, "application/pdf")},
        )
        assert response.status_code == 201
        key = response.json()["stored_key"]
        assert ".." not in key
        assert "etc" not in key
        assert key.startswith("documents/")

    def test_stored_key_has_correct_extension(self, client):
        response = client.post(
            _hall_ticket_upload_url(client),
            files={"file": ("hall.pdf", PDF_CONTENT, "application/pdf")},
        )
        assert response.status_code == 201
        assert response.json()["stored_key"].endswith(".pdf")

    def test_document_metadata_in_postgresql(self, client):
        response = client.post(
            _hall_ticket_upload_url(client),
            files={"file": ("test.pdf", PDF_CONTENT, "application/pdf")},
        )
        assert response.status_code == 201
        doc_id = response.json()["id"]

        db = SessionLocal()
        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            assert doc is not None
            assert doc.original_filename == "test.pdf"
            assert doc.file_size == len(PDF_CONTENT)
        finally:
            db.close()


class TestDocumentRetrieval:
    def test_get_document(self, client):
        create = client.post(
            _hall_ticket_upload_url(client),
            files={"file": ("test.pdf", PDF_CONTENT, "application/pdf")},
        )
        doc_id = create.json()["id"]

        response = client.get(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 200
        assert response.json()["id"] == doc_id

    def test_get_document_not_found(self, client):
        response = client.get("/api/v1/documents/999999")
        assert response.status_code == 404

    def test_list_documents(self, client):
        client.post(
            _hall_ticket_upload_url(client),
            files={"file": ("a.pdf", PDF_CONTENT, "application/pdf")},
        )
        client.post(
            _hall_ticket_upload_url(client),
            files={"file": ("b.jpg", JPEG_CONTENT, "image/jpeg")},
        )
        response = client.get("/api/v1/documents")
        assert response.status_code == 200
        assert response.json()["total"] >= 2

    def test_list_documents_filters_by_exam(self, client):
        created = client.post(
            _hall_ticket_upload_url(client),
            files={"file": ("scoped.pdf", PDF_CONTENT, "application/pdf")},
        )
        response = client.get(f"/api/v1/documents?exam_id={client.exam_id}")
        assert response.status_code == 200
        assert any(
            row["id"] == created.json()["id"]
            for row in response.json()["items"]
        )

    def test_path_traversal_blocked(self, client):
        # The storage layer should prevent path traversal
        from app.storage.local import LocalStorage

        storage = LocalStorage(TEST_UPLOAD_DIR)
        with pytest.raises(FileNotFoundError):
            storage.get_path("../../../etc/passwd")

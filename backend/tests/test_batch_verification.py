import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.models.document import Document, DocumentStatus
from app.models.extraction import ExtractedField, ExtractionResult, ExtractionStatus
from app.models.hall_ticket_match import HallTicketMatchResult, HallTicketMatchSignal
from app.models.seat_assignment import SeatAssignment
from app.models.student import Student
from app.models.subject import Subject
from app.models.exam import Exam
from app.models.exam_registration import ExamRegistration
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationEvidence,
)
from app.models.verification import VerificationDecision, VerificationOutcome
from app.models.hall_ticket import HallTicket
from app.models.entry_verification import EntryVerification
from app.models.attendance import AttendanceEvent, AttendanceRecord
from app.services import batch_verification


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        db.execute(delete(VerificationOutcome))
        all_match_results = db.query(HallTicketMatchResult.id).subquery()
        db.execute(
            delete(HallTicketMatchSignal).where(
                HallTicketMatchSignal.match_result_id.in_(
                    db.query(all_match_results)
                )
            )
        )
        db.execute(delete(HallTicketMatchResult))
        db.execute(delete(ExtractedField))
        db.execute(delete(ExtractionResult))
        db.execute(delete(SeatAssignment))
        db.execute(delete(HallTicket))
        db.execute(delete(IdentityVerificationEvidence))
        db.execute(delete(IdentityVerificationAttempt))
        db.execute(delete(AttendanceEvent))
        db.execute(delete(AttendanceRecord))
        db.execute(delete(EntryVerification))
        db.execute(delete(ExamRegistration))
        db.execute(delete(Exam))
        db.execute(delete(Subject))
        db.execute(delete(Student))
        db.execute(delete(Document))
        db.commit()
    finally:
        db.close()
    yield


def _create_document(db, doc_id, status=DocumentStatus.PROCESSED, suffix=""):
    doc = Document(
        id=doc_id,
        original_filename=f"test{doc_id}{suffix}.pdf",
        stored_key=f"test{doc_id}{suffix}.pdf",
        content_type="application/pdf",
        file_size=1024,
        document_type="HALL_TICKET",
        status=status,
    )
    db.add(doc)
    db.flush()
    return doc


def _create_extraction_result(db, document_id, ocr_avg_confidence=85.0):
    er = ExtractionResult(
        document_id=document_id,
        ocr_engine="tesseract5",
        ocr_avg_confidence=ocr_avg_confidence,
        processing_time_ms=1500,
        status=ExtractionStatus.COMPLETED,
    )
    db.add(er)
    db.flush()
    return er


def _create_match_result(db, document_id, extraction_result_id, overall_status="MATCHED",
                         student_id=None, exam_id=None):
    mr = HallTicketMatchResult(
        document_id=document_id,
        extraction_result_id=extraction_result_id,
        overall_status=overall_status,
        student_id=student_id,
        exam_id=exam_id,
    )
    db.add(mr)
    db.flush()
    return mr


class TestBatchVerify:
    def test_empty_document_list(self):
        db = SessionLocal()
        try:
            result = batch_verification.batch_verify(db, [])
            assert result["total"] == 0
            assert result["processed"] == 0
            assert result["matched"] == 0
            assert result["verified"] == 0
            assert result["failed"] == 0
            assert len(result["results"]) == 0
        finally:
            db.close()

    def test_document_not_found(self):
        db = SessionLocal()
        try:
            result = batch_verification.batch_verify(db, [999999])
            assert result["total"] == 1
            assert result["failed"] == 1
            assert len(result["results"]) == 1
            assert result["results"][0]["status"] == "failed"
            assert "not found" in result["results"][0]["error"]
        finally:
            db.close()

    def test_already_verified_skips_all_steps(self):
        db = SessionLocal()
        try:
            doc = _create_document(db, 100)
            er = _create_extraction_result(db, 100)
            mr = _create_match_result(db, 100, er.id)
            vo = VerificationOutcome(
                document_id=100,
                decision=VerificationDecision.VERIFIED.value,
                extraction_check="PASSED",
                match_check="PASSED",
                review_check="NOT_STARTED",
                ocr_avg_confidence=90.0,
                match_status="MATCHED",
                review_completed=False,
            )
            db.add(vo)
            db.commit()

            result = batch_verification.batch_verify(db, [100])

            assert result["total"] == 1
            assert result["processed"] == 0
            assert result["matched"] == 0
            assert result["verified"] == 0
            assert result["failed"] == 0
            assert len(result["results"]) == 1
            assert result["results"][0]["status"] == "completed"
            assert result["results"][0]["decision"] == "VERIFIED"
        finally:
            db.close()

    @patch("app.services.batch_verification._process_single")
    def test_single_document_needs_processing(self, mock_process):
        db = SessionLocal()
        try:
            doc = _create_document(db, 200, DocumentStatus.READY_FOR_PROCESSING)
            db.commit()

            mock_process.return_value = {
                "document_id": 200,
                "step": "extraction",
                "status": "completed",
                "extraction_result_id": 1,
                "ocr_avg_confidence": 85.0,
            }

            with patch("app.services.batch_verification._match_single") as mock_match, \
                 patch("app.services.batch_verification._verify_single") as mock_verify:
                mock_match.return_value = {
                    "document_id": 200,
                    "step": "matching",
                    "status": "completed",
                    "match_result_id": 1,
                    "overall_status": "MATCHED",
                }
                mock_verify.return_value = {
                    "document_id": 200,
                    "step": "verification",
                    "status": "completed",
                    "outcome_id": 1,
                    "decision": "VERIFIED",
                }

                result = batch_verification.batch_verify(db, [200])

                assert result["total"] == 1
                assert result["processed"] == 1
                assert result["matched"] == 1
                assert result["verified"] == 1
                assert result["failed"] == 0
                mock_process.assert_called_once()
                mock_match.assert_called_once()
                mock_verify.assert_called_once()
        finally:
            db.close()

    @patch("app.services.batch_verification._match_single")
    def test_extraction_already_done_skips_to_match(self, mock_match):
        db = SessionLocal()
        try:
            doc = _create_document(db, 300)
            er = _create_extraction_result(db, 300)
            db.commit()

            mock_match.return_value = {
                "document_id": 300,
                "step": "matching",
                "status": "completed",
                "match_result_id": 1,
                "overall_status": "MATCHED",
            }

            with patch("app.services.batch_verification._verify_single") as mock_verify:
                mock_verify.return_value = {
                    "document_id": 300,
                    "step": "verification",
                    "status": "completed",
                    "outcome_id": 1,
                    "decision": "VERIFIED",
                }

                result = batch_verification.batch_verify(db, [300])

                assert result["processed"] == 0
                assert result["matched"] == 1
                assert result["verified"] == 1
                mock_match.assert_called_once()
        finally:
            db.close()

    @patch("app.services.batch_verification._verify_single")
    def test_extraction_and_match_done_skips_to_verify(self, mock_verify):
        db = SessionLocal()
        try:
            doc = _create_document(db, 400)
            er = _create_extraction_result(db, 400)
            mr = _create_match_result(db, 400, er.id)
            db.commit()

            mock_verify.return_value = {
                "document_id": 400,
                "step": "verification",
                "status": "completed",
                "outcome_id": 1,
                "decision": "VERIFIED",
            }

            result = batch_verification.batch_verify(db, [400])

            assert result["processed"] == 0
            assert result["matched"] == 0
            assert result["verified"] == 1
            mock_verify.assert_called_once()
        finally:
            db.close()

    @patch("app.services.batch_verification._process_single")
    def test_extraction_failure_counts_as_failed(self, mock_process):
        db = SessionLocal()
        try:
            doc = _create_document(db, 500, DocumentStatus.READY_FOR_PROCESSING)
            db.commit()

            mock_process.return_value = {
                "document_id": 500,
                "step": "extraction",
                "status": "failed",
                "error": "OCR not available",
            }

            result = batch_verification.batch_verify(db, [500])

            assert result["failed"] == 1
            assert result["processed"] == 0
            assert result["results"][0]["error"] == "OCR not available"
        finally:
            db.close()

    @patch("app.services.batch_verification._match_single")
    def test_match_failure_counts_as_failed(self, mock_match):
        db = SessionLocal()
        try:
            doc = _create_document(db, 600)
            er = _create_extraction_result(db, 600)
            db.commit()

            mock_match.return_value = {
                "document_id": 600,
                "step": "matching",
                "status": "failed",
                "error": "No extraction results found",
            }

            result = batch_verification.batch_verify(db, [600])

            assert result["failed"] == 1
            assert result["matched"] == 0
        finally:
            db.close()

    @patch("app.services.batch_verification._verify_single")
    def test_verify_failure_counts_as_failed(self, mock_verify):
        db = SessionLocal()
        try:
            doc = _create_document(db, 700)
            er = _create_extraction_result(db, 700)
            mr = _create_match_result(db, 700, er.id)
            db.commit()

            mock_verify.return_value = {
                "document_id": 700,
                "step": "verification",
                "status": "failed",
                "error": "Document not found",
            }

            result = batch_verification.batch_verify(db, [700])

            assert result["failed"] == 1
            assert result["verified"] == 0
        finally:
            db.close()

    @patch("app.services.batch_verification._process_single")
    @patch("app.services.batch_verification._match_single")
    @patch("app.services.batch_verification._verify_single")
    def test_multiple_documents_mixed_results(self, mock_verify, mock_match, mock_process):
        db = SessionLocal()
        try:
            doc1 = _create_document(db, 801, DocumentStatus.READY_FOR_PROCESSING)
            doc2 = _create_document(db, 802)
            er2 = _create_extraction_result(db, 802)
            db.commit()

            mock_process.return_value = {
                "document_id": 801,
                "step": "extraction",
                "status": "completed",
                "extraction_result_id": 1,
                "ocr_avg_confidence": 85.0,
            }
            mock_match.side_effect = [
                {
                    "document_id": 801,
                    "step": "matching",
                    "status": "completed",
                    "match_result_id": 1,
                    "overall_status": "MATCHED",
                },
                {
                    "document_id": 802,
                    "step": "matching",
                    "status": "failed",
                    "error": "No student found",
                },
            ]
            mock_verify.return_value = {
                "document_id": 801,
                "step": "verification",
                "status": "completed",
                "outcome_id": 1,
                "decision": "VERIFIED",
            }

            result = batch_verification.batch_verify(db, [801, 802])

            assert result["total"] == 2
            assert result["processed"] == 1
            assert result["matched"] == 1
            assert result["verified"] == 1
            assert result["failed"] == 1
        finally:
            db.close()

    @patch("app.services.batch_verification._process_single")
    def test_mixed_not_found_and_valid(self, mock_process):
        db = SessionLocal()
        try:
            doc = _create_document(db, 900, DocumentStatus.READY_FOR_PROCESSING)
            db.commit()

            mock_process.return_value = {
                "document_id": 900,
                "step": "extraction",
                "status": "completed",
                "extraction_result_id": 1,
                "ocr_avg_confidence": 85.0,
            }

            with patch("app.services.batch_verification._match_single") as mock_match, \
                 patch("app.services.batch_verification._verify_single") as mock_verify:
                mock_match.return_value = {
                    "document_id": 900,
                    "step": "matching",
                    "status": "completed",
                    "match_result_id": 1,
                    "overall_status": "MATCHED",
                }
                mock_verify.return_value = {
                    "document_id": 900,
                    "step": "verification",
                    "status": "completed",
                    "outcome_id": 1,
                    "decision": "VERIFIED",
                }

                result = batch_verification.batch_verify(db, [999999, 900])

                assert result["total"] == 2
                assert result["failed"] == 1
                assert result["verified"] == 1
                assert result["results"][0]["status"] == "failed"
                assert result["results"][1]["status"] == "completed"
        finally:
            db.close()

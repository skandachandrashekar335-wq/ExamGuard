import pytest
from datetime import date, time, datetime, timezone
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.models.document import Document, DocumentStatus
from app.models.extraction import (
    ExtractedField,
    ExtractionResult,
    ExtractionStatus,
    ReviewStatus,
)
from app.models.hall_ticket_match import HallTicketMatchResult
from app.models.student import Student
from app.models.subject import Subject
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.verification import VerificationDecision, VerificationOutcome
from app.services import verification


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        db.execute(delete(VerificationOutcome))
        all_match_results = db.query(HallTicketMatchResult.id).subquery()
        from app.models.hall_ticket_match import HallTicketMatchSignal
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
        db.execute(delete(ExamRegistration))
        db.execute(delete(ExamHall))
        db.execute(delete(Exam))
        db.execute(delete(Subject))
        db.execute(delete(Student))
        db.execute(delete(Document))
        db.commit()
    finally:
        db.close()
    yield


def _create_document(db, status=DocumentStatus.PROCESSED, suffix=""):
    doc = Document(
        original_filename=f"test{suffix}.pdf",
        stored_key=f"test{suffix}.pdf",
        content_type="application/pdf",
        file_size=1024,
        document_type="HALL_TICKET",
        status=status,
    )
    db.add(doc)
    db.flush()
    return doc


def _create_extraction_result(
    db,
    document_id,
    status=ExtractionStatus.COMPLETED,
    reviewed_at=None,
    ocr_avg_confidence=85.0,
):
    er = ExtractionResult(
        document_id=document_id,
        ocr_engine="tesseract5",
        ocr_avg_confidence=ocr_avg_confidence,
        processing_time_ms=1500,
        status=status,
        reviewed_at=reviewed_at,
    )
    db.add(er)
    db.flush()
    return er


def _create_extracted_field(
    db,
    extraction_result_id,
    field_name="usn",
    extracted_value="1RV21CS001",
    review_status=ReviewStatus.AUTO_APPROVED.value,
):
    ef = ExtractedField(
        extraction_result_id=extraction_result_id,
        field_name=field_name,
        extracted_value=extracted_value,
        ocr_confidence=92.0,
        pattern_match=True,
        label_found=True,
        extraction_method="rule_based",
        validation_status="VALID",
        review_status=review_status,
    )
    db.add(ef)
    db.flush()
    return ef


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


def _create_student(db, usn="1RV21CS001"):
    student = Student(usn=usn, name="Test Student", is_active=True)
    db.add(student)
    db.flush()
    return student


def _create_subject(db, code="CS401"):
    subject = Subject(code=code, name="Test Subject", department="CS", semester=6, is_active=True)
    db.add(subject)
    db.flush()
    return subject


def _create_exam(db, subject_id, exam_name="Midterm"):
    exam = Exam(
        subject_id=subject_id,
        exam_name=exam_name,
        exam_date=date(2026, 9, 15),
        start_time=time(9, 0),
        end_time=time(12, 0),
        semester=6,
        department="CS",
        is_active=True,
    )
    db.add(exam)
    db.flush()
    return exam


class TestGetVerificationSummary:
    def test_document_not_found(self):
        db = SessionLocal()
        try:
            with pytest.raises(LookupError, match="not found"):
                verification.get_verification_summary(db, 999999)
        finally:
            db.close()

    def test_no_extraction_no_match(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            db.commit()

            data = verification.get_verification_summary(db, doc.id)

            assert data["has_extraction"] is False
            assert data["has_match"] is False
            assert data["extraction_check"] == "NOT_AVAILABLE"
            assert data["match_check"] == "NOT_AVAILABLE"
            assert data["can_verify"] is False
            assert len(data["blocking_reasons"]) == 2
        finally:
            db.close()

    def test_extraction_only(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id)
            db.commit()

            data = verification.get_verification_summary(db, doc.id)

            assert data["has_extraction"] is True
            assert data["has_match"] is False
            assert data["extraction_check"] == "PASSED"
            assert data["match_check"] == "NOT_AVAILABLE"
            assert data["can_verify"] is False
        finally:
            db.close()

    def test_extraction_and_match(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id)
            mr = _create_match_result(db, doc.id, er.id, "MATCHED")
            db.commit()

            data = verification.get_verification_summary(db, doc.id)

            assert data["has_extraction"] is True
            assert data["has_match"] is True
            assert data["extraction_check"] == "PASSED"
            assert data["match_check"] == "PASSED"
            assert data["ocr_avg_confidence"] == 85.0
            assert data["match_status"] == "MATCHED"
            assert data["can_verify"] is True
            assert len(data["blocking_reasons"]) == 0
        finally:
            db.close()

    def test_extraction_needs_review(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(
                db, doc.id, ExtractionStatus.REVIEW_REQUIRED
            )
            _create_extracted_field(
                db, er.id, review_status=ReviewStatus.REVIEW_REQUIRED.value
            )
            db.commit()

            data = verification.get_verification_summary(db, doc.id)

            assert data["extraction_check"] == "NEEDS_REVIEW"
            assert data["can_verify"] is False
        finally:
            db.close()

    def test_match_partial(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id)
            _create_match_result(db, doc.id, er.id, "PARTIAL_MATCH")
            db.commit()

            data = verification.get_verification_summary(db, doc.id)

            assert data["match_check"] == "NEEDS_REVIEW"
            assert data["can_verify"] is False
        finally:
            db.close()

    def test_match_mismatch(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id)
            _create_match_result(db, doc.id, er.id, "MISMATCH")
            db.commit()

            data = verification.get_verification_summary(db, doc.id)

            assert data["match_check"] == "FAILED"
            assert data["can_verify"] is False
        finally:
            db.close()

    def test_extraction_failed(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id, ExtractionStatus.FAILED)
            db.commit()

            data = verification.get_verification_summary(db, doc.id)

            assert data["extraction_check"] == "FAILED"
            assert data["can_verify"] is False
        finally:
            db.close()

    def test_review_completed(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(
                db, doc.id, reviewed_at=datetime.now(timezone.utc)
            )
            _create_extracted_field(db, er.id)
            _create_match_result(db, doc.id, er.id, "MATCHED")
            db.commit()

            data = verification.get_verification_summary(db, doc.id)

            assert data["review_completed"] is True
            assert data["review_check"] == "COMPLETED"
        finally:
            db.close()


class TestRunVerification:
    def test_document_not_found(self):
        db = SessionLocal()
        try:
            with pytest.raises(LookupError, match="not found"):
                verification.run_verification(db, 999999)
        finally:
            db.close()

    def test_incomplete_no_extraction(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            db.commit()

            outcome = verification.run_verification(db, doc.id)

            assert outcome.decision == VerificationDecision.INCOMPLETE.value
            assert outcome.extraction_check == "NOT_AVAILABLE"
            assert outcome.match_check == "NOT_AVAILABLE"
            assert outcome.document_id == doc.id
            assert outcome.extraction_result_id is None
            assert outcome.match_result_id is None
        finally:
            db.close()

    def test_incomplete_no_match(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id)
            db.commit()

            outcome = verification.run_verification(db, doc.id)

            assert outcome.decision == VerificationDecision.INCOMPLETE.value
            assert outcome.extraction_check == "PASSED"
            assert outcome.match_check == "NOT_AVAILABLE"
        finally:
            db.close()

    def test_verified_all_passed(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id, ocr_avg_confidence=85.0)
            _create_extracted_field(db, er.id)
            _create_match_result(db, doc.id, er.id, "MATCHED")
            db.commit()

            outcome = verification.run_verification(db, doc.id)

            assert outcome.decision == VerificationDecision.VERIFIED.value
            assert outcome.extraction_check == "PASSED"
            assert outcome.match_check == "PASSED"
            assert outcome.ocr_avg_confidence == 85.0
            assert outcome.match_status == "MATCHED"
        finally:
            db.close()

    def test_failed_match_not_found(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id)
            _create_match_result(db, doc.id, er.id, "NOT_FOUND")
            db.commit()

            outcome = verification.run_verification(db, doc.id)

            assert outcome.decision == VerificationDecision.FAILED.value
            assert outcome.match_check == "FAILED"
        finally:
            db.close()

    def test_failed_match_mismatch(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id)
            _create_match_result(db, doc.id, er.id, "MISMATCH")
            db.commit()

            outcome = verification.run_verification(db, doc.id)

            assert outcome.decision == VerificationDecision.FAILED.value
            assert outcome.match_check == "FAILED"
        finally:
            db.close()

    def test_review_required_partial_match(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id)
            _create_match_result(db, doc.id, er.id, "PARTIAL_MATCH")
            db.commit()

            outcome = verification.run_verification(db, doc.id)

            assert outcome.decision == VerificationDecision.REVIEW_REQUIRED.value
            assert outcome.match_check == "NEEDS_REVIEW"
        finally:
            db.close()

    def test_review_required_low_ocr_confidence(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id, ocr_avg_confidence=40.0)
            _create_extracted_field(db, er.id)
            _create_match_result(db, doc.id, er.id, "MATCHED")
            db.commit()

            outcome = verification.run_verification(db, doc.id)

            assert outcome.decision == VerificationDecision.REVIEW_REQUIRED.value
            assert "below threshold" in (outcome.reasoning or "")
        finally:
            db.close()

    def test_failed_extraction(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id, ExtractionStatus.FAILED)
            db.commit()

            outcome = verification.run_verification(db, doc.id)

            assert outcome.decision == VerificationDecision.FAILED.value
            assert outcome.extraction_check == "FAILED"
        finally:
            db.close()

    def test_stores_student_and_exam_ids(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id)
            student = _create_student(db)
            subject = _create_subject(db)
            exam = _create_exam(db, subject.id)
            _create_match_result(
                db, doc.id, er.id, "MATCHED",
                student_id=student.id, exam_id=exam.id,
            )
            db.commit()

            outcome = verification.run_verification(db, doc.id)

            assert outcome.student_id == student.id
            assert outcome.exam_id == exam.id
        finally:
            db.close()

    def test_multiple_verifications_create_independent_records(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id)
            _create_match_result(db, doc.id, er.id, "MATCHED")
            db.commit()

            o1 = verification.run_verification(db, doc.id)
            o2 = verification.run_verification(db, doc.id)

            assert o1.id != o2.id
            assert o1.decision == o2.decision
        finally:
            db.close()


class TestGetLatestOutcome:
    def test_returns_latest(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id)
            _create_extracted_field(db, er.id)
            _create_match_result(db, doc.id, er.id, "MATCHED")
            db.commit()

            o1 = verification.run_verification(db, doc.id)
            o2 = verification.run_verification(db, doc.id)

            latest = verification.get_latest_outcome(db, doc.id)
            assert latest is not None
            assert latest.id == o2.id
        finally:
            db.close()

    def test_returns_none_when_no_outcome(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            db.commit()

            latest = verification.get_latest_outcome(db, doc.id)
            assert latest is None
        finally:
            db.close()


class TestSecurityBoundary:
    def test_outcome_is_immutable_record(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            er = _create_extraction_result(db, doc.id, ocr_avg_confidence=90.0)
            _create_extracted_field(db, er.id)
            _create_match_result(db, doc.id, er.id, "MATCHED")
            db.commit()

            outcome = verification.run_verification(db, doc.id)

            original_decision = outcome.decision
            original_created = outcome.created_at

            outcome.decision = "VERIFIED"
            db.commit()
            db.refresh(outcome)

            assert outcome.decision == original_decision
            assert outcome.created_at == original_created
        finally:
            db.close()

    def test_does_not_create_domain_records(self):
        db = SessionLocal()
        try:
            doc = _create_document(db)
            db.commit()

            initial_student_count = db.query(Student).count()
            initial_exam_count = db.query(Exam).count()
            initial_reg_count = db.query(ExamRegistration).count()
            initial_outcome_count = db.query(VerificationOutcome).count()

            verification.run_verification(db, doc.id)

            assert db.query(Student).count() == initial_student_count
            assert db.query(Exam).count() == initial_exam_count
            assert db.query(ExamRegistration).count() == initial_reg_count
            assert db.query(VerificationOutcome).count() == initial_outcome_count + 1
        finally:
            db.close()

    def test_does_not_mutate_document_status(self):
        db = SessionLocal()
        try:
            doc = _create_document(db, DocumentStatus.PROCESSED)
            db.commit()

            original_status = doc.status
            verification.run_verification(db, doc.id)

            db.refresh(doc)
            assert doc.status == original_status
        finally:
            db.close()

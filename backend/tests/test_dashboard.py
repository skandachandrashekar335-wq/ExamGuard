import pytest
from datetime import date, time
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.models.document import Document, DocumentStatus
from app.models.extraction import ExtractedField, ExtractionResult, ExtractionStatus
from app.models.hall_ticket_match import HallTicketMatchResult, HallTicketMatchSignal
from app.models.student import Student
from app.models.subject import Subject
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationEvidence,
)
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.verification import VerificationDecision, VerificationOutcome
from app.models.hall_ticket import HallTicket
from app.services import dashboard


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


def _create_student(db, usn="1RV21CS001", name="Test Student"):
    student = Student(usn=usn, name=name, is_active=True)
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


def _create_exam_hall(db, building="Block A", room="101"):
    hall = ExamHall(
        building=building,
        room_number=room,
        capacity=60,
        rows=6,
        columns=10,
        is_active=True,
    )
    db.add(hall)
    db.flush()
    return hall


def _create_registration(db, student_id, exam_id, status=RegistrationStatus.REGISTERED.value):
    reg = ExamRegistration(
        student_id=student_id,
        exam_id=exam_id,
        status=status,
    )
    db.add(reg)
    db.flush()
    return reg


def _create_seat_assignment(db, registration_id, exam_hall_id, exam_id, student_id, seat_number="A1"):
    sa = SeatAssignment(
        exam_registration_id=registration_id,
        exam_hall_id=exam_hall_id,
        seat_number=seat_number,
        exam_id=exam_id,
        student_id=student_id,
        status=SeatAssignmentStatus.ASSIGNED.value,
    )
    db.add(sa)
    db.flush()
    return sa


def _create_document(db, suffix=""):
    doc = Document(
        original_filename=f"test{suffix}.pdf",
        stored_key=f"test{suffix}.pdf",
        content_type="application/pdf",
        file_size=1024,
        document_type="HALL_TICKET",
        status=DocumentStatus.PROCESSED,
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


def _create_verification_outcome(db, document_id, decision, student_id=None, exam_id=None,
                                  registration_id=None, extraction_check="PASSED",
                                  match_check="PASSED", ocr_avg_confidence=85.0,
                                  match_status="MATCHED"):
    vo = VerificationOutcome(
        document_id=document_id,
        decision=decision,
        student_id=student_id,
        exam_id=exam_id,
        extraction_check=extraction_check,
        match_check=match_check,
        review_check="NOT_STARTED",
        ocr_avg_confidence=ocr_avg_confidence,
        match_status=match_status,
        review_completed=False,
    )
    db.add(vo)
    db.flush()
    return vo


class TestGetExamDashboard:
    def test_exam_not_found(self):
        db = SessionLocal()
        try:
            with pytest.raises(LookupError, match="not found"):
                dashboard.get_exam_dashboard(db, 999999)
        finally:
            db.close()

    def test_empty_exam_no_registrations(self):
        db = SessionLocal()
        try:
            subject = _create_subject(db)
            exam = _create_exam(db, subject.id)
            db.commit()

            data = dashboard.get_exam_dashboard(db, exam.id)

            assert data["summary"]["total_registered"] == 0
            assert data["summary"]["total_verified"] == 0
            assert data["summary"]["total_failed"] == 0
            assert data["summary"]["total_review_required"] == 0
            assert data["summary"]["total_incomplete"] == 0
            assert data["summary"]["total_not_uploaded"] == 0
            assert data["summary"]["total_seated"] == 0
            assert data["summary"]["verification_rate"] == 0.0
            assert len(data["students"]) == 0
        finally:
            db.close()

    def test_all_students_not_uploaded(self):
        db = SessionLocal()
        try:
            subject = _create_subject(db)
            exam = _create_exam(db, subject.id)
            student1 = _create_student(db, "1RV21CS001", "Alice")
            student2 = _create_student(db, "1RV21CS002", "Bob")
            _create_registration(db, student1.id, exam.id)
            _create_registration(db, student2.id, exam.id)
            db.commit()

            data = dashboard.get_exam_dashboard(db, exam.id)

            assert data["summary"]["total_registered"] == 2
            assert data["summary"]["total_not_uploaded"] == 2
            assert data["summary"]["verification_rate"] == 0.0
            assert len(data["students"]) == 2
            for s in data["students"]:
                assert s["verification_status"] == "NOT_UPLOADED"
        finally:
            db.close()

    def test_all_students_verified(self):
        db = SessionLocal()
        try:
            subject = _create_subject(db)
            exam = _create_exam(db, subject.id)
            student1 = _create_student(db, "1RV21CS001", "Alice")
            student2 = _create_student(db, "1RV21CS002", "Bob")
            reg1 = _create_registration(db, student1.id, exam.id)
            reg2 = _create_registration(db, student2.id, exam.id)
            doc1 = _create_document(db, "1")
            doc2 = _create_document(db, "2")
            _create_verification_outcome(db, doc1.id, VerificationDecision.VERIFIED.value,
                                         student_id=student1.id, exam_id=exam.id)
            _create_verification_outcome(db, doc2.id, VerificationDecision.VERIFIED.value,
                                         student_id=student2.id, exam_id=exam.id)
            db.commit()

            data = dashboard.get_exam_dashboard(db, exam.id)

            assert data["summary"]["total_registered"] == 2
            assert data["summary"]["total_verified"] == 2
            assert data["summary"]["verification_rate"] == 100.0
            for s in data["students"]:
                assert s["verification_status"] == "VERIFIED"
        finally:
            db.close()

    def test_mixed_verification_statuses(self):
        db = SessionLocal()
        try:
            subject = _create_subject(db)
            exam = _create_exam(db, subject.id)

            student_v = _create_student(db, "1RV21CS001", "Verified Student")
            student_f = _create_student(db, "1RV21CS002", "Failed Student")
            student_r = _create_student(db, "1RV21CS003", "Review Student")
            student_n = _create_student(db, "1RV21CS004", "No Upload Student")

            reg_v = _create_registration(db, student_v.id, exam.id)
            reg_f = _create_registration(db, student_f.id, exam.id)
            reg_r = _create_registration(db, student_r.id, exam.id)
            reg_n = _create_registration(db, student_n.id, exam.id)

            doc_v = _create_document(db, "v")
            doc_f = _create_document(db, "f")
            doc_r = _create_document(db, "r")

            _create_verification_outcome(db, doc_v.id, VerificationDecision.VERIFIED.value,
                                         student_id=student_v.id, exam_id=exam.id)
            _create_verification_outcome(db, doc_f.id, VerificationDecision.FAILED.value,
                                         student_id=student_f.id, exam_id=exam.id,
                                         extraction_check="FAILED", match_check="NOT_AVAILABLE",
                                         match_status=None, ocr_avg_confidence=None)
            _create_verification_outcome(db, doc_r.id, VerificationDecision.REVIEW_REQUIRED.value,
                                         student_id=student_r.id, exam_id=exam.id,
                                         match_status="PARTIAL_MATCH")
            db.commit()

            data = dashboard.get_exam_dashboard(db, exam.id)

            assert data["summary"]["total_registered"] == 4
            assert data["summary"]["total_verified"] == 1
            assert data["summary"]["total_failed"] == 1
            assert data["summary"]["total_review_required"] == 1
            assert data["summary"]["total_not_uploaded"] == 1
            assert data["summary"]["verification_rate"] == 25.0

            statuses = {s["student_usn"]: s["verification_status"] for s in data["students"]}
            assert statuses["1RV21CS001"] == "VERIFIED"
            assert statuses["1RV21CS002"] == "FAILED"
            assert statuses["1RV21CS003"] == "REVIEW_REQUIRED"
            assert statuses["1RV21CS004"] == "NOT_UPLOADED"
        finally:
            db.close()

    def test_seat_assignment_appears_in_student_entry(self):
        db = SessionLocal()
        try:
            subject = _create_subject(db)
            exam = _create_exam(db, subject.id)
            student = _create_student(db)
            reg = _create_registration(db, student.id, exam.id)
            hall = _create_exam_hall(db)
            sa = _create_seat_assignment(db, reg.id, hall.id, exam.id, student.id, "B3")
            db.commit()

            data = dashboard.get_exam_dashboard(db, exam.id)

            assert data["summary"]["total_seated"] == 1
            entry = data["students"][0]
            assert entry["seat_assignment_id"] == sa.id
            assert entry["seat_number"] == "B3"
            assert entry["hall_name"] == "Block A 101"
        finally:
            db.close()

    def test_student_without_seat_assignment(self):
        db = SessionLocal()
        try:
            subject = _create_subject(db)
            exam = _create_exam(db, subject.id)
            student = _create_student(db)
            _create_registration(db, student.id, exam.id)
            db.commit()

            data = dashboard.get_exam_dashboard(db, exam.id)

            assert data["summary"]["total_seated"] == 0
            entry = data["students"][0]
            assert entry["seat_assignment_id"] is None
            assert entry["seat_number"] is None
            assert entry["hall_name"] is None
        finally:
            db.close()

    def test_cancelled_registration_excluded(self):
        db = SessionLocal()
        try:
            subject = _create_subject(db)
            exam = _create_exam(db, subject.id)
            student_active = _create_student(db, "1RV21CS001", "Active")
            student_cancelled = _create_student(db, "1RV21CS002", "Cancelled")
            _create_registration(db, student_active.id, exam.id)
            _create_registration(db, student_cancelled.id, exam.id,
                                 status=RegistrationStatus.CANCELLED.value)
            db.commit()

            data = dashboard.get_exam_dashboard(db, exam.id)

            assert data["summary"]["total_registered"] == 1
            assert len(data["students"]) == 1
            assert data["students"][0]["student_usn"] == "1RV21CS001"
        finally:
            db.close()

    def test_latest_outcome_selected_when_multiple(self):
        db = SessionLocal()
        try:
            subject = _create_subject(db)
            exam = _create_exam(db, subject.id)
            student = _create_student(db)
            reg = _create_registration(db, student.id, exam.id)
            doc1 = _create_document(db, "1")
            doc2 = _create_document(db, "2")

            _create_verification_outcome(db, doc1.id, VerificationDecision.INCOMPLETE.value,
                                         student_id=student.id, exam_id=exam.id,
                                         extraction_check="NOT_AVAILABLE", match_check="NOT_AVAILABLE",
                                         ocr_avg_confidence=None, match_status=None)
            _create_verification_outcome(db, doc2.id, VerificationDecision.VERIFIED.value,
                                         student_id=student.id, exam_id=exam.id)
            db.commit()

            data = dashboard.get_exam_dashboard(db, exam.id)

            entry = data["students"][0]
            assert entry["verification_status"] == "VERIFIED"
            assert entry["decision"] == VerificationDecision.VERIFIED.value
            assert entry["document_id"] == doc2.id
        finally:
            db.close()

    def test_verification_details_populated(self):
        db = SessionLocal()
        try:
            subject = _create_subject(db)
            exam = _create_exam(db, subject.id)
            student = _create_student(db)
            reg = _create_registration(db, student.id, exam.id)
            doc = _create_document(db)
            _create_verification_outcome(
                db, doc.id, VerificationDecision.VERIFIED.value,
                student_id=student.id, exam_id=exam.id,
                ocr_avg_confidence=92.5, match_status="MATCHED",
            )
            db.commit()

            data = dashboard.get_exam_dashboard(db, exam.id)
            entry = data["students"][0]

            assert entry["decision"] == "VERIFIED"
            assert entry["extraction_check"] == "PASSED"
            assert entry["match_check"] == "PASSED"
            assert entry["ocr_avg_confidence"] == 92.5
            assert entry["match_status"] == "MATCHED"
            assert entry["document_id"] == doc.id
            assert entry["verification_created_at"] is not None
        finally:
            db.close()

    def test_incomplete_status_counted(self):
        db = SessionLocal()
        try:
            subject = _create_subject(db)
            exam = _create_exam(db, subject.id)
            student = _create_student(db)
            reg = _create_registration(db, student.id, exam.id)
            doc = _create_document(db)
            _create_verification_outcome(
                db, doc.id, VerificationDecision.INCOMPLETE.value,
                student_id=student.id, exam_id=exam.id,
                extraction_check="NOT_AVAILABLE", match_check="NOT_AVAILABLE",
                ocr_avg_confidence=None, match_status=None,
            )
            db.commit()

            data = dashboard.get_exam_dashboard(db, exam.id)

            assert data["summary"]["total_incomplete"] == 1
            assert data["students"][0]["verification_status"] == "INCOMPLETE"
        finally:
            db.close()

    def test_verification_rate_rounded(self):
        db = SessionLocal()
        try:
            subject = _create_subject(db)
            exam = _create_exam(db, subject.id)

            for i in range(3):
                student = _create_student(db, f"1RV21CS00{i+1}")
                _create_registration(db, student.id, exam.id)

            student_v = _create_student(db, "1RV21CS010")
            _create_registration(db, student_v.id, exam.id)
            doc = _create_document(db, "v")
            _create_verification_outcome(db, doc.id, VerificationDecision.VERIFIED.value,
                                         student_id=student_v.id, exam_id=exam.id)
            db.commit()

            data = dashboard.get_exam_dashboard(db, exam.id)

            assert data["summary"]["total_registered"] == 4
            assert data["summary"]["total_verified"] == 1
            assert data["summary"]["verification_rate"] == 25.0
        finally:
            db.close()

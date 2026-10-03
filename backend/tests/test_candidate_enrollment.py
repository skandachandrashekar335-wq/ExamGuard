import base64
import uuid
from datetime import date, time, datetime, timezone

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.auth import Role, get_current_user
from app.core.database import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration
from app.models.examination_session import ExaminationSession
from app.models.extraction import ExtractedField, ExtractionResult
from app.models.hall_ticket import HallTicket
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationEvidence,
)
from app.models.import_audit_log import ImportAuditLog
from app.models.invigilator_assignment import InvigilatorAssignment
from app.models.seat_assignment import SeatAssignment
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import User


ENROLL_PREFIX = "ENROLLPHASE2"
ACTOR_EMAIL = "test@example.com"


def _file_ids(db):
    return db.query(Document.id).filter(
        Document.original_filename.like(f"{ENROLL_PREFIX}-%")
    )


@pytest.fixture(autouse=True)
def cleanup_enrollment_data():
    db = SessionLocal()
    try:
        exam_ids = db.query(Exam.id).filter(Exam.exam_name.like(f"{ENROLL_PREFIX}-%"))
        student_ids = db.query(Student.id).filter(Student.usn.like(f"{ENROLL_PREFIX}%"))
        registration_ids = db.query(ExamRegistration.id).filter(
            ExamRegistration.exam_id.in_(exam_ids)
            | ExamRegistration.student_id.in_(student_ids)
        )
        extraction_ids = db.query(ExtractionResult.id).filter(
            ExtractionResult.document_id.in_(_file_ids(db))
        )
        match_ids = db.query(IdentityVerificationAttempt.id).filter(
            IdentityVerificationAttempt.exam_registration_id.in_(registration_ids)
        )
        db.execute(delete(IdentityVerificationEvidence).where(
            IdentityVerificationEvidence.attempt_id.in_(match_ids)
        ))
        db.execute(delete(IdentityVerificationAttempt).where(
            IdentityVerificationAttempt.id.in_(match_ids)
        ))
        db.execute(delete(HallTicket).where(
            HallTicket.exam_registration_id.in_(registration_ids)
            | HallTicket.document_id.in_(_file_ids(db))
        ))
        db.execute(delete(SeatAssignment).where(
            SeatAssignment.exam_registration_id.in_(registration_ids)
        ))
        db.execute(delete(ExaminationSession).where(
            ExaminationSession.exam_id.in_(exam_ids)
        ))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.id.in_(registration_ids)
        ))
        db.execute(delete(ExtractedField).where(
            ExtractedField.extraction_result_id.in_(extraction_ids)
        ))
        db.execute(delete(ExtractionResult).where(
            ExtractionResult.id.in_(extraction_ids)
        ))
        db.execute(delete(Document).where(Document.id.in_(_file_ids(db))))
        db.execute(delete(Exam).where(Exam.id.in_(exam_ids)))
        db.execute(delete(ExamHall).where(ExamHall.building.like(f"{ENROLL_PREFIX}%")))
        db.execute(delete(Subject).where(Subject.code.like(f"{ENROLL_PREFIX}%")))
        db.execute(delete(Student).where(Student.id.in_(student_ids)))
        db.execute(delete(ImportAuditLog).where(ImportAuditLog.actor == ACTOR_EMAIL))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def exam_context():
    suffix = uuid.uuid4().hex[:8].upper()
    db = SessionLocal()
    try:
        subject = Subject(
            code=f"{ENROLL_PREFIX}{suffix}",
            name="Enrollment Subject",
            department="Enrollment",
            semester=2,
            credits=3,
        )
        db.add(subject)
        db.flush()
        exam = Exam(
            subject_id=subject.id,
            exam_name=f"{ENROLL_PREFIX}-{suffix} End Semester",
            exam_date=date(2026, 12, 12),
            start_time=time(9, 0),
            end_time=time(12, 0),
            semester=2,
            department="Enrollment",
        )
        db.add(exam)
        db.flush()
        hall = ExamHall(
            building=f"{ENROLL_PREFIX} Block",
            room_number=suffix,
            name=f"{ENROLL_PREFIX} Hall {suffix}",
            capacity=30,
        )
        db.add(hall)
        db.flush()
        session = ExaminationSession(exam_id=exam.id, exam_hall_id=hall.id)
        db.add(session)
        db.commit()
        yield {"exam_id": exam.id, "subject_id": subject.id, "hall_id": hall.id}
    finally:
        db.close()


def _seed_reviewed_document(exam_id: int, fields: dict[str, str | None], *, uncertain=()):
    token = uuid.uuid4().hex
    db = SessionLocal()
    try:
        document = Document(
            original_filename=f"{ENROLL_PREFIX}-{token}.pdf",
            stored_key=f"documents/{ENROLL_PREFIX}-{token}.pdf",
            content_type="application/pdf",
            file_size=128,
            document_type="HALL_TICKET",
            exam_id=exam_id,
            status="PROCESSED",
        )
        db.add(document)
        db.flush()
        extraction = ExtractionResult(
            document_id=document.id,
            raw_ocr_text="reviewed admit card",
            ocr_engine="tesseract5",
            ocr_avg_confidence=90.0,
            status="COMPLETED",
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(extraction)
        db.flush()
        for name, value in fields.items():
            db.add(ExtractedField(
                extraction_result_id=extraction.id,
                field_name=name,
                extracted_value=value,
                corrected_value=None,
                ocr_confidence=95.0 if value is not None else None,
                label_found=value is not None,
                pattern_match=True if value is not None else None,
                validation_status="VALID" if value is not None else "MISSING",
                review_status="REVIEW_REQUIRED" if name in uncertain else "REVIEWED",
            ))
        db.commit()
        return document.id
    finally:
        db.close()


def _fields(exam_context, *, usn="ENROLLPHASE2001", name="Asha Candidate", **overrides):
    values = {
        "usn": usn,
        "name": name,
        "exam_name": None,
        "subject": None,
        "exam_date": None,
        "start_time": None,
        "end_time": None,
        "exam_hall": None,
        "seat_number": None,
    }
    values.update(overrides)
    return values


def _confirm(client, document_id: int, exam_id: int, *, confirmed=True):
    return client.post(
        f"/api/v1/documents/{document_id}/enroll-candidate",
        json={"exam_id": exam_id, "confirmed": confirmed},
    )


def _claim_as(monkeypatch, *, user_id="1", role=Role.ADMIN):
    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: {"sub": user_id, "role": role, "email": ACTOR_EMAIL},
    )


def test_confirmed_candidate_creates_linked_records(client, exam_context):
    document_id = _seed_reviewed_document(
        exam_context["exam_id"], _fields(exam_context)
    )

    response = _confirm(client, document_id, exam_context["exam_id"])

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["student_created"] is True
    assert data["registration_created"] is True
    assert data["reference_photo_enrolled"] is False
    assert data["needs_seat_assignment"] is True
    db = SessionLocal()
    try:
        student = db.get(Student, data["student_id"])
        registration = db.get(ExamRegistration, data["registration_id"])
        ticket = db.get(HallTicket, data["hall_ticket_id"])
        attempt = db.get(IdentityVerificationAttempt, data["identity_attempt_id"])
        assert student.usn == "ENROLLPHASE2001"
        assert registration.exam_id == exam_context["exam_id"]
        assert ticket.exam_registration_id == registration.id
        assert ticket.document_id == document_id
        assert attempt.exam_registration_id == registration.id
        assert attempt.hall_ticket_id == ticket.id
        assert attempt.reference_face_url is None
        audit = db.query(ImportAuditLog).filter(
            ImportAuditLog.actor == ACTOR_EMAIL,
            ImportAuditLog.import_type == "candidate_enrollment",
        ).one()
        assert audit.successful_rows == 1
    finally:
        db.close()


def test_operator_can_confirm_enrollment(client, exam_context, monkeypatch):
    document_id = _seed_reviewed_document(
        exam_context["exam_id"],
        _fields(exam_context, usn="ENROLLPHASE2015", name="Operator Candidate"),
    )
    _claim_as(monkeypatch, user_id="operator-15", role=Role.OPERATOR)

    response = _confirm(client, document_id, exam_context["exam_id"])

    assert response.status_code == 200, response.text
    assert response.json()["registration_created"] is True


def test_readiness_counts_update_after_enrollment(client, exam_context):
    document_id = _seed_reviewed_document(
        exam_context["exam_id"],
        _fields(exam_context, usn="ENROLLPHASE2016", name="Readiness Candidate"),
    )
    path = f"/api/v1/exams/{exam_context['exam_id']}/enrollment-readiness"
    before = client.get(path)
    assert before.status_code == 200, before.text
    assert before.json()["candidates_enrolled"] == 0
    assert before.json()["reference_photos_enrolled"] == 0
    assert before.json()["candidates_needing_review"] == 1

    enrolled = _confirm(client, document_id, exam_context["exam_id"])
    assert enrolled.status_code == 200, enrolled.text
    after = client.get(path)
    assert after.json()["candidates_enrolled"] == 1
    assert after.json()["reference_photos_enrolled"] == 0
    assert after.json()["candidates_needing_review"] == 0


def test_existing_student_is_linked_without_duplicate(client, exam_context):
    db = SessionLocal()
    existing = Student(usn="ENROLLPHASE2002", name="Asha Existing")
    db.add(existing)
    db.commit()
    db.refresh(existing)
    existing_id = existing.id
    db.close()
    document_id = _seed_reviewed_document(
        exam_context["exam_id"],
        _fields(exam_context, usn="ENROLLPHASE2002", name="Asha Existing"),
    )

    response = _confirm(client, document_id, exam_context["exam_id"])

    assert response.status_code == 200, response.text
    assert response.json()["student_id"] == existing_id
    assert response.json()["student_created"] is False
    db = SessionLocal()
    try:
        assert db.query(Student).filter(Student.usn == "ENROLLPHASE2002").count() == 1
    finally:
        db.close()


def test_existing_exam_registration_is_reused(client, exam_context):
    db = SessionLocal()
    student = Student(usn="ENROLLPHASE2014", name="Already Registered")
    db.add(student)
    db.flush()
    registration = ExamRegistration(
        student_id=student.id,
        exam_id=exam_context["exam_id"],
        status="REGISTERED",
    )
    db.add(registration)
    db.commit()
    student_id = student.id
    registration_id = registration.id
    db.close()
    document_id = _seed_reviewed_document(
        exam_context["exam_id"],
        _fields(exam_context, usn="ENROLLPHASE2014", name="Already Registered"),
    )

    response = _confirm(client, document_id, exam_context["exam_id"])

    assert response.status_code == 200, response.text
    assert response.json()["student_id"] == student_id
    assert response.json()["registration_id"] == registration_id
    assert response.json()["registration_created"] is False
    db = SessionLocal()
    try:
        assert db.query(ExamRegistration).filter(
            ExamRegistration.student_id == student_id,
            ExamRegistration.exam_id == exam_context["exam_id"],
        ).count() == 1
    finally:
        db.close()


def test_same_usn_uploaded_twice_does_not_duplicate_enrollment(client, exam_context):
    values = _fields(exam_context, usn="ENROLLPHASE2003", name="Duplicate Candidate")
    first_doc = _seed_reviewed_document(exam_context["exam_id"], values)
    second_doc = _seed_reviewed_document(exam_context["exam_id"], values)
    first = _confirm(client, first_doc, exam_context["exam_id"])
    assert first.status_code == 200, first.text

    second = _confirm(client, second_doc, exam_context["exam_id"])

    assert second.status_code == 409
    db = SessionLocal()
    try:
        assert db.query(Student).filter(Student.usn == "ENROLLPHASE2003").count() == 1
        assert db.query(ExamRegistration).filter(
            ExamRegistration.student_id == first.json()["student_id"],
            ExamRegistration.exam_id == exam_context["exam_id"],
        ).count() == 1
    finally:
        db.close()


def test_reconfirming_same_document_is_idempotent(client, exam_context):
    document_id = _seed_reviewed_document(
        exam_context["exam_id"],
        _fields(exam_context, usn="ENROLLPHASE2004", name="Repeat Confirm"),
    )
    first = _confirm(client, document_id, exam_context["exam_id"])
    second = _confirm(client, document_id, exam_context["exam_id"])

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["already_enrolled"] is True
    assert second.json()["registration_id"] == first.json()["registration_id"]


def test_upload_exam_binding_and_extracted_exam_mismatch_are_rejected(client, exam_context):
    other_exam = Exam(
        subject_id=exam_context["subject_id"],
        exam_name=f"{ENROLL_PREFIX}-OTHER",
        exam_date=date(2026, 12, 13),
        start_time=time(9, 0),
        end_time=time(12, 0),
        semester=2,
        department="Enrollment",
    )
    db = SessionLocal()
    db.add(other_exam)
    db.commit()
    db.refresh(other_exam)
    other_exam_id = other_exam.id
    db.close()

    bound_doc = _seed_reviewed_document(
        exam_context["exam_id"], _fields(exam_context, usn="ENROLLPHASE2005")
    )
    wrong_selected_exam = _confirm(client, bound_doc, other_exam_id)
    assert wrong_selected_exam.status_code == 409

    mismatched_text_doc = _seed_reviewed_document(
        exam_context["exam_id"],
        _fields(
            exam_context,
            usn="ENROLLPHASE2006",
            exam_name=other_exam.exam_name,
        ),
    )
    mismatched_text = _confirm(client, mismatched_text_doc, exam_context["exam_id"])
    assert mismatched_text.status_code == 409


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"usn": None, "name": "Missing USN"}, "USN"),
        ({"usn": "ENROLLPHASE2007", "name": None}, "student name"),
    ],
)
def test_missing_required_candidate_field_blocks_enrollment(
    client, exam_context, fields, message
):
    document_id = _seed_reviewed_document(
        exam_context["exam_id"], _fields(exam_context, **fields)
    )
    response = _confirm(client, document_id, exam_context["exam_id"])
    assert response.status_code == 409
    assert message.casefold() in response.json()["detail"].casefold()


def test_uncertain_ocr_field_blocks_enrollment(client, exam_context):
    document_id = _seed_reviewed_document(
        exam_context["exam_id"],
        _fields(exam_context, usn="ENROLLPHASE2008", name="Uncertain Candidate"),
        uncertain=("name",),
    )
    response = _confirm(client, document_id, exam_context["exam_id"])
    assert response.status_code == 409
    assert "uncertain" in response.json()["detail"].lower()


def test_confirmed_seat_and_hall_create_seat_assignment(client, exam_context):
    db = SessionLocal()
    hall = db.get(ExamHall, exam_context["hall_id"])
    hall_label = hall.name
    db.close()
    document_id = _seed_reviewed_document(
        exam_context["exam_id"],
        _fields(
            exam_context,
            usn="ENROLLPHASE2010",
            name="Seated Candidate",
            exam_hall=hall_label,
            seat_number="B-12",
        ),
    )

    response = _confirm(client, document_id, exam_context["exam_id"])

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["seat_assignment_id"] is not None
    assert data["needs_seat_assignment"] is False
    db = SessionLocal()
    try:
        seat = db.get(SeatAssignment, data["seat_assignment_id"])
        assert seat.exam_registration_id == data["registration_id"]
        assert seat.exam_id == exam_context["exam_id"]
        assert seat.exam_hall_id == exam_context["hall_id"]
        assert seat.seat_number == "B-12"
    finally:
        db.close()


def test_preexisting_seat_assignment_is_linked_when_admit_card_has_no_seat(
    client, exam_context
):
    db = SessionLocal()
    student = Student(usn="ENROLLPHASE2018", name="Preseated Candidate")
    db.add(student)
    db.flush()
    registration = ExamRegistration(
        student_id=student.id,
        exam_id=exam_context["exam_id"],
        status="REGISTERED",
    )
    db.add(registration)
    db.flush()
    seat = SeatAssignment(
        exam_registration_id=registration.id,
        exam_hall_id=exam_context["hall_id"],
        exam_id=exam_context["exam_id"],
        student_id=student.id,
        seat_number="A-18",
    )
    db.add(seat)
    db.commit()
    seat_id = seat.id
    db.close()
    document_id = _seed_reviewed_document(
        exam_context["exam_id"],
        _fields(
            exam_context,
            usn="ENROLLPHASE2018",
            name="Preseated Candidate",
        ),
    )

    response = _confirm(client, document_id, exam_context["exam_id"])

    assert response.status_code == 200, response.text
    assert response.json()["seat_assignment_id"] == seat_id
    assert response.json()["needs_seat_assignment"] is False


def test_reviewer_cannot_confirm_candidate_enrollment(client, exam_context, monkeypatch):
    document_id = _seed_reviewed_document(
        exam_context["exam_id"],
        _fields(exam_context, usn="ENROLLPHASE2011", name="Protected Candidate"),
    )
    _claim_as(monkeypatch, user_id="88", role=Role.REVIEWER)

    response = _confirm(client, document_id, exam_context["exam_id"])

    assert response.status_code == 403
    db = SessionLocal()
    try:
        assert db.query(Student).filter(Student.usn == "ENROLLPHASE2011").count() == 0
    finally:
        db.close()


def test_active_invigilator_assignment_does_not_grant_enrollment_access(
    client, exam_context, monkeypatch
):
    document_id = _seed_reviewed_document(
        exam_context["exam_id"],
        _fields(exam_context, usn="ENROLLPHASE2017", name="Invigilator Candidate"),
    )
    db = SessionLocal()
    try:
        user = User(
            email="enrollphase2-invigilator@example.com",
            full_name="Enrollment Invigilator",
            role=Role.REVIEWER,
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(InvigilatorAssignment(
            user_id=user.id,
            exam_id=exam_context["exam_id"],
            exam_hall_id=exam_context["hall_id"],
            is_active=True,
        ))
        db.commit()
        user_id = user.id
    finally:
        db.close()
    _claim_as(monkeypatch, user_id=str(user_id), role=Role.REVIEWER)

    response = _confirm(client, document_id, exam_context["exam_id"])

    assert response.status_code == 403


def test_reference_upload_stays_on_correct_candidate_attempt(
    client, exam_context, monkeypatch
):
    document_id = _seed_reviewed_document(
        exam_context["exam_id"],
        _fields(exam_context, usn="ENROLLPHASE2012", name="Reference Candidate"),
    )
    enrollment = _confirm(client, document_id, exam_context["exam_id"])
    assert enrollment.status_code == 200, enrollment.text
    attempt_id = enrollment.json()["identity_attempt_id"]
    other_doc = _seed_reviewed_document(
        exam_context["exam_id"],
        _fields(exam_context, usn="ENROLLPHASE2013", name="Other Candidate"),
    )
    other = _confirm(client, other_doc, exam_context["exam_id"])
    assert other.status_code == 200, other.text
    other_attempt_id = other.json()["identity_attempt_id"]

    image = np.full((32, 32, 3), 20, np.uint8)
    ok, image_bytes = cv2.imencode(".png", image)
    assert ok
    monkeypatch.setattr(
        "app.storage.cloudinary.CloudinaryStorage.save",
        lambda _storage, _key, _data: f"https://cloudinary.test/{attempt_id}.png",
    )
    upload = client.post(
        f"/api/v1/identity-verifications/{attempt_id}/reference-face",
        json={
            "reference_image": base64.b64encode(image_bytes.tobytes()).decode(),
            "image_format": "image/png",
        },
    )
    assert upload.status_code == 200, upload.text
    db = SessionLocal()
    try:
        attempt = db.get(IdentityVerificationAttempt, attempt_id)
        other_attempt = db.get(IdentityVerificationAttempt, other_attempt_id)
        assert attempt.exam_registration_id == enrollment.json()["registration_id"]
        assert attempt.reference_face_url == f"https://cloudinary.test/{attempt_id}.png"
        assert other_attempt.reference_face_url is None
    finally:
        db.close()
    readiness = client.get(
        f"/api/v1/exams/{exam_context['exam_id']}/enrollment-readiness"
    )
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["candidates_enrolled"] == 2
    assert readiness.json()["reference_photos_enrolled"] == 1
"""Hard security rule: NO_MATCH can never be manually allowed.

The invigilator manual-review endpoints are the ONLY path that acts on an
automated identity decision, and they apply exclusively to INCONCLUSIVE
results. An automated NO_MATCH must be rejected server-side (409) for BOTH
actions — not merely hidden in the UI — with an error that points to
REVERIFY. This file also covers the review-status seat_number added for the
review panel.
"""

from contextlib import contextmanager
from datetime import date, time
from types import SimpleNamespace

import pytest
from sqlalchemy import delete

from app.auth import Role, get_current_user
from app.core.database import SessionLocal
from app.main import app
from app.models.attendance import AttendanceEvent, AttendanceRecord
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.identity_verification import IdentityVerificationAttempt
from app.models.invigilator_assignment import InvigilatorAssignment
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import User

REVIEW_URL = "/api/v1/attendance/manual-review"


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def cleanup():
    """Remove NMG-prefixed test data before each test."""
    db = SessionLocal()
    try:
        student_ids = db.query(Student.id).filter(Student.usn.ilike("NMG%"))
        reg_ids = db.query(ExamRegistration.id).filter(
            ExamRegistration.student_id.in_(student_ids)
        )
        exam_ids = db.query(Exam.id).filter(Exam.exam_name.ilike("NMG%"))
        db.execute(delete(AttendanceEvent).where(
            AttendanceEvent.student_id.in_(student_ids)
        ))
        db.execute(delete(AttendanceRecord).where(
            AttendanceRecord.student_id.in_(student_ids)
        ))
        db.execute(delete(IdentityVerificationAttempt).where(
            IdentityVerificationAttempt.exam_registration_id.in_(reg_ids)
        ))
        db.execute(delete(SeatAssignment).where(
            SeatAssignment.exam_registration_id.in_(reg_ids)
        ))
        db.execute(delete(InvigilatorAssignment).where(
            InvigilatorAssignment.exam_id.in_(exam_ids)
        ))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.id.in_(reg_ids)
        ))
        db.execute(delete(Exam).where(Exam.id.in_(exam_ids)))
        db.execute(delete(ExamHall).where(ExamHall.building.ilike("NMG%")))
        db.execute(delete(Subject).where(Subject.code.ilike("NMG%")))
        db.execute(delete(Student).where(Student.usn.ilike("NMG%")))
        db.execute(delete(User).where(User.email.ilike("nmg-%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


def _mk_env(db, *, usn="NMG001", decision="NO_MATCH", with_seat=True):
    subject = Subject(
        code=f"NMGSUB{usn[-3:]}", name="NMG Subject",
        department="NMG Dept", semester=6, credits=3,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)

    exam = Exam(
        subject_id=subject.id, exam_name=f"NMG Exam {usn[-3:]}",
        exam_date=date(2026, 12, 3), start_time=time(9, 0),
        end_time=time(12, 0), semester=6, department="NMG Dept",
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    hall = ExamHall(
        building=f"NMG Hall {usn[-3:]}", room_number="101", capacity=50,
    )
    db.add(hall)
    db.commit()
    db.refresh(hall)

    student = Student(usn=usn, name=f"NMG Student {usn[-3:]}")
    db.add(student)
    db.commit()
    db.refresh(student)

    reg = ExamRegistration(
        student_id=student.id, exam_id=exam.id,
        status=RegistrationStatus.REGISTERED.value,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)

    seat = None
    if with_seat:
        seat = SeatAssignment(
            exam_registration_id=reg.id, exam_hall_id=hall.id,
            exam_id=exam.id, student_id=student.id,
            seat_number=f"NMG-{usn[-3:]}",
            status=SeatAssignmentStatus.ASSIGNED.value,
        )
        db.add(seat)

    attempt = IdentityVerificationAttempt(
        student_id=student.id, exam_registration_id=reg.id,
        status="COMPLETED", decision=decision,
        verification_method="FACE",
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return SimpleNamespace(
        exam=exam, hall=hall, student=student, reg=reg,
        seat=seat, attempt=attempt,
    )


def _mk_invigilator(db, exam_id, hall_id, *, email="nmg-inv@example.com"):
    user = User(email=email, full_name="NMG Invigilator", role=Role.INVIGILATOR)
    db.add(user)
    db.commit()
    db.refresh(user)
    assignment = InvigilatorAssignment(
        user_id=user.id, exam_id=exam_id, exam_hall_id=hall_id,
        is_active=True,
    )
    db.add(assignment)
    db.commit()
    return user, assignment


@contextmanager
def _claims(user, role=Role.INVIGILATOR):
    prev = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(user.id),
        "role": role,
        "email": user.email,
        "full_name": user.full_name,
    }
    try:
        yield
    finally:
        if prev is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = prev


def _post(client, reg_id, action, reason="Attempting manual override"):
    return client.post(
        REVIEW_URL,
        json={
            "exam_registration_id": reg_id,
            "action": action,
            "reason": reason,
        },
    )


# ---------------------------------------------------------------------------
# NO_MATCH hard guard
# ---------------------------------------------------------------------------


class TestNoMatchNeverManuallyAllowed:
    def test_no_match_allow_rejected_server_side(self, client, db):
        env = _mk_env(db, decision="NO_MATCH")
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            resp = _post(client, env.reg.id, "CHECK_IN")

        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert "NO_MATCH" in detail
        assert "REVERIFY" in detail

    def test_no_match_deny_also_rejected_manual_review_only_for_inconclusive(
        self, client, db
    ):
        env = _mk_env(db, decision="NO_MATCH")
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            resp = _post(client, env.reg.id, "CHECK_OUT")

        assert resp.status_code == 409
        assert "NO_MATCH" in resp.json()["detail"]

    def test_no_match_attempts_create_no_attendance_side_effects(
        self, client, db
    ):
        env = _mk_env(db, decision="NO_MATCH")
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            assert _post(client, env.reg.id, "CHECK_IN").status_code == 409
            assert _post(client, env.reg.id, "CHECK_OUT").status_code == 409

        assert (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.exam_registration_id == env.reg.id)
            .count()
            == 0
        )
        assert (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == env.reg.id)
            .count()
            == 0
        )


# ---------------------------------------------------------------------------
# Review status: seat exposure for the review panel
# ---------------------------------------------------------------------------


class TestReviewStatusSeat:
    def test_status_returns_assigned_seat_number(self, client, db):
        env = _mk_env(db, decision="INCONCLUSIVE")
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            resp = client.get(f"{REVIEW_URL}/{env.reg.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["seat_number"] == f"NMG-{env.student.usn[-3:]}"
        assert data["latest_attempt_decision"] == "INCONCLUSIVE"

"""REVERIFY — fresh verification attempt after NO_MATCH / INCONCLUSIVE.

Hard requirements covered:
- The previous attempt and all of its evidence are preserved (audit trail).
- The new attempt copies student/registration/hall-ticket binding and the
  stored reference_face_url, and starts CREATED / PENDING.
- Terminal-state preconditions: only COMPLETED/FAILED attempts may be
  reverified; MATCH results are not reverified; active attempts are not
  reverified and a second reverify is blocked by the duplicate-active rule.
- RBAC: ADMIN/OPERATOR/INVIGILATOR only, invigilator scope enforced.
"""

from contextlib import contextmanager
from datetime import date, time
from types import SimpleNamespace

import pytest
from sqlalchemy import delete

from app.auth import Role, get_current_user
from app.core.database import SessionLocal
from app.main import app
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationEvidence,
)
from app.models.invigilator_assignment import InvigilatorAssignment
from app.models.seat_assignment import SeatAssignment
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import User

REVERIFY_URL = "/api/v1/identity-verifications/{attempt_id}/reverify"


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def cleanup():
    """Remove RVW-prefixed test data before each test."""
    db = SessionLocal()
    try:
        from app.models.examination_session import ExaminationSession
        student_ids = db.query(Student.id).filter(Student.usn.ilike("RVW%"))
        reg_ids = db.query(ExamRegistration.id).filter(
            ExamRegistration.student_id.in_(student_ids)
        )
        attempt_ids = db.query(IdentityVerificationAttempt.id).filter(
            IdentityVerificationAttempt.exam_registration_id.in_(reg_ids)
        )
        exam_ids = db.query(Exam.id).filter(Exam.exam_name.ilike("RVW%"))
        db.execute(delete(IdentityVerificationEvidence).where(
            IdentityVerificationEvidence.attempt_id.in_(attempt_ids)
        ))
        db.execute(delete(IdentityVerificationAttempt).where(
            IdentityVerificationAttempt.id.in_(attempt_ids)
        ))
        db.execute(delete(InvigilatorAssignment).where(
            InvigilatorAssignment.exam_id.in_(exam_ids)
        ))
        db.execute(delete(SeatAssignment).where(
            SeatAssignment.exam_registration_id.in_(reg_ids)
        ))
        db.execute(delete(ExaminationSession).where(
            ExaminationSession.exam_id.in_(exam_ids)
        ))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.id.in_(reg_ids)
        ))
        db.execute(delete(Exam).where(Exam.id.in_(exam_ids)))
        db.execute(delete(ExamHall).where(ExamHall.building.ilike("RVW%")))
        db.execute(delete(Subject).where(Subject.code.ilike("RVWSUB%")))
        db.execute(delete(Student).where(Student.usn.ilike("RVW%")))
        db.execute(delete(User).where(User.email.ilike("rvw-%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


def _mk_env(
    db,
    *,
    usn="RVW001",
    exam_name="RVW Exam 1",
    status="COMPLETED",
    decision="NO_MATCH",
    reference_url="https://example.com/rvw-reference.jpg",
):
    subject = Subject(
        code=f"RVWSUB{usn[-3:]}", name="RVW Subject",
        department="RVW Dept", semester=6, credits=3,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)

    exam = Exam(
        subject_id=subject.id, exam_name=exam_name,
        exam_date=date(2026, 12, 2), start_time=time(9, 0),
        end_time=time(12, 0), semester=6, department="RVW Dept",
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    hall = ExamHall(building=f"RVW Hall {usn[-3:]}", room_number="101", capacity=50)
    db.add(hall)
    db.commit()
    db.refresh(hall)

    student = Student(usn=usn, name=f"RVW Student {usn[-3:]}")
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
    db.add(SeatAssignment(
        exam_registration_id=reg.id,
        exam_hall_id=hall.id,
        exam_id=exam.id,
        student_id=student.id,
        seat_number=f"RVW-{usn[-3:]}",
    ))
    db.commit()

    attempt = IdentityVerificationAttempt(
        student_id=student.id, exam_registration_id=reg.id,
        status=status, decision=decision,
        verification_method="FACE",
        reference_face_url=reference_url,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    # Create IN_PROGRESS session for the exam/hall (required for invigilator actions)
    from app.models.examination_session import ExaminationSession, SessionStatus
    session = ExaminationSession(
        exam_id=exam.id,
        exam_hall_id=hall.id,
        status=SessionStatus.IN_PROGRESS.value,
        gate_status="GATES_OPEN",
        expected_capacity=30,
        notes="Test session",
        created_by="test",
    )
    db.add(session)
    db.commit()

    return SimpleNamespace(
        subject=subject, exam=exam, hall=hall, student=student,
        reg=reg, attempt=attempt, session=session,
    )


def _seed_evidence(db, attempt_id, count=2):
    rows = []
    for i in range(count):
        ev = IdentityVerificationEvidence(
            attempt_id=attempt_id,
            signal_type="similarity_score",
            signal_value="0.404",
            confidence=0.404,
            provider_name="uniface",
            provider_version="4.0.0",
        )
        db.add(ev)
        rows.append(ev)
    db.commit()
    return rows


def _mk_invigilator(db, exam_id, hall_id, *, email="rvw-inv@example.com"):
    user = User(email=email, full_name="RVW Invigilator", role=Role.INVIGILATOR)
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


def _reverify(client, attempt_id):
    return client.post(REVERIFY_URL.format(attempt_id=attempt_id))


# ---------------------------------------------------------------------------
# Happy path: fresh attempt, history preserved
# ---------------------------------------------------------------------------


class TestReverifyHappyPath:
    def test_creates_fresh_attempt_and_preserves_history(self, client, db):
        env = _mk_env(db)
        evidence_rows = _seed_evidence(db, env.attempt.id, count=2)
        old_id = env.attempt.id

        resp = _reverify(client, old_id)

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] != old_id
        assert data["status"] == "CREATED"
        assert data["decision"] == "PENDING"
        assert data["student_id"] == env.student.id
        assert data["exam_registration_id"] == env.reg.id
        # Reference provenance carried over — no re-upload required.
        assert data["reference_face_url"] == env.attempt.reference_face_url
        assert data["verification_method"] == "FACE"

        # Previous attempt untouched: decision, status, evidence all intact.
        db.expire_all()
        old = (
            db.query(IdentityVerificationAttempt)
            .filter(IdentityVerificationAttempt.id == old_id)
            .one()
        )
        assert old.status == "COMPLETED"
        assert old.decision == "NO_MATCH"
        assert (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == old_id)
            .count()
            == len(evidence_rows)
        )
        # Fresh attempt starts with zero accumulated evidence.
        assert (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == data["id"])
            .count()
            == 0
        )

    def test_reverify_from_inconclusive_allowed(self, client, db):
        env = _mk_env(db, decision="INCONCLUSIVE")

        resp = _reverify(client, env.attempt.id)

        assert resp.status_code == 201
        assert resp.json()["decision"] == "PENDING"


# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------


class TestReverifyPreconditions:
    def test_rejected_while_previous_attempt_active(self, client, db):
        env = _mk_env(db, status="CREATED", decision="PENDING")

        resp = _reverify(client, env.attempt.id)

        assert resp.status_code == 422
        assert "finished" in resp.json()["detail"]

    def test_rejected_after_match(self, client, db):
        env = _mk_env(db, status="COMPLETED", decision="MATCH")

        resp = _reverify(client, env.attempt.id)

        assert resp.status_code == 422
        assert "MATCH" in resp.json()["detail"]

    def test_unknown_attempt_returns_404(self, client, db):
        resp = _reverify(client, 999999)

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_second_reverify_blocked_by_active_attempt(self, client, db):
        env = _mk_env(db)
        first = _reverify(client, env.attempt.id)
        assert first.status_code == 201

        # Re-referencing the ORIGINAL attempt while the fresh one is active
        # must not create a second active attempt.
        resp = _reverify(client, env.attempt.id)

        assert resp.status_code == 422
        assert "Active identity verification attempt already exists" in (
            resp.json()["detail"]
        )
        assert (
            db.query(IdentityVerificationAttempt)
            .filter(
                IdentityVerificationAttempt.exam_registration_id == env.reg.id
            )
            .count()
            == 2
        )


# ---------------------------------------------------------------------------
# RBAC & scope
# ---------------------------------------------------------------------------


class TestReverifyRBAC:
    def test_reviewer_role_forbidden(self, client, db):
        env = _mk_env(db)
        user = User(
            email="rvw-reviewer@example.com",
            full_name="RVW Reviewer",
            role=Role.REVIEWER,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        with _claims(user, role=Role.REVIEWER):
            resp = _reverify(client, env.attempt.id)

        assert resp.status_code == 403
        assert (
            db.query(IdentityVerificationAttempt)
            .filter(
                IdentityVerificationAttempt.exam_registration_id == env.reg.id
            )
            .count()
            == 1
        )

    def test_invigilator_out_of_scope_forbidden(self, client, db):
        env = _mk_env(db)
        other = _mk_env(db, usn="RVW002", exam_name="RVW Exam 2")
        user, _ = _mk_invigilator(db, other.exam.id, other.hall.id)

        with _claims(user):
            resp = _reverify(client, env.attempt.id)

        assert resp.status_code == 403
        assert (
            db.query(IdentityVerificationAttempt)
            .filter(
                IdentityVerificationAttempt.exam_registration_id == env.reg.id
            )
            .count()
            == 1
        )

    def test_invigilator_in_scope_allowed(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            resp = _reverify(client, env.attempt.id)

        assert resp.status_code == 201
        assert resp.json()["decision"] == "PENDING"

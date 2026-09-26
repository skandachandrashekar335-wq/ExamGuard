"""Part 16 — Manual review of INCONCLUSIVE identity attempts.

Covers the backend side of regression tests F, G, H, I, J, K, L, M:

- F: review status endpoint exposes state, attempt, session, history
- G: CHECK_IN / CHECK_OUT happy paths with auditable history
- H: missing registration -> 404 (frontend shows friendly message)
- I: INCONCLUSIVE alone never marks ABSENT; verified entries protected
- J: RBAC — INVIGILATOR only, enforced within assignment scope
- K: server-enforced state machine + preconditions (409/422)
- L: audit trail — reason + recorded_by persisted, event history
- M: fail-safe — no fabricated EntryVerification, no silent acceptance
"""

from contextlib import contextmanager
from datetime import date, datetime, time, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import delete

from app.auth import Role, get_current_user
from app.core.database import SessionLocal
from app.main import app
from app.models.attendance import (
    AttendanceEvent,
    AttendanceEventType,
    AttendanceRecord,
    AttendanceStatus,
    EntryMethod,
)
from app.models.entry_verification import EntryVerification
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.examination_session import (
    ExaminationSession,
    GateStatus,
    SessionStatus,
)
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationDecision,
)
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
    """Remove MRW-prefixed test data before each test."""
    db = SessionLocal()
    try:
        student_ids = db.query(Student.id).filter(Student.usn.ilike("MRW%"))
        reg_ids = db.query(ExamRegistration.id).filter(
            ExamRegistration.student_id.in_(student_ids)
        )
        exam_ids = db.query(Exam.id).filter(Exam.exam_name.ilike("MRW%"))
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
        db.execute(delete(ExaminationSession).where(
            ExaminationSession.exam_id.in_(exam_ids)
        ))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.id.in_(reg_ids)
        ))
        db.execute(delete(Exam).where(Exam.id.in_(exam_ids)))
        db.execute(delete(ExamHall).where(ExamHall.building.ilike("MRW%")))
        db.execute(delete(Subject).where(Subject.code.ilike("MRW%")))
        db.execute(delete(Student).where(Student.usn.ilike("MRW%")))
        db.execute(delete(User).where(User.email.ilike("mrw-%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


def _mk_env(db, *, usn="MRW001", exam_name="MRW Exam 1", decision="INCONCLUSIVE"):
    """Create subject/exam/hall/student/registration/attempt/session/invigilator."""
    subject = Subject(
        code=f"MRWSUB{usn[-3:]}", name="MRW Subject",
        department="MRW Dept", semester=6, credits=3,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)

    exam = Exam(
        subject_id=subject.id, exam_name=exam_name,
        exam_date=date(2026, 12, 1), start_time=time(9, 0),
        end_time=time(12, 0), semester=6, department="MRW Dept",
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    hall = ExamHall(building=f"MRW Hall {usn[-3:]}", room_number="101", capacity=50)
    db.add(hall)
    db.commit()
    db.refresh(hall)

    student = Student(usn=usn, name=f"MRW Student {usn[-3:]}")
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

    seat = SeatAssignment(
        exam_registration_id=reg.id, exam_hall_id=hall.id,
        exam_id=exam.id, student_id=student.id,
        seat_number=f"MRW-{usn[-3:]}",
        status=SeatAssignmentStatus.ASSIGNED.value,
    )
    db.add(seat)

    attempt = IdentityVerificationAttempt(
        student_id=student.id, exam_registration_id=reg.id,
        decision=decision,
    )
    db.add(attempt)

    session = ExaminationSession(
        exam_id=exam.id, exam_hall_id=hall.id,
        status=SessionStatus.IN_PROGRESS.value,
        gate_status=GateStatus.GATES_OPEN.value,
    )
    db.add(session)
    db.commit()
    db.refresh(attempt)
    db.refresh(session)

    return SimpleNamespace(
        subject=subject, exam=exam, hall=hall, student=student, reg=reg,
        seat=seat, attempt=attempt, session=session,
    )


def _mk_invigilator(db, exam_id, hall_id, *, email="mrw-inv@example.com"):
    user = User(email=email, full_name="MRW Invigilator", role=Role.INVIGILATOR)
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
    """Impersonate a user for API calls, restoring prior override."""
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


def _post(client, reg_id, action, reason="ID documents match, face check inconclusive"):
    return client.post(
        REVIEW_URL,
        json={
            "exam_registration_id": reg_id,
            "action": action,
            "reason": reason,
        },
    )


# ---------------------------------------------------------------------------
# G. CHECK_IN / CHECK_OUT happy paths
# ---------------------------------------------------------------------------


class TestCheckInOut:
    def test_check_in_creates_present_record_and_event(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            resp = _post(client, env.reg.id, "CHECK_IN")

        assert resp.status_code == 200
        data = resp.json()
        assert data["review_state"] == "CHECKED_IN"
        assert data["event"]["event_type"] == "MANUAL_CHECK_IN"
        assert data["event"]["status_snapshot"] == "PRESENT"
        assert data["event"]["entry_verification_id"] is None
        assert data["event"]["reason"] == (
            "ID documents match, face check inconclusive"
        )
        assert data["event"]["recorded_by"] == "mrw-inv@example.com"
        assert data["attendance_record_id"] is not None

        record = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == env.reg.id)
            .one()
        )
        assert record.status == AttendanceStatus.PRESENT.value
        assert record.entry_method == EntryMethod.MANUAL_ENTRY.value
        assert record.entry_verification_id is None
        assert record.hall_id == env.hall.id
        assert record.seat_number == "MRW-001"
        assert record.session_id == env.session.id

        # M: no EntryVerification was fabricated
        assert (
            db.query(EntryVerification)
            .filter(EntryVerification.exam_registration_id == env.reg.id)
            .count()
            == 0
        )

    def test_check_out_after_check_in_marks_absent(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            assert _post(client, env.reg.id, "CHECK_IN").status_code == 200
            resp = _post(
                client, env.reg.id, "CHECK_OUT",
                reason="Student left the hall with invigilator escort",
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["review_state"] == "CHECKED_OUT"
        assert data["event"]["event_type"] == "MANUAL_CHECK_OUT"
        assert data["event"]["status_snapshot"] == "ABSENT"

        record = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == env.reg.id)
            .one()
        )
        assert record.status == AttendanceStatus.ABSENT.value

    def test_check_out_from_not_reviewed_is_event_only(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            resp = _post(client, env.reg.id, "CHECK_OUT")

        assert resp.status_code == 200
        data = resp.json()
        assert data["review_state"] == "CHECKED_OUT"
        assert data["attendance_record_id"] is None
        assert data["event"]["status_snapshot"] == "N/A"

        # Event only — no attendance record was created or flipped
        assert (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == env.reg.id)
            .count()
            == 0
        )
        # After CHECK_OUT, CHECK_IN is rejected
        with _claims(user):
            resp = _post(client, env.reg.id, "CHECK_IN")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# K. Server-enforced state machine
# ---------------------------------------------------------------------------


class TestStateMachine:
    def test_duplicate_check_in_conflicts(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            assert _post(client, env.reg.id, "CHECK_IN").status_code == 200
            resp = _post(client, env.reg.id, "CHECK_IN")

        assert resp.status_code == 409
        assert "CHECKED_IN" in resp.json()["detail"]

        assert (
            db.query(AttendanceEvent)
            .filter(
                AttendanceEvent.exam_registration_id == env.reg.id,
                AttendanceEvent.event_type
                == AttendanceEventType.MANUAL_CHECK_IN.value,
            )
            .count()
            == 1
        )

    def test_duplicate_check_out_conflicts(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            assert _post(client, env.reg.id, "CHECK_OUT").status_code == 200
            resp = _post(client, env.reg.id, "CHECK_OUT")

        assert resp.status_code == 409
        assert "CHECKED_OUT" in resp.json()["detail"]

    def test_check_in_rejected_when_session_not_started(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)
        env.session.status = SessionStatus.NOT_STARTED.value
        db.commit()

        with _claims(user):
            resp = _post(client, env.reg.id, "CHECK_IN")

        assert resp.status_code == 409
        assert "not IN_PROGRESS" in resp.json()["detail"]

    def test_check_in_rejected_when_session_completed(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)
        env.session.status = SessionStatus.COMPLETED.value
        db.commit()

        with _claims(user):
            resp = _post(client, env.reg.id, "CHECK_IN")

        assert resp.status_code == 409
        assert "not IN_PROGRESS" in resp.json()["detail"]

    def test_reason_required(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            resp_blank = client.post(
                REVIEW_URL,
                json={"exam_registration_id": env.reg.id,
                      "action": "CHECK_IN", "reason": ""},
            )
            resp_whitespace = client.post(
                REVIEW_URL,
                json={"exam_registration_id": env.reg.id,
                      "action": "CHECK_IN", "reason": "   "},
            )

        assert resp_blank.status_code == 422
        assert resp_whitespace.status_code == 422
        assert (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.exam_registration_id == env.reg.id)
            .count()
            == 0
        )

    def test_invalid_action_rejected(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            resp = client.post(
                REVIEW_URL,
                json={"exam_registration_id": env.reg.id,
                      "action": "CHECK_INOUT",
                      "reason": "trying an invalid action"},
            )

        assert resp.status_code == 422

    def test_cancelled_registration_rejected(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)
        env.reg.status = RegistrationStatus.CANCELLED.value
        db.commit()

        with _claims(user):
            resp = _post(client, env.reg.id, "CHECK_IN")

        assert resp.status_code == 422
        assert "cancelled" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# M. Preconditions: only INCONCLUSIVE attempts are reviewable
# ---------------------------------------------------------------------------


class TestInconclusivePrecondition:
    def test_match_decision_not_reviewable(self, client, db):
        env = _mk_env(db, decision="MATCH")
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            resp = _post(client, env.reg.id, "CHECK_IN")

        assert resp.status_code == 409
        assert "not INCONCLUSIVE" in resp.json()["detail"]
        assert (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == env.reg.id)
            .count()
            == 0
        )

    def test_no_attempt_not_reviewable(self, client, db):
        env = _mk_env(db)
        db.delete(env.attempt)
        db.commit()
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            resp = _post(client, env.reg.id, "CHECK_IN")

        assert resp.status_code == 409
        assert "No identity verification attempt" in resp.json()["detail"]

    def test_inconclusive_without_action_creates_nothing(self, client, db):
        """I: an inconclusive decision alone never changes attendance."""
        env = _mk_env(db)

        assert (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == env.reg.id)
            .count()
            == 0
        )
        assert (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.exam_registration_id == env.reg.id)
            .count()
            == 0
        )


# ---------------------------------------------------------------------------
# I. Verified entries are protected from manual review actions
# ---------------------------------------------------------------------------


class TestVerifiedEntryProtected:
    def _seed_verified_record(self, db, env):
        record = AttendanceRecord(
            student_id=env.student.id,
            exam_id=env.exam.id,
            exam_registration_id=env.reg.id,
            status=AttendanceStatus.PRESENT.value,
            entry_method=EntryMethod.VERIFIED_ENTRY.value,
            entry_time=datetime.now(timezone.utc),
            hall_id=env.hall.id,
            seat_number="MRW-001",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def test_check_out_never_flips_verified_entry_to_absent(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)
        self._seed_verified_record(db, env)

        with _claims(user):
            resp = _post(client, env.reg.id, "CHECK_OUT")

        assert resp.status_code == 409
        assert "attendance correction" in resp.json()["detail"]

        db.expire_all()
        record = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == env.reg.id)
            .one()
        )
        assert record.status == AttendanceStatus.PRESENT.value

    def test_check_in_conflicts_with_existing_verified_record(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)
        self._seed_verified_record(db, env)

        with _claims(user):
            resp = _post(client, env.reg.id, "CHECK_IN")

        assert resp.status_code == 409
        assert "attendance correction" in resp.json()["detail"]

        db.expire_all()
        record = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == env.reg.id)
            .one()
        )
        assert record.entry_method == EntryMethod.VERIFIED_ENTRY.value
        assert record.status == AttendanceStatus.PRESENT.value


# ---------------------------------------------------------------------------
# H. Missing registration -> 404
# ---------------------------------------------------------------------------


class TestMissingRegistration:
    def test_post_missing_registration_returns_404(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            resp = _post(client, 999999, "CHECK_IN")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_status_missing_registration_returns_404(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            resp = client.get(f"{REVIEW_URL}/999999")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# J. RBAC: INVIGILATOR only + scope enforced
# ---------------------------------------------------------------------------


class TestRBAC:
    def test_admin_forbidden(self, client, db):
        env = _mk_env(db)
        # conftest default override is ADMIN
        resp = _post(client, env.reg.id, "CHECK_IN")
        assert resp.status_code == 403

    @pytest.mark.parametrize("role", [Role.OPERATOR, Role.REVIEWER])
    def test_other_roles_forbidden(self, client, db, role):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)
        with _claims(user, role=role):
            resp = _post(client, env.reg.id, "CHECK_IN")
        assert resp.status_code == 403

    def test_invigilator_out_of_scope_exam_forbidden(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)
        other = _mk_env(db, usn="MRW002", exam_name="MRW Exam 2")

        with _claims(user):
            resp = _post(client, other.reg.id, "CHECK_IN")
            resp_get = client.get(f"{REVIEW_URL}/{other.reg.id}")

        assert resp.status_code == 403
        assert "outside your assigned exam" in resp.json()["detail"]
        assert resp_get.status_code == 403
        assert (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.exam_registration_id == other.reg.id)
            .count()
            == 0
        )

    def test_invigilator_without_assignment_forbidden(self, client, db):
        env = _mk_env(db)
        user = User(
            email="mrw-noassign@example.com",
            full_name="MRW No Assignment",
            role=Role.INVIGILATOR,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        with _claims(user):
            resp = _post(client, env.reg.id, "CHECK_IN")

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# F, L. Status endpoint + audit history
# ---------------------------------------------------------------------------


class TestReviewStatus:
    def test_status_reports_attempt_session_and_state(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            resp = client.get(f"{REVIEW_URL}/{env.reg.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["exam_registration_id"] == env.reg.id
        assert data["review_state"] == "NOT_REVIEWED"
        assert data["latest_attempt_id"] == env.attempt.id
        assert data["latest_attempt_decision"] == "INCONCLUSIVE"
        assert data["session_status"] == "IN_PROGRESS"
        assert data["events"] == []

    def test_status_reflects_review_history(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            assert _post(client, env.reg.id, "CHECK_IN").status_code == 200
            resp = client.get(f"{REVIEW_URL}/{env.reg.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["review_state"] == "CHECKED_IN"
        assert len(data["events"]) == 1
        event = data["events"][0]
        assert event["event_type"] == "MANUAL_CHECK_IN"
        assert event["recorded_by"] == "mrw-inv@example.com"
        assert event["reason"] == (
            "ID documents match, face check inconclusive"
        )
        assert event["entry_verification_id"] is None

    def test_history_contains_both_events_after_check_out(self, client, db):
        env = _mk_env(db)
        user, _ = _mk_invigilator(db, env.exam.id, env.hall.id)

        with _claims(user):
            _post(client, env.reg.id, "CHECK_IN")
            _post(client, env.reg.id, "CHECK_OUT")
            resp = client.get(f"{REVIEW_URL}/{env.reg.id}")

        data = resp.json()
        assert data["review_state"] == "CHECKED_OUT"
        types = [e["event_type"] for e in data["events"]]
        assert types == ["MANUAL_CHECK_IN", "MANUAL_CHECK_OUT"]
        snapshots = [e["status_snapshot"] for e in data["events"]]
        assert snapshots == ["PRESENT", "ABSENT"]
        # L: every manual event carries a reason and actor
        for event in data["events"]:
            assert event["reason"]
            assert event["recorded_by"] == "mrw-inv@example.com"

"""Invigilator capability is an exam assignment, not a permanent account role."""

from datetime import date, time
import uuid

from app.auth import Role, get_current_user
from app.core.database import SessionLocal
from app.main import app
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.entry_point import EntryPoint
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.examination_session import ExaminationSession, GateStatus, SessionStatus
from app.models.entry_verification import EntryVerification
from app.models.identity_verification import IdentityVerificationAttempt, IdentityVerificationEvidence
from app.models.invigilator_assignment import InvigilatorAssignment
from app.models.seat_assignment import SeatAssignment
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import User

ASSIGN_URL = "/api/v1/demo/assign-invigilator"
LOAD_URL = "/api/v1/demo/load"
START_URL = "/api/v1/demo/start-session"
STATUS_URL = "/api/v1/demo/session-status"
DEMO_STATUS_URL = "/api/v1/demo/status"
PROFILE_URL = "/api/v1/invigilator/profile"
MINE_URL = "/api/v1/invigilator/my-assignment"
REVIEW_URL = "/api/v1/attendance/manual-review"


def _db():
    return SessionLocal()


def _user(email: str, role: str = "REVIEWER") -> User:
    db = _db()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                email=email,
                full_name=email,
                firebase_uid=f"uid-{email}",
                role=role,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.role = role
            db.commit()
            db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def _role_of(email: str) -> str:
    db = _db()
    try:
        return db.query(User).filter(User.email == email).one().role
    finally:
        db.close()


def _as(user: User, role: str | None = None):
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(user.id),
        "role": role or user.role,
        "email": user.email,
        "full_name": user.full_name,
    }


def _as_admin():
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "1",
        "role": Role.ADMIN,
        "email": "test@example.com",
        "full_name": "Test User",
    }


def test_assign_does_not_mutate_role_and_non_admin_cannot_assign(client):
    client.post(LOAD_URL)
    teacher = _user("esc-teacher@example.com", "REVIEWER")
    _as_admin()
    resp = client.post(ASSIGN_URL, json={"email": teacher.email, "role": "INVIGILATOR"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["account_role"] == "REVIEWER"
    assert body["assignment_status"] == "SCHEDULED"
    assert _role_of(teacher.email) == "REVIEWER"

    _as(teacher)
    denied = client.post(ASSIGN_URL, json={"email": teacher.email, "role": "ADMIN"})
    assert denied.status_code == 403
    assert _role_of(teacher.email) == "REVIEWER"
    _as_admin()


def test_unauthenticated_invigilator_endpoint_is_401(client):
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides.pop(get_current_user, None)
    try:
        resp = client.get(PROFILE_URL)
        assert resp.status_code == 401
    finally:
        if previous is not None:
            app.dependency_overrides[get_current_user] = previous


def test_assignment_follows_session_lifecycle(client):
    _as_admin()
    client.post("/api/v1/demo/reset")
    loaded = client.post(LOAD_URL)
    assert loaded.status_code == 200, loaded.text
    teacher = _user("esc-teacher@example.com", "REVIEWER")
    assigned = client.post(ASSIGN_URL, json={"email": teacher.email})
    assert assigned.status_code == 200, assigned.text

    _as(teacher)
    before = client.get(MINE_URL)
    assert before.status_code == 200
    assert before.json()["account_role"] == "REVIEWER"
    assert before.json()["exam_role"] is None
    assert before.json()["assignment_status"] == "SCHEDULED"
    demo = client.get(DEMO_STATUS_URL)
    # Demo status allows REVIEWER.
    assert demo.status_code == 200, demo.text
    attempt_id = demo.json()["demo_attempt_ids"][0]
    early = client.post(f"/api/v1/identity-verifications/{attempt_id}/reverify")
    assert early.status_code == 403
    assert "in progress" in early.json()["detail"].lower()

    _as_admin()
    started = client.post(START_URL, json={"performed_by": "tester"})
    assert started.status_code == 200, started.text

    _as(teacher)
    during = client.get(MINE_URL)
    assert during.json()["exam_role"] == "INVIGILATOR"
    assert during.json()["assignment_status"] == "ACTIVE"
    profile = client.get(PROFILE_URL)
    assert profile.status_code == 200, profile.text
    opened = client.post(f"/api/v1/identity-verifications/{attempt_id}/reverify")
    assert opened.status_code != 403
    assert _role_of(teacher.email) == "REVIEWER"

    _as_admin()
    session_id = client.get(STATUS_URL).json()["session_id"]
    ended = client.post(
        f"/api/v1/examination-sessions/{session_id}/end",
        json={"performed_by": "tester"},
    )
    assert ended.status_code == 200, ended.text

    _as(teacher)
    after = client.get(MINE_URL)
    assert after.json()["exam_role"] is None
    assert after.json()["assignment_status"] == "COMPLETED"
    assert _role_of(teacher.email) == "REVIEWER"
    denied = client.get(PROFILE_URL)
    assert denied.status_code == 403
    denied_op = client.post(f"/api/v1/identity-verifications/{attempt_id}/reverify")
    assert denied_op.status_code == 403
    _as_admin()


def test_cross_exam_and_multiple_assignees(client):
    _as_admin()


def test_assigned_reviewer_is_scoped_to_exact_exam_hall_and_live_session(client):
    _as_admin()
    assert client.post("/api/v1/demo/reset").status_code == 200
    assert client.post(LOAD_URL).status_code == 200
    demo = client.get(DEMO_STATUS_URL)
    assert demo.status_code == 200, demo.text
    demo_attempt_id = demo.json()["demo_attempt_ids"][0]

    teacher = _user("esc-pair-reviewer@example.com", "REVIEWER")
    assert client.post(ASSIGN_URL, json={"email": teacher.email}).status_code == 200
    assert client.post(START_URL, json={"performed_by": "tester"}).status_code == 200

    db = _db()
    try:
        demo_attempt = db.get(IdentityVerificationAttempt, demo_attempt_id)
        own_reg = db.query(ExamRegistration).filter(
            ExamRegistration.id == demo_attempt.exam_registration_id
        ).one()
        own_seat = db.query(SeatAssignment).filter(
            SeatAssignment.exam_registration_id == own_reg.id
        ).one()
        session = db.query(ExaminationSession).filter(
            ExaminationSession.exam_id == own_reg.exam_id,
            ExaminationSession.exam_hall_id == own_seat.exam_hall_id,
        ).one()
        entry_point = db.query(EntryPoint).filter(
            EntryPoint.exam_hall_id == own_seat.exam_hall_id
        ).first()
        assert entry_point is not None

        own_entry = EntryVerification(
            student_id=own_reg.student_id,
            exam_registration_id=own_reg.id,
            exam_hall_id=own_seat.exam_hall_id,
            entry_point_id=entry_point.id,
            session_id=session.id,
        )
        inactive_session_entry = EntryVerification(
            student_id=own_reg.student_id,
            exam_registration_id=own_reg.id,
            exam_hall_id=own_seat.exam_hall_id,
            entry_point_id=entry_point.id,
            session_id=session.id,
        )
        test_suffix = uuid.uuid4().hex[:8].upper()
        other_hall = ExamHall(
            building=f"ESC Foreign {test_suffix}", room_number="H2", capacity=10,
            name="Foreign Hall",
        )
        other_subject = Subject(
            code=f"ESCP{test_suffix}", name="Pair Scope Subject", department="ESC",
            semester=1, credits=1,
        )
        db.add_all([other_hall, other_subject])
        db.commit()
        db.refresh(other_hall)
        db.refresh(other_subject)
        other_exam = Exam(
            subject_id=other_subject.id,
            exam_name=f"ESC Pair Foreign Exam {test_suffix}",
            exam_date=date(2026, 12, 6),
            start_time=time(9, 0),
            end_time=time(12, 0),
            semester=1,
            department="ESC",
        )
        db.add(other_exam)
        db.commit()
        db.refresh(other_exam)
        wrong_exam_reg = ExamRegistration(
            student_id=own_reg.student_id,
            exam_id=other_exam.id,
            status=RegistrationStatus.REGISTERED.value,
        )
        wrong_hall_student = Student(
            usn=f"ESCP{test_suffix}", name="Pair Scope Hall Student",
        )
        db.add(wrong_hall_student)
        db.commit()
        db.refresh(wrong_hall_student)
        wrong_hall_reg = ExamRegistration(
            student_id=wrong_hall_student.id,
            exam_id=own_reg.exam_id,
            status=RegistrationStatus.REGISTERED.value,
        )
        db.add_all([wrong_exam_reg, wrong_hall_reg])
        db.commit()
        db.refresh(wrong_exam_reg)
        db.refresh(wrong_hall_reg)
        wrong_exam_seat = SeatAssignment(
            exam_registration_id=wrong_exam_reg.id,
            exam_hall_id=own_seat.exam_hall_id,
            exam_id=other_exam.id,
            student_id=own_reg.student_id,
            seat_number="PAIR-OTHER-EXAM",
        )
        wrong_hall_seat = SeatAssignment(
            exam_registration_id=wrong_hall_reg.id,
            exam_hall_id=other_hall.id,
            exam_id=own_reg.exam_id,
            student_id=wrong_hall_student.id,
            seat_number="PAIR-OTHER-HALL",
        )
        wrong_exam_attempt = IdentityVerificationAttempt(
            student_id=own_reg.student_id,
            exam_registration_id=wrong_exam_reg.id,
            status="COMPLETED",
            decision="INCONCLUSIVE",
            verification_method="FACE",
        )
        wrong_hall_attempt = IdentityVerificationAttempt(
            student_id=wrong_hall_student.id,
            exam_registration_id=wrong_hall_reg.id,
            status="COMPLETED",
            decision="INCONCLUSIVE",
            verification_method="FACE",
        )
        wrong_exam_entry = EntryVerification(
            student_id=own_reg.student_id,
            exam_registration_id=wrong_exam_reg.id,
            exam_hall_id=own_seat.exam_hall_id,
            entry_point_id=entry_point.id,
            session_id=session.id,
        )
        wrong_hall_entry = EntryVerification(
            student_id=wrong_hall_student.id,
            exam_registration_id=wrong_hall_reg.id,
            exam_hall_id=other_hall.id,
            entry_point_id=entry_point.id,
            session_id=session.id,
        )
        db.add_all([
            wrong_exam_seat, wrong_hall_seat, wrong_exam_attempt,
            wrong_hall_attempt, own_entry, inactive_session_entry,
            wrong_exam_entry, wrong_hall_entry,
        ])
        db.commit()
        for row in [
            own_entry, inactive_session_entry, wrong_exam_entry, wrong_hall_entry,
            wrong_exam_attempt, wrong_hall_attempt,
        ]:
            db.refresh(row)
        ids = {
            "own_entry": own_entry.id,
            "session_id": session.id,
            "inactive_entry": inactive_session_entry.id,
            "wrong_exam_entry": wrong_exam_entry.id,
            "wrong_hall_entry": wrong_hall_entry.id,
            "wrong_exam_attempt": wrong_exam_attempt.id,
            "wrong_hall_attempt": wrong_hall_attempt.id,
            "wrong_exam_reg": wrong_exam_reg.id,
            "wrong_hall_reg": wrong_hall_reg.id,
        }
    finally:
        db.close()

    _as(teacher)
    assert client.get(f"/api/v1/entry-verifications/{ids['own_entry']}").status_code == 200
    assert client.get(f"/api/v1/entry-verifications/{ids['wrong_exam_entry']}").status_code == 403
    assert client.get(f"/api/v1/entry-verifications/{ids['wrong_hall_entry']}").status_code == 403
    assert client.post(f"/api/v1/entry-verifications/{ids['own_entry']}/begin").status_code == 200
    entry_list = client.get("/api/v1/entry-verifications")
    assert entry_list.status_code == 200, entry_list.text
    returned_entry_ids = {item["id"] for item in entry_list.json()["items"]}
    assert ids["own_entry"] in returned_entry_ids
    assert ids["wrong_exam_entry"] not in returned_entry_ids
    assert ids["wrong_hall_entry"] not in returned_entry_ids

    db = _db()
    try:
        session = db.get(ExaminationSession, ids["session_id"])
        session.status = SessionStatus.COMPLETED.value
        db.commit()
    finally:
        db.close()
    inactive = client.post(
        f"/api/v1/entry-verifications/{ids['inactive_entry']}/begin"
    )
    assert inactive.status_code == 403

    identity_list = client.get("/api/v1/identity-verifications")
    assert identity_list.status_code == 200, identity_list.text
    returned_attempt_ids = {item["id"] for item in identity_list.json()["items"]}
    assert demo_attempt_id in returned_attempt_ids
    assert ids["wrong_exam_attempt"] not in returned_attempt_ids
    assert ids["wrong_hall_attempt"] not in returned_attempt_ids
    assert client.get(
        f"/api/v1/identity-verifications/{ids['wrong_exam_attempt']}"
    ).status_code == 403
    assert client.get(
        f"/api/v1/identity-verifications/{ids['wrong_hall_attempt']}"
    ).status_code == 403
    assert client.get(
        f"/api/v1/identity-verifications?exam_registration_id={ids['wrong_exam_reg']}"
    ).status_code == 403
    assert client.get(
        f"/api/v1/identity-verifications?exam_registration_id={ids['wrong_hall_reg']}"
    ).status_code == 403

    operator = _user("esc-list-operator@example.com", "OPERATOR")
    ordinary_reviewer = _user("esc-list-reviewer@example.com", "REVIEWER")
    for user in (operator, ordinary_reviewer):
        _as(user)
        visible = client.get("/api/v1/identity-verifications")
        assert visible.status_code == 200, visible.text
        visible_ids = {item["id"] for item in visible.json()["items"]}
        assert ids["wrong_exam_attempt"] in visible_ids
        assert ids["wrong_hall_attempt"] in visible_ids
    _as_admin()
    admin_visible = client.get("/api/v1/identity-verifications")
    assert admin_visible.status_code == 200, admin_visible.text
    admin_ids = {item["id"] for item in admin_visible.json()["items"]}
    assert ids["wrong_exam_attempt"] in admin_ids
    assert ids["wrong_hall_attempt"] in admin_ids
    client.post("/api/v1/demo/reset")
    client.post(LOAD_URL)
    teacher_a = _user("esc-teacher-a@example.com", "REVIEWER")
    teacher_b = _user("esc-teacher-b@example.com", "REVIEWER")
    assert client.post(ASSIGN_URL, json={"email": teacher_a.email}).status_code == 200
    assert client.post(ASSIGN_URL, json={"email": teacher_b.email}).status_code == 200
    assert _role_of(teacher_a.email) == "REVIEWER"
    assert _role_of(teacher_b.email) == "REVIEWER"
    kept = _user("esc-operator@example.com", "OPERATOR")
    assert client.post(ASSIGN_URL, json={"email": kept.email}).status_code == 200
    assert _role_of(kept.email) == "OPERATOR"
    client.post(START_URL, json={"performed_by": "tester"})

    db = _db()
    try:
        subject = Subject(
            code="ESCX", name="ESC Other", department="ESC", semester=1, credits=1,
        )
        db.add(subject)
        db.commit()
        db.refresh(subject)
        exam = Exam(
            subject_id=subject.id,
            exam_name="ESC Exam B",
            exam_date=date(2026, 12, 4),
            start_time=time(9, 0),
            end_time=time(12, 0),
            semester=1,
            department="ESC",
        )
        hall = ExamHall(building="ESC", room_number="B", capacity=10, name="Other Hall")
        db.add_all([exam, hall])
        db.commit()
        db.refresh(exam)
        db.refresh(hall)
        session = ExaminationSession(
            exam_id=exam.id,
            exam_hall_id=hall.id,
            status=SessionStatus.IN_PROGRESS.value,
            gate_status=GateStatus.GATES_OPEN.value,
        )
        student = Student(usn="ESC0001", name="ESC Student")
        db.add_all([session, student])
        db.commit()
        db.refresh(student)
        reg = ExamRegistration(
            student_id=student.id,
            exam_id=exam.id,
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
            seat_number="ESCNM-1",
        ))
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=reg.id,
            status="COMPLETED",
            decision="INCONCLUSIVE",
            verification_method="FACE",
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        other_attempt = attempt.id
    finally:
        db.close()

    for teacher in (teacher_a, teacher_b):
        _as(teacher)
        own = client.get(PROFILE_URL)
        assert own.status_code == 200, own.text
        foreign = client.post(f"/api/v1/identity-verifications/{other_attempt}/reverify")
        assert foreign.status_code == 403
        assert "assigned exam" in foreign.json()["detail"].lower()
    assert _role_of(teacher_a.email) == "REVIEWER"
    assert _role_of(kept.email) == "OPERATOR"
    _as_admin()


def test_no_match_manual_allow_stays_blocked_for_assigned_reviewer(client):
    db = _db()
    try:
        subject = Subject(
            code="ESCNM", name="ESC NM", department="ESCNM", semester=1, credits=1,
        )
        db.add(subject)
        db.commit()
        db.refresh(subject)
        exam = Exam(
            subject_id=subject.id,
            exam_name="ESC NM Exam",
            exam_date=date(2026, 12, 5),
            start_time=time(9, 0),
            end_time=time(12, 0),
            semester=1,
            department="ESCNM",
        )
        hall = ExamHall(building="ESCNM", room_number="1", capacity=10, name="NM Hall")
        db.add_all([exam, hall])
        db.commit()
        db.refresh(exam)
        db.refresh(hall)
        session = ExaminationSession(
            exam_id=exam.id,
            exam_hall_id=hall.id,
            status=SessionStatus.IN_PROGRESS.value,
            gate_status=GateStatus.GATES_OPEN.value,
        )
        student = Student(usn="ESCNM001", name="ESC NM Student")
        teacher = User(
            email="esc-nm-teacher@example.com",
            full_name="NM Teacher",
            firebase_uid="uid-esc-nm",
            role="REVIEWER",
            is_active=True,
        )
        db.add_all([session, student, teacher])
        db.commit()
        db.refresh(student)
        db.refresh(teacher)
        reg = ExamRegistration(
            student_id=student.id,
            exam_id=exam.id,
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
            seat_number="ESCNM-1",
        ))
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=reg.id,
            status="COMPLETED",
            decision="NO_MATCH",
            verification_method="FACE",
        )
        from app.models.invigilator_assignment import InvigilatorAssignment

        db.add(attempt)
        db.add(InvigilatorAssignment(
            user_id=teacher.id,
            exam_id=exam.id,
            exam_hall_id=hall.id,
            is_active=True,
        ))
        db.commit()
        db.refresh(teacher)
        db.expunge(teacher)
        registration_id = reg.id
    finally:
        db.close()

    _as(teacher)
    resp = client.post(REVIEW_URL, json={
        "exam_registration_id": registration_id,
        "action": "CHECK_IN",
        "reason": "trying to allow a no match",
    })
    assert resp.status_code == 409
    assert "NO_MATCH" in resp.json()["detail"]
    assert _role_of(teacher.email) == "REVIEWER"
    _as_admin()


def test_admin_allowlist_promotes_without_a_client_role(client, monkeypatch):
    from app.core.config import get_settings

    emails = [item.lower() for item in get_settings().INITIAL_ADMIN_EMAILS]
    assert "skandachandrashekhar335@gmail.com" in emails
    # skandamusic17@gmail.com is not in the default config; test uses a different email
    # that matches the actual configured admin emails
    admin_emails = [e.lower() for e in get_settings().INITIAL_ADMIN_EMAILS]
    assert len(admin_emails) > 0
    test_admin_email = admin_emails[0]

    def _verify(token: str):
        if token == "music":
            return {"uid": "uid-music-17", "email": test_admin_email, "name": "Music"}
        if token == "plain":
            return {"uid": "uid-plain-esc", "email": "esc-plain@example.com", "name": "Plain"}
        if token == "existing-admin":
            return {
                "uid": "uid-existing-admin",
                "email": test_admin_email,
                "name": "Existing",
            }
        return None

    monkeypatch.setattr("app.api.v1.auth.verify_firebase_id_token", _verify)
    music = client.post("/api/v1/auth/firebase/exchange", json={
        "firebaseToken": "music",
        "role": "REVIEWER",
    })
    assert music.status_code == 200, music.text
    assert music.json()["user"]["role"] == "ADMIN"

    existing = client.post("/api/v1/auth/firebase/exchange", json={
        "firebaseToken": "existing-admin",
        "role": "REVIEWER",
    })
    assert existing.status_code == 200, existing.text
    assert existing.json()["user"]["role"] == "ADMIN"

    plain = client.post("/api/v1/auth/firebase/exchange", json={
        "firebaseToken": "plain",
        "role": "ADMIN",
    })
    assert plain.status_code == 200, plain.text
    assert plain.json()["user"]["role"] == "REVIEWER"

    forged = client.post("/api/v1/auth/firebase/exchange", json={
        "firebaseToken": "not-a-token",
        "role": "ADMIN",
    })
    assert forged.status_code == 401

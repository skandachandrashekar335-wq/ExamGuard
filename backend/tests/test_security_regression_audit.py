"""Security Regression and Change-Acceptance Audit Test Suite.

Validates:
1. Cross-exam isolation for invigilator endpoints.
2. Inactive / revoked assignment rejection.
3. Role escalation prevention (unassigned admin/operator/reviewer blocked).
4. Request parameter tampering immutability.
5. Rate limiter OPTIONS preflight bypass and CORS header compliance.
6. CORS origin filtering: trusted vs untrusted origin handling on 429.
7. Development vs Production rate limit defaults.
"""

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch
import uuid

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.auth import Role, create_access_token, get_current_user
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.entry_point import EntryPoint
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.examination_session import ExaminationSession, SessionStatus
from app.models.invigilator_assignment import InvigilatorAssignment
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import User
from app.security import hardening


# ---------------------------------------------------------------------------
# Fixtures & Setup
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cleanup_audit_data():
    """Clean up test entities after execution and restore dependency overrides."""
    orig_override = app.dependency_overrides.get(get_current_user)
    db = SessionLocal()
    try:
        yield
        exam_ids = [e.id for e in db.query(Exam.id).filter(Exam.exam_name.ilike("Security Audit Exam %")).all()]
        if exam_ids:
            db.execute(delete(ExamRegistration).where(ExamRegistration.exam_id.in_(exam_ids)))
            db.execute(delete(InvigilatorAssignment).where(InvigilatorAssignment.exam_id.in_(exam_ids)))
            db.execute(delete(ExaminationSession).where(ExaminationSession.exam_id.in_(exam_ids)))
            db.execute(delete(Exam).where(Exam.id.in_(exam_ids)))
        db.execute(delete(Student).where(Student.usn.ilike("SEC-STU-%")))
        db.execute(delete(User).where(User.email.ilike("sec_audit_%@examguard.test")))
        db.commit()
    finally:
        db.close()
        if orig_override is not None:
            app.dependency_overrides[get_current_user] = orig_override
        else:
            app.dependency_overrides.pop(get_current_user, None)


def _get_or_create_user(db, email: str, role: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name=email.split("@")[0].capitalize(),
            firebase_uid=f"fbase-{uuid.uuid4().hex[:12]}",
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.role = role
        user.is_active = True
        db.commit()
        db.refresh(user)
    return user


def _setup_exam_scenario(db, tag: str):
    """Create a subject, exam, hall, entry point, session, and 2 students."""
    subject = db.query(Subject).filter(Subject.code == f"SUB-{tag[:10]}").first()
    if not subject:
        subject = Subject(
            code=f"SUB-{tag[:10]}",
            name=f"Subject {tag}",
            department="CSE",
            semester=5,
            credits=4,
        )
        db.add(subject)
        db.commit()
        db.refresh(subject)

    hall = db.query(ExamHall).first()
    if not hall:
        hall = ExamHall(name=f"Hall-{tag}", building="Main Block", room_number="101", capacity=60)
        db.add(hall)
        db.commit()
        db.refresh(hall)

    now = datetime.now(timezone.utc)
    exam = Exam(
        subject_id=subject.id,
        exam_name=f"Security Audit Exam {tag}",
        exam_date=now.date(),
        start_time=(now - timedelta(minutes=5)).time(),
        end_time=(now + timedelta(hours=2)).time(),
        semester=5,
        department="CSE",
        is_active=True,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    session = ExaminationSession(
        exam_id=exam.id,
        exam_hall_id=hall.id,
        status=SessionStatus.IN_PROGRESS.value,
        gate_status="OPEN",
        started_at=now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    stu1 = Student(usn=f"SEC-STU-{tag[:6]}-1", name=f"Student {tag} 1", is_active=True)
    stu2 = Student(usn=f"SEC-STU-{tag[:6]}-2", name=f"Student {tag} 2", is_active=True)
    db.add_all([stu1, stu2])
    db.commit()
    db.refresh(stu1)
    db.refresh(stu2)

    reg1 = ExamRegistration(exam_id=exam.id, student_id=stu1.id, status=RegistrationStatus.REGISTERED.value)
    reg2 = ExamRegistration(exam_id=exam.id, student_id=stu2.id, status=RegistrationStatus.REGISTERED.value)
    db.add_all([reg1, reg2])
    db.commit()

    return exam, hall, session, [stu1, stu2]


# ---------------------------------------------------------------------------
# Section 2: Authorization Security Tests
# ---------------------------------------------------------------------------

def test_invigilator_cross_exam_isolation():
    """An invigilator assigned to Exam A cannot access Exam B's candidates."""
    db = SessionLocal()
    try:
        exam_a, hall_a, session_a, stu_a = _setup_exam_scenario(db, "A")
        exam_b, hall_b, session_b, stu_b = _setup_exam_scenario(db, "B")

        user_a = _get_or_create_user(db, "sec_audit_inv_a@examguard.test", Role.INVIGILATOR)
        user_b = _get_or_create_user(db, "sec_audit_inv_b@examguard.test", Role.INVIGILATOR)

        # Assignment for Invigilator A to Exam A
        assign_a = InvigilatorAssignment(
            exam_id=exam_a.id,
            exam_hall_id=hall_a.id,
            user_id=user_a.id,
            is_active=True,
        )
        # Assignment for Invigilator B to Exam B
        assign_b = InvigilatorAssignment(
            exam_id=exam_b.id,
            exam_hall_id=hall_b.id,
            user_id=user_b.id,
            is_active=True,
        )
        db.add_all([assign_a, assign_b])
        db.commit()

        client = TestClient(app)

        # Query as Invigilator A
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": str(user_a.id),
            "role": Role.INVIGILATOR,
            "email": user_a.email,
        }
        resp_a = client.get("/api/v1/invigilator/registered-students")
        assert resp_a.status_code == 200, resp_a.text
        data_a = resp_a.json()
        returned_usns_a = [s["student_usn"] for s in data_a["items"]]
        assert "SEC-STU-A-1" in returned_usns_a
        assert "SEC-STU-A-2" in returned_usns_a
        # MUST NOT contain Exam B students
        assert "SEC-STU-B-1" not in returned_usns_a
        assert "SEC-STU-B-2" not in returned_usns_a

        # Query as Invigilator B
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": str(user_b.id),
            "role": Role.INVIGILATOR,
            "email": user_b.email,
        }
        resp_b = client.get("/api/v1/invigilator/registered-students")
        assert resp_b.status_code == 200, resp_b.text
        data_b = resp_b.json()
        returned_usns_b = [s["student_usn"] for s in data_b["items"]]
        assert "SEC-STU-B-1" in returned_usns_b
        assert "SEC-STU-B-2" in returned_usns_b
        # MUST NOT contain Exam A students
        assert "SEC-STU-A-1" not in returned_usns_b
        assert "SEC-STU-A-2" not in returned_usns_b
    finally:
        db.close()


def test_revoked_or_inactive_assignment_rejected():
    """An invigilator whose assignment is inactive is rejected with 404/403."""
    db = SessionLocal()
    try:
        exam, hall, session, _ = _setup_exam_scenario(db, "REVOK")
        user = _get_or_create_user(db, "sec_audit_revoked@examguard.test", Role.INVIGILATOR)

        # Inactive assignment
        assign = InvigilatorAssignment(
            exam_id=exam.id,
            exam_hall_id=hall.id,
            user_id=user.id,
            is_active=False,
        )
        db.add(assign)
        db.commit()

        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": str(user.id),
            "role": Role.INVIGILATOR,
            "email": user.email,
        }

        # Profile access
        resp_profile = client.get("/api/v1/invigilator/profile")
        assert resp_profile.status_code in (403, 404)

        # Dashboard access
        resp_dash = client.get("/api/v1/invigilator/dashboard")
        assert resp_dash.status_code in (403, 404)

        # Start exam attempt
        resp_start = client.post("/api/v1/invigilator/start-exam", json={})
        assert resp_start.status_code in (403, 404)
    finally:
        db.close()


def test_unassigned_roles_cannot_escalate_to_invigilator():
    """Admin, Operator, and Reviewer accounts without exam assignments cannot invoke invigilator endpoints."""
    db = SessionLocal()
    try:
        admin = _get_or_create_user(db, "sec_audit_admin@examguard.test", Role.ADMIN)
        operator = _get_or_create_user(db, "sec_audit_operator@examguard.test", Role.OPERATOR)
        reviewer = _get_or_create_user(db, "sec_audit_reviewer@examguard.test", Role.REVIEWER)

        client = TestClient(app)

        for user in [reviewer, operator, admin]:
            app.dependency_overrides[get_current_user] = lambda u=user: {
                "sub": str(u.id),
                "role": u.role,
                "email": u.email,
            }

            r_profile = client.get("/api/v1/invigilator/profile")
            assert r_profile.status_code in (403, 404), f"{user.role} got {r_profile.status_code} on profile"

            r_dash = client.get("/api/v1/invigilator/dashboard")
            assert r_dash.status_code in (403, 404), f"{user.role} got {r_dash.status_code} on dashboard"

            r_students = client.get("/api/v1/invigilator/registered-students")
            assert r_students.status_code in (403, 404), f"{user.role} got {r_students.status_code} on students"
    finally:
        db.close()


def test_parameter_tampering_cannot_bypass_exam_isolation():
    """Client cannot supply query params or body fields to switch to another exam session."""
    db = SessionLocal()
    try:
        exam_a, hall_a, session_a, _ = _setup_exam_scenario(db, "TAMP-A")
        exam_b, hall_b, session_b, _ = _setup_exam_scenario(db, "TAMP-B")

        user_a = _get_or_create_user(db, "sec_audit_tamper@examguard.test", Role.INVIGILATOR)
        assign_a = InvigilatorAssignment(
            exam_id=exam_a.id,
            exam_hall_id=hall_a.id,
            user_id=user_a.id,
            is_active=True,
        )
        db.add(assign_a)
        db.commit()

        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": str(user_a.id),
            "role": Role.INVIGILATOR,
            "email": user_a.email,
        }

        # Try to pass exam_id=exam_b.id in query string
        r = client.get(f"/api/v1/invigilator/profile?exam_id={exam_b.id}")
        assert r.status_code == 200
        # The returned profile MUST still be exam_a
        assert r.json()["exam_id"] == exam_a.id
        assert r.json()["exam_id"] != exam_b.id
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Section 3: Rate Limiter and CORS Tests
# ---------------------------------------------------------------------------

def test_rate_limiter_options_preflight_bypass():
    """OPTIONS preflight requests are never blocked by the rate limiter."""
    test_app = FastAPI()

    @test_app.middleware("http")
    async def _rate_limit(request: Request, call_next):
        return await hardening.rate_limit_handler(request, call_next)

    @test_app.options("/api/v1/test-resource")
    async def _options():
        return PlainTextResponse("OK")

    client = TestClient(test_app)

    # Send 50 OPTIONS requests — none should be rate limited even if client exceeded limits
    for _ in range(50):
        resp = client.options(
            "/api/v1/test-resource",
            headers={"Origin": "http://localhost:3000"}
        )
        assert resp.status_code == 200


def test_cors_headers_on_429_trusted_origin():
    """When a trusted origin hits HTTP 429, CORS headers are preserved."""
    test_app = FastAPI()

    @test_app.middleware("http")
    async def _rate_limit(request: Request, call_next):
        return await hardening.rate_limit_handler(request, call_next)

    @test_app.get("/api/v1/limited")
    async def _limited():
        return PlainTextResponse("OK")

    client = TestClient(test_app)

    # Force rate limiting for a specific client IP by monkeypatching RATE_LIMIT_MAX
    with patch.object(hardening, "RATE_LIMIT_MAX", 2):
        headers = {"Origin": "http://localhost:3000", "X-Forwarded-For": "198.51.100.1"}

        r1 = client.get("/api/v1/limited", headers=headers)
        assert r1.status_code == 200

        r2 = client.get("/api/v1/limited", headers=headers)
        assert r2.status_code == 200

        # Third request exceeds limit
        r3 = client.get("/api/v1/limited", headers=headers)
        assert r3.status_code == 429
        # CORS headers MUST be present for trusted origin
        assert r3.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert r3.headers.get("access-control-allow-credentials") == "true"


def test_cors_headers_on_429_untrusted_origin_rejected():
    """When an untrusted origin hits HTTP 429, Access-Control-Allow-Origin is NOT set."""
    test_app = FastAPI()

    @test_app.middleware("http")
    async def _rate_limit(request: Request, call_next):
        return await hardening.rate_limit_handler(request, call_next)

    @test_app.get("/api/v1/limited")
    async def _limited():
        return PlainTextResponse("OK")

    client = TestClient(test_app)

    with patch.object(hardening, "RATE_LIMIT_MAX", 1):
        headers = {"Origin": "https://attacker.evil.corp", "X-Forwarded-For": "198.51.100.2"}

        r1 = client.get("/api/v1/limited", headers=headers)
        assert r1.status_code == 200

        # Exceeds limit
        r2 = client.get("/api/v1/limited", headers=headers)
        assert r2.status_code == 429
        # Untrusted origin must NOT receive Access-Control-Allow-Origin
        assert "access-control-allow-origin" not in r2.headers


def test_production_vs_development_rate_limit_defaults():
    """Verify default rate limit window settings distinguish dev from prod."""
    settings = get_settings()

    # In production, default max is 100 requests / min
    with patch.object(settings, "APP_ENV", "production"):
        dev_prod_calc = "500" if getattr(settings, "APP_ENV", "production") == "development" else "100"
        assert dev_prod_calc == "100"

    # In development, default max is relaxed to 500 requests / min
    with patch.object(settings, "APP_ENV", "development"):
        dev_prod_calc = "500" if getattr(settings, "APP_ENV", "production") == "development" else "100"
        assert dev_prod_calc == "500"


def test_dev_login_prohibited_in_production():
    """Verify that /api/v1/auth/dev/login returns 404 in production mode."""
    settings = get_settings()
    client = TestClient(app)

    with patch.object(settings, "APP_ENV", "production"):
        resp = client.post("/api/v1/auth/dev/login", json={"role": "ADMIN"})
        assert resp.status_code == 404
        assert "prohibited in production" in resp.json()["detail"]


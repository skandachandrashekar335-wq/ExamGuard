"""Phase 15 — Examination Session Management Tests.

Tests for examination session models, services, and API endpoints.
"""

import pytest
from datetime import date, time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.examination_session import (
    ExaminationSession,
    GateEvent,
    GateStatus,
    SessionStatus,
)
from app.models.student import Student
from app.models.subject import Subject
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.entry_point import EntryPoint
from app.core.database import get_db
from app.main import app
from app.services import examination_session as svc


@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(db_engine):
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def client(db_engine):
    SessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clean_tables(db_engine):
    """Clean examination session tables before each test."""
    with db_engine.connect() as conn:
        conn.execute(text("DELETE FROM gate_events"))
        conn.execute(text("DELETE FROM examination_sessions"))
        conn.execute(text("DELETE FROM entry_points"))
        conn.execute(text("DELETE FROM exam_halls"))
        conn.execute(text("DELETE FROM exams"))
        conn.execute(text("DELETE FROM subjects"))
        conn.execute(text("DELETE FROM students"))
        conn.commit()
    yield
    with db_engine.connect() as conn:
        conn.execute(text("DELETE FROM gate_events"))
        conn.execute(text("DELETE FROM examination_sessions"))
        conn.execute(text("DELETE FROM entry_points"))
        conn.execute(text("DELETE FROM exam_halls"))
        conn.execute(text("DELETE FROM exams"))
        conn.execute(text("DELETE FROM subjects"))
        conn.execute(text("DELETE FROM students"))
        conn.commit()


@pytest.fixture()
def seed_data(db_session):
    """Create prerequisite data for tests."""
    student = Student(usn="TEST_USN_15", name="Test Student 15")
    db_session.add(student)
    db_session.flush()

    subject = Subject(code="CS15", name="Test Subject 15", department="CS", semester=5, credits=4)
    db_session.add(subject)
    db_session.flush()

    exam = Exam(
        subject_id=subject.id,
        exam_name="Test Exam 15",
        exam_date=date(2026, 9, 15),
        start_time=time(10, 0),
        end_time=time(13, 0),
        semester=5,
        department="CS",
    )
    db_session.add(exam)
    db_session.flush()

    hall = ExamHall(building="Block A", room_number="101", capacity=60)
    db_session.add(hall)
    db_session.flush()

    entry_point = EntryPoint(name="Main Gate", code="MG_15", exam_hall_id=hall.id)
    db_session.add(entry_point)
    db_session.flush()

    db_session.commit()

    return {
        "student": student,
        "subject": subject,
        "exam": exam,
        "hall": hall,
        "entry_point": entry_point,
    }


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------


class TestExaminationSessionModel:
    """ExaminationSession model behavior."""

    def test_create_session(self, db_session, seed_data):
        session = ExaminationSession(
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        db_session.add(session)
        db_session.commit()
        assert session.id is not None
        assert session.status == SessionStatus.NOT_STARTED.value
        assert session.gate_status == GateStatus.GATES_CLOSED.value

    def test_unique_exam_hall_constraint(self, db_session, seed_data):
        s1 = ExaminationSession(exam_id=seed_data["exam"].id, exam_hall_id=seed_data["hall"].id)
        s2 = ExaminationSession(exam_id=seed_data["exam"].id, exam_hall_id=seed_data["hall"].id)
        db_session.add(s1)
        db_session.commit()
        db_session.add(s2)
        with pytest.raises(Exception):
            db_session.commit()

    def test_different_halls_allowed(self, db_session, seed_data):
        hall2 = ExamHall(building="Block B", room_number="201", capacity=40)
        db_session.add(hall2)
        db_session.flush()
        s1 = ExaminationSession(exam_id=seed_data["exam"].id, exam_hall_id=seed_data["hall"].id)
        s2 = ExaminationSession(exam_id=seed_data["exam"].id, exam_hall_id=hall2.id)
        db_session.add(s1)
        db_session.add(s2)
        db_session.commit()
        assert s1.id != s2.id

    def test_repr(self, db_session, seed_data):
        session = ExaminationSession(
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        db_session.add(session)
        db_session.commit()
        r = repr(session)
        assert "ExaminationSession" in r
        assert str(session.id) in r


class TestGateEventModel:
    """GateEvent model behavior."""

    def test_create_gate_event(self, db_session, seed_data):
        session = ExaminationSession(
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        db_session.add(session)
        db_session.flush()

        event = GateEvent(
            session_id=session.id,
            previous_status=GateStatus.GATES_CLOSED.value,
            new_status=GateStatus.GATES_OPEN.value,
            reason="Test",
        )
        db_session.add(event)
        db_session.commit()
        assert event.id is not None

    def test_repr(self, db_session, seed_data):
        session = ExaminationSession(
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        db_session.add(session)
        db_session.flush()
        event = GateEvent(
            session_id=session.id,
            previous_status=GateStatus.GATES_CLOSED.value,
            new_status=GateStatus.GATES_OPEN.value,
        )
        db_session.add(event)
        db_session.commit()
        r = repr(event)
        assert "GateEvent" in r


# ---------------------------------------------------------------------------
# Service Tests
# ---------------------------------------------------------------------------


class TestCreateSession:
    """create_examination_session service."""

    def test_creates_session(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        assert session.id is not None
        assert session.status == SessionStatus.NOT_STARTED.value

    def test_with_optional_fields(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
            expected_capacity=60,
            notes="Test session",
            created_by="admin",
        )
        assert session.expected_capacity == 60
        assert session.notes == "Test session"
        assert session.created_by == "admin"


class TestGetSession:
    """get_examination_session service."""

    def test_get_existing(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        result = svc.get_examination_session(db_session, session.id)
        assert result.id == session.id

    def test_get_nonexistent_raises(self, db_session):
        with pytest.raises(LookupError):
            svc.get_examination_session(db_session, 99999)


class TestListSessions:
    """list_examination_sessions service."""

    def test_empty_list(self, db_session):
        result = svc.list_examination_sessions(db_session)
        assert result["items"] == []
        assert result["total"] == 0

    def test_filter_by_status(self, db_session, seed_data):
        svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        result = svc.list_examination_sessions(
            db_session, status=SessionStatus.NOT_STARTED.value
        )
        assert result["total"] == 1

    def test_filter_by_exam(self, db_session, seed_data):
        svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        result = svc.list_examination_sessions(
            db_session, exam_id=seed_data["exam"].id
        )
        assert result["total"] == 1


class TestStartSession:
    """start_session service — lifecycle transitions."""

    def test_start_not_started(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        result = svc.start_session(db_session, session.id, performed_by="admin")
        assert result.status == SessionStatus.IN_PROGRESS.value
        assert result.gate_status == GateStatus.GATES_OPEN.value
        assert result.started_at is not None
        assert result.gate_open_at is not None

    def test_start_creates_gate_event(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id)
        events = db_session.query(GateEvent).filter(GateEvent.session_id == session.id).all()
        assert len(events) == 1
        assert events[0].previous_status == GateStatus.GATES_CLOSED.value
        assert events[0].new_status == GateStatus.GATES_OPEN.value

    def test_cannot_start_already_started(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id)
        with pytest.raises(ValueError, match="Cannot transition"):
            svc.start_session(db_session, session.id)

    def test_cannot_start_completed(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id)
        svc.end_session(db_session, session.id)
        with pytest.raises(ValueError, match="Cannot transition"):
            svc.start_session(db_session, session.id)


class TestEndSession:
    """end_session service — lifecycle transitions."""

    def test_end_in_progress(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id)
        result = svc.end_session(db_session, session.id)
        assert result.status == SessionStatus.COMPLETED.value
        assert result.gate_status == GateStatus.GATES_CLOSED.value
        assert result.ended_at is not None

    def test_end_creates_gate_event(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id)
        svc.end_session(db_session, session.id)
        events = db_session.query(GateEvent).filter(GateEvent.session_id == session.id).all()
        assert len(events) == 2  # start + end

    def test_cannot_end_not_started(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        with pytest.raises(ValueError, match="Cannot transition"):
            svc.end_session(db_session, session.id)

    def test_cannot_end_twice(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id)
        svc.end_session(db_session, session.id)
        with pytest.raises(ValueError, match="Cannot transition"):
            svc.end_session(db_session, session.id)


class TestCancelSession:
    """cancel_session service."""

    def test_cancel_not_started(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        result = svc.cancel_session(db_session, session.id, reason="Weather")
        assert result.status == SessionStatus.CANCELLED.value

    def test_cancel_in_progress(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id)
        result = svc.cancel_session(db_session, session.id, reason="Emergency")
        assert result.status == SessionStatus.CANCELLED.value
        assert result.ended_at is not None

    def test_cannot_cancel_completed(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id)
        svc.end_session(db_session, session.id)
        with pytest.raises(ValueError, match="Cannot transition"):
            svc.cancel_session(db_session, session.id)

    def test_cannot_cancel_already_cancelled(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.cancel_session(db_session, session.id)
        with pytest.raises(ValueError, match="Cannot transition"):
            svc.cancel_session(db_session, session.id)


class TestGateOperations:
    """Gate open/close operations."""

    def test_close_gates(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id)
        result = svc.close_gates(db_session, session.id, reason="Break")
        assert result.gate_status == GateStatus.GATES_CLOSED.value

    def test_open_gates_after_close(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id)
        svc.close_gates(db_session, session.id)
        result = svc.open_gates(db_session, session.id, reason="Break over")
        assert result.gate_status == GateStatus.GATES_OPEN.value

    def test_cannot_close_already_closed(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id)
        svc.close_gates(db_session, session.id)
        with pytest.raises(ValueError, match="already closed"):
            svc.close_gates(db_session, session.id)

    def test_cannot_open_already_open(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id)
        with pytest.raises(ValueError, match="already open"):
            svc.open_gates(db_session, session.id)

    def test_cannot_close_not_started_without_gates_open(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        with pytest.raises(ValueError, match="only close gates for an in-progress"):
            svc.close_gates(db_session, session.id)

    def test_cannot_open_gates_for_completed(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id)
        svc.end_session(db_session, session.id)
        with pytest.raises(ValueError, match="completed or cancelled"):
            svc.open_gates(db_session, session.id)

    def test_gate_events_recorded(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id, performed_by="admin")
        svc.close_gates(db_session, session.id, reason="Break", performed_by="guard")
        svc.open_gates(db_session, session.id, reason="Back", performed_by="guard")
        events = db_session.query(GateEvent).filter(GateEvent.session_id == session.id).all()
        assert len(events) == 3
        assert events[0].performed_by == "admin"
        assert events[1].performed_by == "guard"
        assert events[2].performed_by == "guard"


class TestListGateEvents:
    """list_gate_events service."""

    def test_list_events(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        svc.start_session(db_session, session.id)
        result = svc.list_gate_events(db_session, session.id)
        assert result["total"] == 1

    def test_list_events_empty(self, db_session, seed_data):
        session = svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        result = svc.list_gate_events(db_session, session.id)
        assert result["total"] == 0

    def test_list_events_nonexistent_session(self, db_session):
        with pytest.raises(LookupError):
            svc.list_gate_events(db_session, 99999)


class TestSessionSummary:
    """get_session_summary service."""

    def test_summary_empty(self, db_session):
        result = svc.get_session_summary(db_session)
        assert result["total_sessions"] == 0

    def test_summary_with_sessions(self, db_session, seed_data):
        svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=seed_data["hall"].id,
        )
        hall2 = ExamHall(building="Block C", room_number="301", capacity=30)
        db_session.add(hall2)
        db_session.flush()
        svc.create_examination_session(
            db_session,
            exam_id=seed_data["exam"].id,
            exam_hall_id=hall2.id,
        )
        result = svc.get_session_summary(db_session)
        assert result["total_sessions"] == 2
        assert result["not_started"] == 2


# ---------------------------------------------------------------------------
# API Tests
# ---------------------------------------------------------------------------


class TestCreateSessionAPI:
    """POST /api/v1/examination-sessions."""

    def test_create_session(self, client, seed_data):
        resp = client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "NOT_STARTED"
        assert data["gate_status"] == "GATES_CLOSED"

    def test_create_with_optional_fields(self, client, seed_data):
        resp = client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
                "expected_capacity": 60,
                "notes": "Test",
                "created_by": "admin",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["expected_capacity"] == 60

    def test_create_missing_exam_id(self, client, seed_data):
        resp = client.post(
            "/api/v1/examination-sessions",
            json={"exam_hall_id": seed_data["hall"].id},
        )
        assert resp.status_code == 422


class TestListSessionsAPI:
    """GET /api/v1/examination-sessions."""

    def test_list_empty(self, client):
        resp = client.get("/api/v1/examination-sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_with_data(self, client, seed_data):
        client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
            },
        )
        resp = client.get("/api/v1/examination-sessions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_filter_by_status(self, client, seed_data):
        client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
            },
        )
        resp = client.get(
            "/api/v1/examination-sessions",
            params={"status": "NOT_STARTED"},
        )
        assert resp.json()["total"] == 1

        resp = client.get(
            "/api/v1/examination-sessions",
            params={"status": "IN_PROGRESS"},
        )
        assert resp.json()["total"] == 0


class TestGetSessionAPI:
    """GET /api/v1/examination-sessions/{id}."""

    def test_get_existing(self, client, seed_data):
        create_resp = client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
            },
        )
        session_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/examination-sessions/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == session_id

    def test_get_nonexistent(self, client):
        resp = client.get("/api/v1/examination-sessions/99999")
        assert resp.status_code == 404


class TestStartSessionAPI:
    """POST /api/v1/examination-sessions/{id}/start."""

    def test_start(self, client, seed_data):
        create_resp = client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
            },
        )
        session_id = create_resp.json()["id"]
        resp = client.post(
            f"/api/v1/examination-sessions/{session_id}/start",
            json={"performed_by": "admin"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "IN_PROGRESS"
        assert resp.json()["gate_status"] == "GATES_OPEN"

    def test_start_nonexistent(self, client):
        resp = client.post(
            "/api/v1/examination-sessions/99999/start",
            json={},
        )
        assert resp.status_code == 404

    def test_start_already_started(self, client, seed_data):
        create_resp = client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
            },
        )
        session_id = create_resp.json()["id"]
        client.post(f"/api/v1/examination-sessions/{session_id}/start", json={})
        resp = client.post(f"/api/v1/examination-sessions/{session_id}/start", json={})
        assert resp.status_code == 422


class TestEndSessionAPI:
    """POST /api/v1/examination-sessions/{id}/end."""

    def test_end(self, client, seed_data):
        create_resp = client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
            },
        )
        session_id = create_resp.json()["id"]
        client.post(f"/api/v1/examination-sessions/{session_id}/start", json={})
        resp = client.post(f"/api/v1/examination-sessions/{session_id}/end", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "COMPLETED"
        assert resp.json()["gate_status"] == "GATES_CLOSED"

    def test_end_not_started(self, client, seed_data):
        create_resp = client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
            },
        )
        session_id = create_resp.json()["id"]
        resp = client.post(f"/api/v1/examination-sessions/{session_id}/end", json={})
        assert resp.status_code == 422


class TestCancelSessionAPI:
    """POST /api/v1/examination-sessions/{id}/cancel."""

    def test_cancel(self, client, seed_data):
        create_resp = client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
            },
        )
        session_id = create_resp.json()["id"]
        resp = client.post(
            f"/api/v1/examination-sessions/{session_id}/cancel",
            json={"reason": "Weather"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "CANCELLED"


class TestGateOperationsAPI:
    """Gate open/close API endpoints."""

    def test_close_gates(self, client, seed_data):
        create_resp = client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
            },
        )
        session_id = create_resp.json()["id"]
        client.post(f"/api/v1/examination-sessions/{session_id}/start", json={})
        resp = client.post(
            f"/api/v1/examination-sessions/{session_id}/close-gates",
            json={"reason": "Break"},
        )
        assert resp.status_code == 200
        assert resp.json()["gate_status"] == "GATES_CLOSED"

    def test_open_gates(self, client, seed_data):
        create_resp = client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
            },
        )
        session_id = create_resp.json()["id"]
        client.post(f"/api/v1/examination-sessions/{session_id}/start", json={})
        client.post(
            f"/api/v1/examination-sessions/{session_id}/close-gates",
            json={},
        )
        resp = client.post(
            f"/api/v1/examination-sessions/{session_id}/open-gates",
            json={"reason": "Back"},
        )
        assert resp.status_code == 200
        assert resp.json()["gate_status"] == "GATES_OPEN"

    def test_list_gate_events(self, client, seed_data):
        create_resp = client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
            },
        )
        session_id = create_resp.json()["id"]
        client.post(f"/api/v1/examination-sessions/{session_id}/start", json={})
        resp = client.get(
            f"/api/v1/examination-sessions/{session_id}/gate-events"
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


class TestSessionSummaryAPI:
    """GET /api/v1/examination-sessions/summary."""

    def test_summary(self, client):
        resp = client.get("/api/v1/examination-sessions/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_sessions" in data
        assert "not_started" in data
        assert "in_progress" in data
        assert "completed" in data
        assert "cancelled" in data


class TestSecurityPrivacy:
    """Security and privacy checks."""

    def test_no_biometric_data_in_session(self, client, seed_data):
        create_resp = client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
            },
        )
        resp_json = create_resp.json()
        for key in resp_json:
            assert "face" not in key.lower()
            assert "biometric" not in key.lower()
            assert "image" not in key.lower()

    def test_no_credential_leakage(self, client, seed_data):
        create_resp = client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": seed_data["exam"].id,
                "exam_hall_id": seed_data["hall"].id,
            },
        )
        resp_text = create_resp.text
        assert "password" not in resp_text.lower()
        assert "secret" not in resp_text.lower()
        assert "api_key" not in resp_text.lower()

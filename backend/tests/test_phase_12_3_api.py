"""Phase 12.3 — Attendance REST API.

Tests for the attendance REST API layer.
Covers: record, list exam attendance, summary, registration attendance,
manual correction, student history, event history, error mapping,
schema validation, privacy, ownership/isolation.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.attendance import AttendanceEvent, AttendanceRecord
from app.models.entry_point import EntryPoint
from app.models.entry_verification import EntryVerification
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration
from app.models.seat_assignment import SeatAssignment
from app.models.security_event import SecurityAlert, SecurityEvent
from app.models.proxy_risk import ProxyRiskAssessment, SecuritySignal
from app.models.student import Student
from app.models.subject import Subject


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_test_data():
    """Remove test data before each test."""
    db = SessionLocal()
    try:
        ev_ids_sub = db.query(EntryVerification.id).filter(
            EntryVerification.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("ATTAPI%"))
            )
        ).subquery()
        db.execute(delete(SecurityAlert).where(
            SecurityAlert.security_event_id.in_(
                db.query(SecurityEvent.id).filter(
                    SecurityEvent.entry_verification_id.in_(db.query(ev_ids_sub))
                )
            )
        ))
        db.execute(delete(SecurityEvent).where(
            SecurityEvent.entry_verification_id.in_(db.query(ev_ids_sub))
        ))
        db.execute(delete(SecurityAlert).where(
            SecurityAlert.security_event_id.in_(
                db.query(SecurityEvent.id).filter(
                    SecurityEvent.student_id.in_(
                        db.query(Student.id).filter(Student.usn.ilike("ATTAPI%"))
                    )
                )
            )
        ))
        db.execute(delete(SecurityEvent).where(
            SecurityEvent.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("ATTAPI%"))
            )
        ))
        db.execute(delete(SecuritySignal).where(
            SecuritySignal.entry_verification_id.in_(db.query(ev_ids_sub))
        ))
        db.execute(delete(ProxyRiskAssessment).where(
            ProxyRiskAssessment.entry_verification_id.in_(db.query(ev_ids_sub))
        ))
        db.execute(delete(AttendanceEvent).where(
            AttendanceEvent.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("ATTAPI%"))
            )
        ))
        db.execute(delete(AttendanceRecord).where(
            AttendanceRecord.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("ATTAPI%"))
            )
        ))
        db.execute(delete(EntryVerification).where(
            EntryVerification.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("ATTAPI%"))
            )
        ))
        db.execute(delete(SeatAssignment).where(
            SeatAssignment.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("ATTAPI%"))
            )
        ))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("ATTAPI%"))
            )
        ))
        db.execute(delete(EntryPoint).where(EntryPoint.code.ilike("ATTAPIEP%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("ATTAPIEXAM%")))
        db.execute(delete(ExamHall).where(ExamHall.building.ilike("ATTAPIHALL%")))
        db.execute(delete(Subject).where(Subject.code.ilike("ATTAPISUB%")))
        db.execute(delete(Student).where(Student.usn.ilike("ATTAPI%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def test_student(client):
    response = client.post(
        "/api/v1/students",
        json={"usn": "ATTAPI001", "name": "Attendance API Student"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_student2(client):
    response = client.post(
        "/api/v1/students",
        json={"usn": "ATTAPI002", "name": "Attendance API Student 2"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_subject(client):
    response = client.post(
        "/api/v1/subjects",
        json={
            "code": "ATTAPISUB01",
            "name": "Attendance Test Subject",
            "department": "CS",
            "semester": 6,
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_exam(client, test_subject):
    response = client.post(
        "/api/v1/exams",
        json={
            "subject_id": test_subject["id"],
            "exam_name": "ATTAPIEXAM Midterm",
            "exam_date": "2026-09-15",
            "start_time": "09:00:00",
            "end_time": "12:00:00",
            "semester": 6,
            "department": "CS",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_exam_hall(client):
    response = client.post(
        "/api/v1/exam-halls",
        json={"building": "ATTAPIHALL A", "room_number": "101", "capacity": 50},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_exam_hall2(client):
    response = client.post(
        "/api/v1/exam-halls",
        json={"building": "ATTAPIHALL B", "room_number": "202", "capacity": 30},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_registration(client, test_student, test_exam):
    response = client.post(
        "/api/v1/exam-registrations",
        json={
            "student_id": test_student["id"],
            "exam_id": test_exam["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_registration2(client, test_student2, test_exam):
    response = client.post(
        "/api/v1/exam-registrations",
        json={
            "student_id": test_student2["id"],
            "exam_id": test_exam["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_entry_point(client, test_exam_hall):
    from app.models.entry_point import EntryPoint
    response = client.post(
        "/api/v1/entry-points",
        json={
            "name": "Main Gate",
            "code": "ATTAPIEP01",
            "exam_hall_id": test_exam_hall["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_ev_granted(client, test_student, test_registration, test_exam_hall, test_entry_point):
    """Create an EV and resolve it as GRANTED."""
    response = client.post(
        "/api/v1/entry-verifications",
        json={
            "student_id": test_student["id"],
            "exam_registration_id": test_registration["id"],
            "entry_point_id": test_entry_point["id"],
        },
    )
    assert response.status_code == 201
    ev = response.json()

    # Begin
    r = client.post(f"/api/v1/entry-verifications/{ev['id']}/begin")
    assert r.status_code == 200

    # Evaluate → GRANTED
    # We need to manually set status to GRANTED since evaluate requires checks
    from app.core.database import SessionLocal as SL
    from app.models.entry_verification import EntryVerificationStatus
    db = SL()
    try:
        db_ev = db.query(EntryVerification).filter(EntryVerification.id == ev["id"]).first()
        db_ev.status = EntryVerificationStatus.GRANTED.value
        db_ev.hall_ticket_check = "PASSED"
        db_ev.identity_check = "PASSED"
        db_ev.seat_check = "PASSED"
        db.commit()
    finally:
        db.close()

    # Refresh from API
    r = client.get(f"/api/v1/entry-verifications/{ev['id']}")
    assert r.status_code == 200
    return r.json()


@pytest.fixture()
def test_ev_denied(client, test_student, test_registration, test_exam_hall, test_entry_point):
    """Create an EV and resolve it as DENIED."""
    response = client.post(
        "/api/v1/entry-verifications",
        json={
            "student_id": test_student["id"],
            "exam_registration_id": test_registration["id"],
            "entry_point_id": test_entry_point["id"],
        },
    )
    assert response.status_code == 201
    ev = response.json()

    # Begin
    r = client.post(f"/api/v1/entry-verifications/{ev['id']}/begin")
    assert r.status_code == 200

    # Set to DENIED
    from app.core.database import SessionLocal as SL
    from app.models.entry_verification import EntryVerificationStatus
    db = SL()
    try:
        db_ev = db.query(EntryVerification).filter(EntryVerification.id == ev["id"]).first()
        db_ev.status = EntryVerificationStatus.DENIED.value
        db.commit()
    finally:
        db.close()

    r = client.get(f"/api/v1/entry-verifications/{ev['id']}")
    assert r.status_code == 200
    return r.json()


@pytest.fixture()
def test_ev_pending(client, test_student, test_registration, test_exam_hall, test_entry_point):
    """Create an EV in PENDING status."""
    response = client.post(
        "/api/v1/entry-verifications",
        json={
            "student_id": test_student["id"],
            "exam_registration_id": test_registration["id"],
            "entry_point_id": test_entry_point["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_seat_assignment(client, test_student, test_registration, test_exam_hall):
    """Create a seat assignment."""
    response = client.post(
        "/api/v1/seat-assignments",
        json={
            "student_id": test_student["id"],
            "exam_id": test_registration["exam_id"],
            "exam_hall_id": test_exam_hall["id"],
            "exam_registration_id": test_registration["id"],
            "seat_number": "A1",
        },
    )
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

class TestRouteRegistration:
    def test_record_route_exists(self, client):
        response = client.post("/api/v1/attendance/record/1")
        assert response.status_code in (200, 404, 422)

    def test_list_exam_attendance_route_exists(self, client):
        response = client.get("/api/v1/attendance/exams/1")
        assert response.status_code == 200

    def test_exam_summary_route_exists(self, client):
        response = client.get("/api/v1/attendance/exams/1/summary")
        assert response.status_code in (200, 404)

    def test_registration_attendance_route_exists(self, client):
        response = client.get("/api/v1/attendance/registrations/1")
        assert response.status_code in (200, 404)

    def test_correction_route_exists(self, client):
        response = client.post(
            "/api/v1/attendance/registrations/1/correct",
            json={"status": "PRESENT", "reason": "test", "recorded_by": "admin"},
        )
        assert response.status_code in (200, 404, 422)

    def test_student_history_route_exists(self, client):
        response = client.get("/api/v1/attendance/students/1")
        assert response.status_code in (200, 404)

    def test_events_route_exists(self, client):
        response = client.get("/api/v1/attendance/events/1")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /attendance/record/{entry_verification_id}
# ---------------------------------------------------------------------------

class TestRecordAttendance:
    def test_record_granted_creates_record(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        response = client.post(f"/api/v1/attendance/record/{ev_id}")
        assert response.status_code == 200
        data = response.json()
        assert data is not None
        assert data["status"] == "PRESENT"
        assert data["student_id"] == test_ev_granted["student_id"]
        assert data["exam_registration_id"] == test_ev_granted["exam_registration_id"]
        assert data["entry_verification_id"] == ev_id
        assert data["entry_method"] == "VERIFIED_ENTRY"
        assert "id" in data
        assert "recorded_at" in data

    def test_record_denied_returns_none(self, client, test_ev_denied):
        ev_id = test_ev_denied["id"]
        response = client.post(f"/api/v1/attendance/record/{ev_id}")
        assert response.status_code == 200
        data = response.json()
        # Service returns None for DENIED → API returns None/empty
        assert data is None

    def test_record_idempotent(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        r1 = client.post(f"/api/v1/attendance/record/{ev_id}")
        assert r1.status_code == 200
        data1 = r1.json()

        r2 = client.post(f"/api/v1/attendance/record/{ev_id}")
        assert r2.status_code == 200
        data2 = r2.json()

        # Same record returned, no duplicate
        assert data1["id"] == data2["id"]

    def test_record_denied_idempotent(self, client, test_ev_denied):
        ev_id = test_ev_denied["id"]
        r1 = client.post(f"/api/v1/attendance/record/{ev_id}")
        assert r1.status_code == 200
        assert r1.json() is None

        r2 = client.post(f"/api/v1/attendance/record/{ev_id}")
        assert r2.status_code == 200
        assert r2.json() is None

    def test_record_nonexistent_ev_returns_404(self, client):
        response = client.post("/api/v1/attendance/record/99999")
        assert response.status_code == 404

    def test_record_pending_ev_returns_422(self, client, test_ev_pending):
        ev_id = test_ev_pending["id"]
        response = client.post(f"/api/v1/attendance/record/{ev_id}")
        assert response.status_code == 422

    def test_record_creates_event(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        # Verify event was created
        from app.core.database import SessionLocal as SL
        db = SL()
        try:
            events = db.query(AttendanceEvent).filter(
                AttendanceEvent.entry_verification_id == ev_id
            ).all()
            assert len(events) == 1
            assert events[0].event_type == "ENTRY_GRANTED"
            assert events[0].recorded_by == "system"
        finally:
            db.close()

    def test_record_denied_creates_event(self, client, test_ev_denied):
        ev_id = test_ev_denied["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        from app.core.database import SessionLocal as SL
        db = SL()
        try:
            events = db.query(AttendanceEvent).filter(
                AttendanceEvent.entry_verification_id == ev_id
            ).all()
            assert len(events) == 1
            assert events[0].event_type == "ENTRY_DENIED"
            assert events[0].status_snapshot == "N/A"
        finally:
            db.close()

    def test_record_granted_sets_hall(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        response = client.post(f"/api/v1/attendance/record/{ev_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["hall_id"] == test_ev_granted["exam_hall_id"]


# ---------------------------------------------------------------------------
# GET /attendance/exams/{exam_id}
# ---------------------------------------------------------------------------

class TestListExamAttendance:
    def test_list_empty_exam(self, client, test_exam):
        response = client.get(f"/api/v1/attendance/exams/{test_exam['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_list_with_records(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        exam_id = test_ev_granted["exam_registration_id"]
        # Get exam_id from registration
        from app.core.database import SessionLocal as SL
        from app.models.exam_registration import ExamRegistration
        db = SL()
        try:
            reg = db.query(ExamRegistration).filter(
                ExamRegistration.id == test_ev_granted["exam_registration_id"]
            ).first()
            exam_id = reg.exam_id
        finally:
            db.close()

        response = client.get(f"/api/v1/attendance/exams/{exam_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_list_hall_filter(self, client, test_ev_granted, test_seat_assignment, test_exam_hall):
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        from app.core.database import SessionLocal as SL
        from app.models.exam_registration import ExamRegistration
        db = SL()
        try:
            reg = db.query(ExamRegistration).filter(
                ExamRegistration.id == test_ev_granted["exam_registration_id"]
            ).first()
            exam_id = reg.exam_id
        finally:
            db.close()

        # Filter by correct hall
        response = client.get(
            f"/api/v1/attendance/exams/{exam_id}",
            params={"hall_id": test_exam_hall["id"]},
        )
        assert response.status_code == 200
        assert response.json()["total"] >= 1

        # Filter by wrong hall
        response = client.get(
            f"/api/v1/attendance/exams/{exam_id}",
            params={"hall_id": 99999},
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_list_status_filter(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        from app.core.database import SessionLocal as SL
        from app.models.exam_registration import ExamRegistration
        db = SL()
        try:
            reg = db.query(ExamRegistration).filter(
                ExamRegistration.id == test_ev_granted["exam_registration_id"]
            ).first()
            exam_id = reg.exam_id
        finally:
            db.close()

        response = client.get(
            f"/api/v1/attendance/exams/{exam_id}",
            params={"status": "PRESENT"},
        )
        assert response.status_code == 200
        assert response.json()["total"] >= 1

        response = client.get(
            f"/api/v1/attendance/exams/{exam_id}",
            params={"status": "EXCUSED"},
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_list_pagination(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        from app.core.database import SessionLocal as SL
        from app.models.exam_registration import ExamRegistration
        db = SL()
        try:
            reg = db.query(ExamRegistration).filter(
                ExamRegistration.id == test_ev_granted["exam_registration_id"]
            ).first()
            exam_id = reg.exam_id
        finally:
            db.close()

        response = client.get(
            f"/api/v1/attendance/exams/{exam_id}",
            params={"page": 1, "page_size": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 1
        assert len(data["items"]) <= 1


# ---------------------------------------------------------------------------
# GET /attendance/exams/{exam_id}/summary
# ---------------------------------------------------------------------------

class TestExamSummary:
    def test_summary_empty_exam(self, client, test_exam):
        response = client.get(f"/api/v1/attendance/exams/{test_exam['id']}/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["exam_id"] == test_exam["id"]
        assert data["total_registered"] >= 0
        assert data["total_present"] == 0
        assert data["total_absent"] == 0
        assert data["total_excused"] == 0
        assert data["attendance_rate"] == 0.0
        assert data["by_hall"] == []

    def test_summary_with_records(self, client, test_ev_granted, test_seat_assignment, test_exam_hall):
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        from app.core.database import SessionLocal as SL
        from app.models.exam_registration import ExamRegistration
        db = SL()
        try:
            reg = db.query(ExamRegistration).filter(
                ExamRegistration.id == test_ev_granted["exam_registration_id"]
            ).first()
            exam_id = reg.exam_id
        finally:
            db.close()

        response = client.get(f"/api/v1/attendance/exams/{exam_id}/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_present"] >= 1
        assert data["total_registered"] >= 1
        assert data["attendance_rate"] > 0
        assert len(data["by_hall"]) >= 1

        hall_summary = data["by_hall"][0]
        assert "hall_id" in hall_summary
        assert "hall_name" in hall_summary
        assert "total" in hall_summary
        assert "present" in hall_summary

    def test_summary_nonexistent_exam(self, client):
        response = client.get("/api/v1/attendance/exams/99999/summary")
        assert response.status_code == 404

    def test_summary_multiple_halls(self, client, test_ev_granted, test_seat_assignment, test_exam_hall, test_exam_hall2, test_student2, test_registration2):
        # Record for first student
        client.post(f"/api/v1/attendance/record/{test_ev_granted['id']}")

        from app.core.database import SessionLocal as SL
        from app.models.exam_registration import ExamRegistration
        db = SL()
        try:
            reg = db.query(ExamRegistration).filter(
                ExamRegistration.id == test_ev_granted["exam_registration_id"]
            ).first()
            exam_id = reg.exam_id
        finally:
            db.close()

        response = client.get(f"/api/v1/attendance/exams/{exam_id}/summary")
        assert response.status_code == 200
        data = response.json()
        # At least one hall in breakdown
        assert len(data["by_hall"]) >= 1

    def test_summary_rate_calculation(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        from app.core.database import SessionLocal as SL
        from app.models.exam_registration import ExamRegistration
        db = SL()
        try:
            reg = db.query(ExamRegistration).filter(
                ExamRegistration.id == test_ev_granted["exam_registration_id"]
            ).first()
            exam_id = reg.exam_id
            total_registered = db.query(ExamRegistration).filter(
                ExamRegistration.exam_id == exam_id,
                ExamRegistration.status == "REGISTERED",
            ).count()
        finally:
            db.close()

        response = client.get(f"/api/v1/attendance/exams/{exam_id}/summary")
        assert response.status_code == 200
        data = response.json()
        expected_rate = round(1 / total_registered * 100, 1) if total_registered > 0 else 0.0
        assert data["attendance_rate"] == expected_rate


# ---------------------------------------------------------------------------
# GET /attendance/registrations/{exam_registration_id}
# ---------------------------------------------------------------------------

class TestRegistrationAttendance:
    def test_get_existing_record(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        reg_id = test_ev_granted["exam_registration_id"]
        response = client.get(f"/api/v1/attendance/registrations/{reg_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["exam_registration_id"] == reg_id
        assert data["status"] == "PRESENT"

    def test_get_missing_record(self, client, test_registration):
        reg_id = test_registration["id"]
        response = client.get(f"/api/v1/attendance/registrations/{reg_id}")
        assert response.status_code == 404

    def test_get_nonexistent_registration(self, client):
        response = client.get("/api/v1/attendance/registrations/99999")
        assert response.status_code == 404

    def test_record_then_get(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        reg_id = test_ev_granted["exam_registration_id"]

        r1 = client.post(f"/api/v1/attendance/record/{ev_id}")
        assert r1.status_code == 200

        r2 = client.get(f"/api/v1/attendance/registrations/{reg_id}")
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]


# ---------------------------------------------------------------------------
# POST /attendance/registrations/{exam_registration_id}/correct
# ---------------------------------------------------------------------------

class TestManualCorrection:
    def test_correct_to_present(self, client, test_ev_granted, test_registration):
        reg_id = test_registration["id"]
        response = client.post(
            f"/api/v1/attendance/registrations/{reg_id}/correct",
            json={
                "status": "PRESENT",
                "reason": "Medical certificate provided",
                "recorded_by": "admin_john",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PRESENT"
        assert data["entry_method"] == "MANUAL_ENTRY"
        assert data["exam_registration_id"] == reg_id

    def test_correct_to_excused(self, client, test_ev_granted, test_registration):
        reg_id = test_registration["id"]
        response = client.post(
            f"/api/v1/attendance/registrations/{reg_id}/correct",
            json={
                "status": "EXCUSED",
                "reason": "Official duty",
                "recorded_by": "admin_jane",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "EXCUSED"
        assert data["entry_method"] == "MANUAL_ENTRY"

    def test_correct_invalid_status(self, client, test_ev_granted, test_registration):
        reg_id = test_registration["id"]
        response = client.post(
            f"/api/v1/attendance/registrations/{reg_id}/correct",
            json={
                "status": "ABSENT",
                "reason": "test",
                "recorded_by": "admin",
            },
        )
        assert response.status_code == 422

    def test_correct_missing_reason(self, client, test_ev_granted, test_registration):
        reg_id = test_registration["id"]
        response = client.post(
            f"/api/v1/attendance/registrations/{reg_id}/correct",
            json={
                "status": "PRESENT",
                "reason": "",
                "recorded_by": "admin",
            },
        )
        assert response.status_code == 422

    def test_correct_missing_recorded_by(self, client, test_ev_granted, test_registration):
        reg_id = test_registration["id"]
        response = client.post(
            f"/api/v1/attendance/registrations/{reg_id}/correct",
            json={
                "status": "PRESENT",
                "reason": "test",
                "recorded_by": "",
            },
        )
        assert response.status_code == 422

    def test_correct_nonexistent_registration(self, client):
        response = client.post(
            "/api/v1/attendance/registrations/99999/correct",
            json={
                "status": "PRESENT",
                "reason": "test",
                "recorded_by": "admin",
            },
        )
        assert response.status_code == 404

    def test_correct_creates_event(self, client, test_ev_granted, test_registration):
        reg_id = test_registration["id"]
        client.post(
            f"/api/v1/attendance/registrations/{reg_id}/correct",
            json={
                "status": "EXCUSED",
                "reason": "Medical leave",
                "recorded_by": "admin_dr",
            },
        )

        from app.core.database import SessionLocal as SL
        db = SL()
        try:
            events = db.query(AttendanceEvent).filter(
                AttendanceEvent.exam_registration_id == reg_id
            ).all()
            corrected_events = [e for e in events if e.event_type == "ATTENDANCE_CORRECTED"]
            assert len(corrected_events) >= 1
            assert corrected_events[0].recorded_by == "admin_dr"
            assert corrected_events[0].reason == "Medical leave"
        finally:
            db.close()

    def test_correct_updates_existing_record(self, client, test_ev_granted, test_seat_assignment, test_registration):
        ev_id = test_ev_granted["id"]
        reg_id = test_registration["id"]

        # First: automated record
        r1 = client.post(f"/api/v1/attendance/record/{ev_id}")
        assert r1.status_code == 200
        original_id = r1.json()["id"]

        # Then: manual correction
        r2 = client.post(
            f"/api/v1/attendance/registrations/{reg_id}/correct",
            json={
                "status": "EXCUSED",
                "reason": "Updated after review",
                "recorded_by": "admin_chief",
            },
        )
        assert r2.status_code == 200
        # Same record ID, status changed
        assert r2.json()["id"] == original_id
        assert r2.json()["status"] == "EXCUSED"

    def test_correct_empty_body(self, client, test_registration):
        reg_id = test_registration["id"]
        response = client.post(
            f"/api/v1/attendance/registrations/{reg_id}/correct",
            json={},
        )
        assert response.status_code == 422

    def test_correct_no_ev_for_registration(self, client, test_student, test_exam):
        """Correction without any EV should fail (service requires an EV)."""
        # Create registration directly via DB (no EV)
        from app.core.database import SessionLocal as SL
        from app.models.exam_registration import ExamRegistration, RegistrationStatus
        db = SL()
        try:
            reg = ExamRegistration(
                student_id=test_student["id"],
                exam_id=test_exam["id"],
                status=RegistrationStatus.REGISTERED.value,
            )
            db.add(reg)
            db.commit()
            db.refresh(reg)
            reg_id = reg.id
        finally:
            db.close()

        response = client.post(
            f"/api/v1/attendance/registrations/{reg_id}/correct",
            json={
                "status": "PRESENT",
                "reason": "No EV exists",
                "recorded_by": "admin",
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /attendance/students/{student_id}
# ---------------------------------------------------------------------------

class TestStudentHistory:
    def test_empty_history(self, client, test_student):
        student_id = test_student["id"]
        response = client.get(f"/api/v1/attendance/students/{student_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_history_with_records(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        student_id = test_ev_granted["student_id"]
        response = client.get(f"/api/v1/attendance/students/{student_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_history_nonexistent_student(self, client):
        response = client.get("/api/v1/attendance/students/99999")
        assert response.status_code == 404

    def test_history_pagination(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        student_id = test_ev_granted["student_id"]
        response = client.get(
            f"/api/v1/attendance/students/{student_id}",
            params={"page": 1, "page_size": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 1

    def test_history_isolation(self, client, test_ev_granted, test_seat_assignment, test_student2):
        """Student 1's history doesn't include student 2."""
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        student1_id = test_ev_granted["student_id"]
        student2_id = test_student2["id"]

        r1 = client.get(f"/api/v1/attendance/students/{student1_id}")
        r2 = client.get(f"/api/v1/attendance/students/{student2_id}")

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["total"] >= 1
        assert r2.json()["total"] == 0


# ---------------------------------------------------------------------------
# GET /attendance/events/{entry_verification_id}
# ---------------------------------------------------------------------------

class TestEventHistory:
    def test_events_after_record(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        response = client.get(f"/api/v1/attendance/events/{ev_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        event = data["items"][0]
        assert event["entry_verification_id"] == ev_id
        assert event["event_type"] == "ENTRY_GRANTED"
        assert event["recorded_by"] == "system"

    def test_events_after_denied(self, client, test_ev_denied):
        ev_id = test_ev_denied["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        response = client.get(f"/api/v1/attendance/events/{ev_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        event = data["items"][0]
        assert event["event_type"] == "ENTRY_DENIED"
        assert event["status_snapshot"] == "N/A"

    def test_events_empty(self, client, test_ev_pending):
        ev_id = test_ev_pending["id"]
        response = client.get(f"/api/v1/attendance/events/{ev_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_events_pagination(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        response = client.get(
            f"/api/v1/attendance/events/{ev_id}",
            params={"page": 1, "page_size": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 1

    def test_events_nonexistent_ev(self, client):
        response = client.get("/api/v1/attendance/events/99999")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0


# ---------------------------------------------------------------------------
# Response schema validation
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_record_response_fields(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        response = client.post(f"/api/v1/attendance/record/{ev_id}")
        assert response.status_code == 200
        data = response.json()
        expected_fields = {
            "id", "student_id", "exam_id", "exam_registration_id",
            "status", "entry_verification_id", "entry_method", "entry_time",
            "hall_id", "seat_number", "recorded_at", "updated_at",
        }
        assert expected_fields == set(data.keys())

    def test_event_response_fields(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")

        response = client.get(f"/api/v1/attendance/events/{ev_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1
        event = data["items"][0]
        expected_fields = {
            "id", "student_id", "exam_id", "exam_registration_id",
            "entry_verification_id", "event_type", "status_snapshot",
            "recorded_by", "reason", "created_at",
        }
        assert expected_fields == set(event.keys())

    def test_list_response_fields(self, client, test_exam):
        response = client.get(f"/api/v1/attendance/exams/{test_exam['id']}")
        assert response.status_code == 200
        data = response.json()
        expected_fields = {"items", "total", "page", "page_size"}
        assert expected_fields == set(data.keys())

    def test_summary_response_fields(self, client, test_exam):
        response = client.get(f"/api/v1/attendance/exams/{test_exam['id']}/summary")
        assert response.status_code == 200
        data = response.json()
        expected_fields = {
            "exam_id", "total_registered", "total_present",
            "total_absent", "total_excused", "attendance_rate", "by_hall",
        }
        assert expected_fields == set(data.keys())


# ---------------------------------------------------------------------------
# Privacy / sensitive data exclusion
# ---------------------------------------------------------------------------

class TestPrivacy:
    def test_no_biometric_data_in_record(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        response = client.post(f"/api/v1/attendance/record/{ev_id}")
        assert response.status_code == 200
        data = response.json()
        # Should not contain any biometric/face/image fields
        forbidden = {"face_image", "embedding", "biometric_data", "face_embedding",
                      "reference_image", "probe_image", "raw_image", "image_data"}
        assert forbidden.isdisjoint(set(data.keys()))

    def test_no_biometric_data_in_event(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        client.post(f"/api/v1/attendance/record/{ev_id}")
        response = client.get(f"/api/v1/attendance/events/{ev_id}")
        assert response.status_code == 200
        for event in response.json()["items"]:
            forbidden = {"face_image", "embedding", "biometric_data", "face_embedding",
                          "reference_image", "probe_image", "raw_image", "image_data"}
            assert forbidden.isdisjoint(set(event.keys()))

    def test_no_provider_secrets(self, client, test_ev_granted, test_seat_assignment):
        ev_id = test_ev_granted["id"]
        response = client.post(f"/api/v1/attendance/record/{ev_id}")
        data = response.json()
        forbidden = {"api_key", "secret", "credential", "password", "token",
                      "provider_secret", "ocr_raw"}
        assert forbidden.isdisjoint(set(data.keys()))

    def test_no_internal_paths_in_error(self, client):
        response = client.post("/api/v1/attendance/record/99999")
        assert response.status_code == 404
        detail = response.json().get("detail", "")
        assert "D:\\" not in detail
        assert ".py" not in detail
        assert "traceback" not in detail.lower()


# ---------------------------------------------------------------------------
# Ownership / isolation
# ---------------------------------------------------------------------------

class TestOwnershipIsolation:
    def test_two_students_separate_records(self, client, test_ev_granted, test_seat_assignment,
                                            test_student2, test_registration2, test_exam_hall, test_entry_point):
        # Record for student 1
        client.post(f"/api/v1/attendance/record/{test_ev_granted['id']}")

        # Create EV for student 2 and resolve as GRANTED
        response = client.post(
            "/api/v1/entry-verifications",
            json={
                "student_id": test_student2["id"],
                "exam_registration_id": test_registration2["id"],
                "entry_point_id": test_entry_point["id"],
            },
        )
        assert response.status_code == 201
        ev2 = response.json()

        from app.core.database import SessionLocal as SL
        from app.models.entry_verification import EntryVerificationStatus
        db = SL()
        try:
            db_ev = db.query(EntryVerification).filter(EntryVerification.id == ev2["id"]).first()
            db_ev.status = EntryVerificationStatus.GRANTED.value
            db_ev.hall_ticket_check = "PASSED"
            db_ev.identity_check = "PASSED"
            db_ev.seat_check = "PASSED"
            db.commit()
        finally:
            db.close()

        client.post(f"/api/v1/attendance/record/{ev2['id']}")

        # Student 1 history
        r1 = client.get(f"/api/v1/attendance/students/{test_ev_granted['student_id']}")
        # Student 2 history
        r2 = client.get(f"/api/v1/attendance/students/{test_student2['id']}")

        assert r1.status_code == 200
        assert r2.status_code == 200
        # Both have records, but for different students
        for item in r1.json()["items"]:
            assert item["student_id"] == test_ev_granted["student_id"]
        for item in r2.json()["items"]:
            assert item["student_id"] == test_student2["id"]

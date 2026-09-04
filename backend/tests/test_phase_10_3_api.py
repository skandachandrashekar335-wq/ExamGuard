"""Phase 10.3 — Entry Verification API.

Tests for the entry verification REST API layer.
Covers: create, get, list, begin, hall-ticket-check, seat-check,
identity-check, evaluate, escalate, resolve, error mapping, security, privacy.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.camera import Camera
from app.models.camera_entry_point import CameraEntryPointMapping
from app.models.entry_point import EntryPoint
from app.models.entry_verification import EntryVerification
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration
from app.models.hall_ticket import HallTicket
from app.models.identity_verification import IdentityVerificationAttempt
from app.models.seat_assignment import SeatAssignment
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
        db.execute(delete(EntryVerification).where(
            EntryVerification.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("EVAPI%"))
            )
        ))
        db.execute(delete(IdentityVerificationAttempt).where(
            IdentityVerificationAttempt.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("EVAPI%"))
            )
        ))
        db.execute(delete(HallTicket).where(
            HallTicket.exam_registration_id.in_(
                db.query(ExamRegistration.id).filter(
                    ExamRegistration.student_id.in_(
                        db.query(Student.id).filter(Student.usn.ilike("EVAPI%"))
                    )
                )
            )
        ))
        db.execute(delete(SeatAssignment).where(
            SeatAssignment.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("EVAPI%"))
            )
        ))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("EVAPI%"))
            )
        ))
        db.execute(delete(CameraEntryPointMapping).where(
            CameraEntryPointMapping.camera_id.in_(
                db.query(Camera.id).filter(Camera.device_identifier.ilike("EVCAM%"))
            )
        ))
        db.execute(delete(Camera).where(Camera.device_identifier.ilike("EVCAM%")))
        db.execute(delete(EntryPoint).where(EntryPoint.code.ilike("EVEP%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("EVEXAM%")))
        db.execute(delete(ExamHall).where(ExamHall.building.ilike("EVHALL%")))
        db.execute(delete(Subject).where(Subject.code.ilike("EVSUB%")))
        db.execute(delete(Student).where(Student.usn.ilike("EVAPI%")))
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
        json={"usn": "EVAPI001", "name": "EV API Student"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_student2(client):
    response = client.post(
        "/api/v1/students",
        json={"usn": "EVAPI002", "name": "EV API Student 2"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_subject(client):
    response = client.post(
        "/api/v1/subjects",
        json={
            "code": "EVSUB01",
            "name": "EV Test Subject",
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
            "exam_name": "EVEXAM Midterm",
            "exam_date": "2026-09-20",
            "start_time": "09:00:00",
            "end_time": "12:00:00",
            "semester": 6,
            "department": "CS",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_hall(client):
    response = client.post(
        "/api/v1/exam-halls",
        json={
            "building": "EVHALL Main",
            "room_number": "201",
            "capacity": 100,
        },
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
def test_entry_point(client, test_hall):
    response = client.post(
        "/api/v1/entry-points",
        json={
            "name": "EV Main Gate",
            "code": "EVEP001",
            "exam_hall_id": test_hall["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_camera(client, test_hall):
    response = client.post(
        "/api/v1/cameras",
        json={
            "name": "EV Camera",
            "device_identifier": "EVCAM001",
            "exam_hall_id": test_hall["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_mapping(client, test_camera, test_entry_point):
    response = client.post(
        "/api/v1/camera-entry-points",
        json={
            "camera_id": test_camera["id"],
            "entry_point_id": test_entry_point["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_seat(client, test_registration, test_hall, test_exam, test_student):
    response = client.post(
        "/api/v1/seat-assignments",
        json={
            "exam_registration_id": test_registration["id"],
            "exam_hall_id": test_hall["id"],
            "exam_id": test_exam["id"],
            "student_id": test_student["id"],
            "seat_number": "A1",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_hall_ticket(client, test_registration):
    db = SessionLocal()
    try:
        ht = HallTicket(
            exam_registration_id=test_registration["id"],
            status="VERIFIED",
        )
        db.add(ht)
        db.commit()
        db.refresh(ht)
        ht_id = ht.id
        ht_status = ht.status
    finally:
        db.close()
    return {"id": ht_id, "status": ht_status}


@pytest.fixture()
def test_pending_hall_ticket(client, test_registration):
    db = SessionLocal()
    try:
        ht = HallTicket(
            exam_registration_id=test_registration["id"],
            status="CREATED",
        )
        db.add(ht)
        db.commit()
        db.refresh(ht)
        return {"id": ht.id, "status": ht.status}
    finally:
        db.close()


@pytest.fixture()
def test_identity_attempt(client, test_student, test_registration, test_hall_ticket):
    db = SessionLocal()
    try:
        att = IdentityVerificationAttempt(
            student_id=test_student["id"],
            exam_registration_id=test_registration["id"],
            hall_ticket_id=test_hall_ticket["id"],
            status="COMPLETED",
            verification_method="FACE",
            decision="MATCH",
        )
        db.add(att)
        db.commit()
        db.refresh(att)
        att_id = att.id
    finally:
        db.close()
    return {"id": att_id}


@pytest.fixture()
def test_pending_identity_attempt(client, test_student, test_registration, test_hall_ticket):
    db = SessionLocal()
    try:
        att = IdentityVerificationAttempt(
            student_id=test_student["id"],
            exam_registration_id=test_registration["id"],
            hall_ticket_id=test_hall_ticket["id"],
            status="PENDING",
            verification_method="FACE",
            decision="PENDING",
        )
        db.add(att)
        db.commit()
        db.refresh(att)
        return {"id": att.id}
    finally:
        db.close()


def _create_ev_via_api(
    client, test_student, test_registration, test_entry_point,
    camera_id=None, hall_ticket_id=None,
):
    payload = {
        "student_id": test_student["id"],
        "exam_registration_id": test_registration["id"],
        "entry_point_id": test_entry_point["id"],
    }
    if camera_id is not None:
        payload["camera_id"] = camera_id
    if hall_ticket_id is not None:
        payload["hall_ticket_id"] = hall_ticket_id
    response = client.post("/api/v1/entry-verifications", json=payload)
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

class TestCreateEntryVerification:
    def test_create_valid(self, client, test_student, test_registration,
                          test_entry_point):
        data = _create_ev_via_api(client, test_student, test_registration,
                                  test_entry_point)
        assert data["student_id"] == test_student["id"]
        assert data["exam_registration_id"] == test_registration["id"]
        assert data["entry_point_id"] == test_entry_point["id"]
        assert data["exam_hall_id"] is not None
        assert data["status"] == "PENDING"
        assert data["hall_ticket_check"] == "PENDING"
        assert data["identity_check"] == "PENDING"
        assert data["seat_check"] == "PENDING"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_with_camera(self, client, test_student, test_registration,
                                test_entry_point, test_camera, test_mapping):
        data = _create_ev_via_api(
            client, test_student, test_registration, test_entry_point,
            camera_id=test_camera["id"],
        )
        assert data["camera_id"] == test_camera["id"]

    def test_create_with_hall_ticket(self, client, test_student, test_registration,
                                     test_entry_point, test_hall_ticket):
        data = _create_ev_via_api(
            client, test_student, test_registration, test_entry_point,
            hall_ticket_id=test_hall_ticket["id"],
        )
        assert data["hall_ticket_id"] == test_hall_ticket["id"]

    def test_create_missing_student(self, client, test_registration,
                                    test_entry_point):
        response = client.post(
            "/api/v1/entry-verifications",
            json={
                "student_id": 999999,
                "exam_registration_id": test_registration["id"],
                "entry_point_id": test_entry_point["id"],
            },
        )
        assert response.status_code == 404

    def test_create_missing_registration(self, client, test_student,
                                         test_entry_point):
        response = client.post(
            "/api/v1/entry-verifications",
            json={
                "student_id": test_student["id"],
                "exam_registration_id": 999999,
                "entry_point_id": test_entry_point["id"],
            },
        )
        assert response.status_code == 404

    def test_create_registration_student_mismatch(self, client, test_student2,
                                                  test_registration,
                                                  test_entry_point):
        response = client.post(
            "/api/v1/entry-verifications",
            json={
                "student_id": test_student2["id"],
                "exam_registration_id": test_registration["id"],
                "entry_point_id": test_entry_point["id"],
            },
        )
        assert response.status_code == 422

    def test_create_missing_entry_point(self, client, test_student,
                                        test_registration):
        response = client.post(
            "/api/v1/entry-verifications",
            json={
                "student_id": test_student["id"],
                "exam_registration_id": test_registration["id"],
                "entry_point_id": 999999,
            },
        )
        assert response.status_code == 404

    def test_create_camera_not_mapped(self, client, test_student,
                                      test_registration, test_entry_point,
                                      test_camera):
        response = client.post(
            "/api/v1/entry-verifications",
            json={
                "student_id": test_student["id"],
                "exam_registration_id": test_registration["id"],
                "entry_point_id": test_entry_point["id"],
                "camera_id": test_camera["id"],
            },
        )
        assert response.status_code == 422

    def test_create_hall_ticket_wrong_registration(
        self, client, test_student, test_registration, test_entry_point,
        test_subject,
    ):
        other_exam_resp = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EVEXAM Other",
                "exam_date": "2026-09-21",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 6,
                "department": "CS",
            },
        )
        assert other_exam_resp.status_code == 201
        other_exam = other_exam_resp.json()
        other_reg_resp = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": other_exam["id"],
            },
        )
        assert other_reg_resp.status_code == 201
        other_reg = other_reg_resp.json()
        db = SessionLocal()
        try:
            other_ht = HallTicket(
                exam_registration_id=other_reg["id"],
                status="VERIFIED",
            )
            db.add(other_ht)
            db.commit()
            db.refresh(other_ht)
            other_ht_id = other_ht.id
        finally:
            db.close()
        response = client.post(
            "/api/v1/entry-verifications",
            json={
                "student_id": test_student["id"],
                "exam_registration_id": test_registration["id"],
                "entry_point_id": test_entry_point["id"],
                "hall_ticket_id": other_ht_id,
            },
        )
        assert response.status_code == 422

    def test_create_response_shape(self, client, test_student, test_registration,
                                   test_entry_point):
        data = _create_ev_via_api(client, test_student, test_registration,
                                  test_entry_point)
        expected_keys = {
            "id", "student_id", "exam_registration_id", "exam_hall_id",
            "entry_point_id", "camera_id", "hall_ticket_id",
            "identity_verification_attempt_id", "status",
            "hall_ticket_check", "identity_check", "seat_check",
            "escalation_reason", "resolved_at", "created_at", "updated_at",
        }
        assert expected_keys == set(data.keys())

    def test_create_no_status_override(self, client, test_student,
                                       test_registration, test_entry_point):
        response = client.post(
            "/api/v1/entry-verifications",
            json={
                "student_id": test_student["id"],
                "exam_registration_id": test_registration["id"],
                "entry_point_id": test_entry_point["id"],
                "status": "GRANTED",
            },
        )
        assert response.status_code == 201
        assert response.json()["status"] == "PENDING"


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------

class TestGetEntryVerification:
    def test_get_existing(self, client, test_student, test_registration,
                          test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        response = client.get(f"/api/v1/entry-verifications/{created['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created["id"]
        assert data["student_id"] == test_student["id"]

    def test_get_404(self, client):
        response = client.get("/api/v1/entry-verifications/999999")
        assert response.status_code == 404

    def test_get_safe_fields(self, client, test_student, test_registration,
                             test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        response = client.get(f"/api/v1/entry-verifications/{created['id']}")
        data = response.json()
        assert "id" in data
        assert "student_id" in data
        assert "status" in data
        assert "created_at" in data
        assert "updated_at" in data


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------

class TestListEntryVerifications:
    def test_list_empty(self, client):
        response = client.get("/api/v1/entry-verifications")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_list_with_items(self, client, test_student, test_registration,
                             test_entry_point):
        _create_ev_via_api(client, test_student, test_registration,
                           test_entry_point)
        response = client.get("/api/v1/entry-verifications")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_list_pagination(self, client, test_student, test_registration,
                             test_entry_point):
        _create_ev_via_api(client, test_student, test_registration,
                           test_entry_point)
        response = client.get("/api/v1/entry-verifications?page=1&page_size=1")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 1
        assert len(data["items"]) <= 1

    def test_list_filter_status(self, client, test_student, test_registration,
                                test_entry_point):
        _create_ev_via_api(client, test_student, test_registration,
                           test_entry_point)
        response = client.get("/api/v1/entry-verifications?status=PENDING")
        assert response.status_code == 200
        data = response.json()
        assert all(item["status"] == "PENDING" for item in data["items"])

    def test_list_filter_entry_point(self, client, test_student,
                                     test_registration, test_entry_point):
        _create_ev_via_api(client, test_student, test_registration,
                           test_entry_point)
        response = client.get(
            f"/api/v1/entry-verifications?entry_point_id={test_entry_point['id']}"
        )
        assert response.status_code == 200
        data = response.json()
        assert all(
            item["entry_point_id"] == test_entry_point["id"]
            for item in data["items"]
        )

    def test_list_filter_student(self, client, test_student, test_registration,
                                 test_entry_point):
        _create_ev_via_api(client, test_student, test_registration,
                           test_entry_point)
        response = client.get(
            f"/api/v1/entry-verifications?student_id={test_student['id']}"
        )
        assert response.status_code == 200
        data = response.json()
        assert all(
            item["student_id"] == test_student["id"]
            for item in data["items"]
        )


# ---------------------------------------------------------------------------
# BEGIN PROCESSING
# ---------------------------------------------------------------------------

class TestBeginProcessing:
    def test_valid_transition(self, client, test_student, test_registration,
                              test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/begin"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "IN_PROGRESS"

    def test_invalid_transition_from_in_progress(
        self, client, test_student, test_registration, test_entry_point,
    ):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        client.post(f"/api/v1/entry-verifications/{created['id']}/begin")
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/begin"
        )
        assert response.status_code == 422

    def test_terminal_record_cannot_restart(
        self, client, test_student, test_registration, test_entry_point,
    ):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        # Escalate to terminal-like state then resolve
        client.post(
            f"/api/v1/entry-verifications/{created['id']}/escalate",
            json={"reason": "test escalation"},
        )
        client.post(
            f"/api/v1/entry-verifications/{created['id']}/resolve",
            json={"granted": True},
        )
        # Try to begin on a granted record
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/begin"
        )
        assert response.status_code == 422

    def test_begin_404(self, client):
        response = client.post("/api/v1/entry-verifications/999999/begin")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# HALL TICKET CHECK
# ---------------------------------------------------------------------------

class TestHallTicketCheck:
    def test_successful_check(self, client, test_student, test_registration,
                              test_entry_point, test_hall_ticket):
        created = _create_ev_via_api(
            client, test_student, test_registration, test_entry_point,
        )
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/hall-ticket-check"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hall_ticket_check"] == "PASSED"
        assert data["hall_ticket_id"] == test_hall_ticket["id"]

    def test_failed_check_no_ticket(self, client, test_student,
                                    test_registration, test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/hall-ticket-check"
        )
        assert response.status_code == 200
        assert response.json()["hall_ticket_check"] == "FAILED"

    def test_failed_check_pending_ticket(
        self, client, test_student, test_registration, test_entry_point,
        test_pending_hall_ticket,
    ):
        created = _create_ev_via_api(
            client, test_student, test_registration, test_entry_point,
            hall_ticket_id=test_pending_hall_ticket["id"],
        )
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/hall-ticket-check"
        )
        assert response.status_code == 200
        assert response.json()["hall_ticket_check"] == "FAILED"

    def test_check_404(self, client):
        response = client.post(
            "/api/v1/entry-verifications/999999/hall-ticket-check"
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# SEAT CHECK
# ---------------------------------------------------------------------------

class TestSeatCheck:
    def test_successful_check(self, client, test_student, test_registration,
                              test_entry_point, test_seat):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/seat-check"
        )
        assert response.status_code == 200
        assert response.json()["seat_check"] == "PASSED"

    def test_failed_check_no_seat(self, client, test_student,
                                  test_registration, test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/seat-check"
        )
        assert response.status_code == 200
        assert response.json()["seat_check"] == "FAILED"

    def test_check_404(self, client):
        response = client.post(
            "/api/v1/entry-verifications/999999/seat-check"
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# IDENTITY CHECK
# ---------------------------------------------------------------------------

class TestIdentityCheck:
    def test_with_attempt_match(self, client, test_student, test_registration,
                                test_entry_point, test_identity_attempt):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/identity-check",
            json={"identity_attempt_id": test_identity_attempt["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["identity_check"] == "PASSED"
        assert data["identity_verification_attempt_id"] == test_identity_attempt["id"]

    def test_with_attempt_pending(self, client, test_student, test_registration,
                                  test_entry_point,
                                  test_pending_identity_attempt):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/identity-check",
            json={"identity_attempt_id": test_pending_identity_attempt["id"]},
        )
        assert response.status_code == 200
        assert response.json()["identity_check"] == "PENDING"

    def test_no_camera_skipped(self, client, test_student, test_registration,
                               test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/identity-check"
        )
        assert response.status_code == 200
        assert response.json()["identity_check"] == "SKIPPED"

    def test_with_camera_online_pending(self, client, test_student,
                                        test_registration, test_entry_point,
                                        test_camera, test_mapping):
        created = _create_ev_via_api(
            client, test_student, test_registration, test_entry_point,
            camera_id=test_camera["id"],
        )
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/identity-check"
        )
        assert response.status_code == 200
        assert response.json()["identity_check"] == "PENDING"

    def test_with_nonexistent_attempt(self, client, test_student,
                                      test_registration, test_entry_point,
                                      test_camera, test_mapping):
        created = _create_ev_via_api(
            client, test_student, test_registration, test_entry_point,
            camera_id=test_camera["id"],
        )
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/identity-check",
            json={"identity_attempt_id": 999999},
        )
        assert response.status_code == 404

    def test_check_404(self, client):
        response = client.post(
            "/api/v1/entry-verifications/999999/identity-check"
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# EVALUATE
# ---------------------------------------------------------------------------

class TestEvaluateEntry:
    def test_all_pass_granted(self, client, test_student, test_registration,
                              test_entry_point, test_hall_ticket, test_seat,
                              test_identity_attempt):
        created = _create_ev_via_api(
            client, test_student, test_registration, test_entry_point,
        )
        ev_id = created["id"]
        client.post(f"/api/v1/entry-verifications/{ev_id}/begin")
        client.post(f"/api/v1/entry-verifications/{ev_id}/hall-ticket-check")
        client.post(f"/api/v1/entry-verifications/{ev_id}/seat-check")
        client.post(
            f"/api/v1/entry-verifications/{ev_id}/identity-check",
            json={"identity_attempt_id": test_identity_attempt["id"]},
        )
        response = client.post(
            f"/api/v1/entry-verifications/{ev_id}/evaluate"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "GRANTED"

    def test_definitive_failure_denied(self, client, test_student,
                                       test_registration, test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        ev_id = created["id"]
        client.post(f"/api/v1/entry-verifications/{ev_id}/begin")
        client.post(f"/api/v1/entry-verifications/{ev_id}/hall-ticket-check")
        response = client.post(
            f"/api/v1/entry-verifications/{ev_id}/evaluate"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "DENIED"

    def test_inconclusive_escalated(self, client, test_student,
                                    test_registration, test_entry_point,
                                    test_hall_ticket, test_seat,
                                    test_camera, test_mapping):
        created = _create_ev_via_api(
            client, test_student, test_registration, test_entry_point,
            camera_id=test_camera["id"],
        )
        ev_id = created["id"]
        client.post(f"/api/v1/entry-verifications/{ev_id}/begin")
        client.post(f"/api/v1/entry-verifications/{ev_id}/hall-ticket-check")
        client.post(f"/api/v1/entry-verifications/{ev_id}/seat-check")
        client.post(f"/api/v1/entry-verifications/{ev_id}/identity-check")
        response = client.post(
            f"/api/v1/entry-verifications/{ev_id}/evaluate"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ESCALATED"

    def test_evaluate_404(self, client):
        response = client.post(
            "/api/v1/entry-verifications/999999/evaluate"
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# ESCALATE
# ---------------------------------------------------------------------------

class TestEscalateForReview:
    def test_valid_escalation(self, client, test_student, test_registration,
                              test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        client.post(f"/api/v1/entry-verifications/{created['id']}/begin")
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/escalate",
            json={"reason": "Suspicious behavior observed"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ESCALATED"
        assert data["escalation_reason"] == "Suspicious behavior observed"

    def test_missing_reason(self, client, test_student, test_registration,
                            test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        client.post(f"/api/v1/entry-verifications/{created['id']}/begin")
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/escalate",
            json={},
        )
        assert response.status_code == 422

    def test_empty_reason(self, client, test_student, test_registration,
                          test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        client.post(f"/api/v1/entry-verifications/{created['id']}/begin")
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/escalate",
            json={"reason": ""},
        )
        assert response.status_code == 422

    def test_invalid_transition_from_granted(
        self, client, test_student, test_registration, test_entry_point,
        test_hall_ticket, test_seat, test_identity_attempt,
    ):
        created = _create_ev_via_api(
            client, test_student, test_registration, test_entry_point,
        )
        ev_id = created["id"]
        client.post(f"/api/v1/entry-verifications/{ev_id}/begin")
        client.post(f"/api/v1/entry-verifications/{ev_id}/hall-ticket-check")
        client.post(f"/api/v1/entry-verifications/{ev_id}/seat-check")
        client.post(
            f"/api/v1/entry-verifications/{ev_id}/identity-check",
            json={"identity_attempt_id": test_identity_attempt["id"]},
        )
        client.post(f"/api/v1/entry-verifications/{ev_id}/evaluate")
        response = client.post(
            f"/api/v1/entry-verifications/{ev_id}/escalate",
            json={"reason": "Should not work"},
        )
        assert response.status_code == 422

    def test_no_reviewer_identity(self, client, test_student, test_registration,
                                  test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        client.post(f"/api/v1/entry-verifications/{created['id']}/begin")
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/escalate",
            json={"reason": "Test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "reviewer" not in data

    def test_escalate_404(self, client):
        response = client.post(
            "/api/v1/entry-verifications/999999/escalate",
            json={"reason": "Test"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# RESOLVE
# ---------------------------------------------------------------------------

class TestResolveEscalation:
    def test_grant_escalation(self, client, test_student, test_registration,
                              test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        ev_id = created["id"]
        client.post(f"/api/v1/entry-verifications/{ev_id}/begin")
        client.post(
            f"/api/v1/entry-verifications/{ev_id}/escalate",
            json={"reason": "Needs review"},
        )
        response = client.post(
            f"/api/v1/entry-verifications/{ev_id}/resolve",
            json={"granted": True, "reason": "Verified manually"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "GRANTED"
        assert data["resolved_at"] is not None

    def test_deny_escalation(self, client, test_student, test_registration,
                             test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        ev_id = created["id"]
        client.post(f"/api/v1/entry-verifications/{ev_id}/begin")
        client.post(
            f"/api/v1/entry-verifications/{ev_id}/escalate",
            json={"reason": "Needs review"},
        )
        response = client.post(
            f"/api/v1/entry-verifications/{ev_id}/resolve",
            json={"granted": False, "reason": "Cannot verify identity"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "DENIED"
        assert data["resolved_at"] is not None

    def test_invalid_state_not_escalated(self, client, test_student,
                                         test_registration, test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        response = client.post(
            f"/api/v1/entry-verifications/{created['id']}/resolve",
            json={"granted": True},
        )
        assert response.status_code == 422

    def test_no_reviewer_identity(self, client, test_student, test_registration,
                                  test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        ev_id = created["id"]
        client.post(f"/api/v1/entry-verifications/{ev_id}/begin")
        client.post(
            f"/api/v1/entry-verifications/{ev_id}/escalate",
            json={"reason": "Test"},
        )
        response = client.post(
            f"/api/v1/entry-verifications/{ev_id}/resolve",
            json={"granted": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert "reviewer" not in data

    def test_resolve_404(self, client):
        response = client.post(
            "/api/v1/entry-verifications/999999/resolve",
            json={"granted": True},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# SECURITY / PRIVACY
# ---------------------------------------------------------------------------

class TestSecurityPrivacy:
    def test_no_credential_leakage(self, client, test_student, test_registration,
                                   test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        response = client.get(f"/api/v1/entry-verifications/{created['id']}")
        data = response.json()
        assert "password" not in data
        assert "token" not in data
        assert "secret" not in data
        assert "credential" not in data

    def test_no_biometric_leakage(self, client, test_student, test_registration,
                                  test_entry_point, test_identity_attempt):
        created = _create_ev_via_api(
            client, test_student, test_registration, test_entry_point,
        )
        client.post(
            f"/api/v1/entry-verifications/{created['id']}/identity-check",
            json={"identity_attempt_id": test_identity_attempt["id"]},
        )
        response = client.get(f"/api/v1/entry-verifications/{created['id']}")
        data = response.json()
        assert "face" not in data
        assert "embedding" not in data
        assert "image" not in data
        assert "biometric" not in data

    def test_silently_ignores_status_field(self, client, test_student,
                                           test_registration, test_entry_point):
        created = _create_ev_via_api(client, test_student, test_registration,
                                     test_entry_point)
        response = client.post(
            "/api/v1/entry-verifications",
            json={
                "student_id": test_student["id"],
                "exam_registration_id": test_registration["id"],
                "entry_point_id": test_entry_point["id"],
                "status": "GRANTED",
            },
        )
        if response.status_code == 201:
            assert response.json()["status"] == "PENDING"

    def test_list_no_sensitive_data(self, client, test_student, test_registration,
                                   test_entry_point):
        _create_ev_via_api(client, test_student, test_registration,
                           test_entry_point)
        response = client.get("/api/v1/entry-verifications")
        data = response.json()
        for item in data["items"]:
            assert "password" not in item
            assert "token" not in item
            assert "face" not in item
            assert "embedding" not in item

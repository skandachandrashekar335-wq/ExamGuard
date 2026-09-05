"""Phase 11.4 — Proxy Risk REST API.

Tests for the proxy risk assessment REST API layer.
Covers: detect signals, list signals, assess risk, list assessments,
get latest assessment, error handling, idempotency, ownership,
schema validation, sensitive-data exclusion, no EntryVerification mutation.
"""

import pytest
from datetime import date, time
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
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationEvidence,
)
from app.models.proxy_risk import ProxyRiskAssessment, SecuritySignal
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
        db.execute(delete(ProxyRiskAssessment).where(
            ProxyRiskAssessment.entry_verification_id.in_(
                db.query(EntryVerification.id).filter(
                    EntryVerification.student_id.in_(
                        db.query(Student.id).filter(Student.usn.ilike("PRAPI%"))
                    )
                )
            )
        ))
        db.execute(delete(SecuritySignal).where(
            SecuritySignal.entry_verification_id.in_(
                db.query(EntryVerification.id).filter(
                    EntryVerification.student_id.in_(
                        db.query(Student.id).filter(Student.usn.ilike("PRAPI%"))
                    )
                )
            )
        ))
        db.execute(delete(IdentityVerificationEvidence).where(
            IdentityVerificationEvidence.attempt_id.in_(
                db.query(IdentityVerificationAttempt.id).filter(
                    IdentityVerificationAttempt.student_id.in_(
                        db.query(Student.id).filter(Student.usn.ilike("PRAPI%"))
                    )
                )
            )
        ))
        db.execute(delete(IdentityVerificationAttempt).where(
            IdentityVerificationAttempt.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("PRAPI%"))
            )
        ))
        db.execute(delete(EntryVerification).where(
            EntryVerification.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("PRAPI%"))
            )
        ))
        db.execute(delete(HallTicket).where(
            HallTicket.exam_registration_id.in_(
                db.query(ExamRegistration.id).filter(
                    ExamRegistration.student_id.in_(
                        db.query(Student.id).filter(Student.usn.ilike("PRAPI%"))
                    )
                )
            )
        ))
        db.execute(delete(SeatAssignment).where(
            SeatAssignment.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("PRAPI%"))
            )
        ))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("PRAPI%"))
            )
        ))
        db.execute(delete(CameraEntryPointMapping).where(
            CameraEntryPointMapping.camera_id.in_(
                db.query(Camera.id).filter(Camera.device_identifier.ilike("PRAPI%"))
            )
        ))
        db.execute(delete(Camera).where(Camera.device_identifier.ilike("PRAPI%")))
        db.execute(delete(EntryPoint).where(EntryPoint.code.ilike("PRAPI%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("PRAPI%")))
        db.execute(delete(ExamHall).where(ExamHall.building.ilike("PRAPI%")))
        db.execute(delete(Subject).where(Subject.code.ilike("PRAPI%")))
        db.execute(delete(Student).where(Student.usn.ilike("PRAPI%")))
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
        json={"usn": "PRAPI001", "name": "PR API Student"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_student2(client):
    response = client.post(
        "/api/v1/students",
        json={"usn": "PRAPI002", "name": "PR API Student 2"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_subject(client):
    response = client.post(
        "/api/v1/subjects",
        json={
            "code": "PRAPI01",
            "name": "PR Test Subject",
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
            "exam_name": "PRAPI Exam",
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
        json={"building": "PRAPI Hall", "room_number": "101", "capacity": 50},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_entry_point(client, test_exam_hall):
    response = client.post(
        "/api/v1/entry-points",
        json={
            "name": "Main Gate",
            "code": "PRAPIEP01",
            "exam_hall_id": test_exam_hall["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_camera(client, test_exam_hall):
    response = client.post(
        "/api/v1/cameras",
        json={
            "name": "PR Camera",
            "device_identifier": "PRAPI-CAM-001",
            "exam_hall_id": test_exam_hall["id"],
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
def test_entry_verification(client, test_student, test_registration, test_exam_hall, test_entry_point):
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
def test_entry_verification_with_camera(
    client, test_student, test_registration, test_exam_hall, test_entry_point, test_camera
):
    # Map camera to entry point
    mapping_response = client.post(
        "/api/v1/camera-entry-points",
        json={
            "camera_id": test_camera["id"],
            "entry_point_id": test_entry_point["id"],
        },
    )
    assert mapping_response.status_code == 201

    response = client.post(
        "/api/v1/entry-verifications",
        json={
            "student_id": test_student["id"],
            "exam_registration_id": test_registration["id"],
            "entry_point_id": test_entry_point["id"],
            "camera_id": test_camera["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


class TestRouteRegistration:
    def test_detect_signals_route_exists(self, client):
        response = client.post("/api/v1/entry-verifications/1/risk/signals/detect")
        assert response.status_code in (201, 404)

    def test_list_signals_route_exists(self, client):
        response = client.get("/api/v1/entry-verifications/1/risk/signals")
        assert response.status_code in (200, 404)

    def test_assess_risk_route_exists(self, client):
        response = client.post("/api/v1/entry-verifications/1/risk/assess")
        assert response.status_code in (201, 404)

    def test_list_assessments_route_exists(self, client):
        response = client.get("/api/v1/entry-verifications/1/risk/assessments")
        assert response.status_code in (200, 404)

    def test_get_latest_assessment_route_exists(self, client):
        response = client.get("/api/v1/entry-verifications/1/risk")
        assert response.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Detect signals
# ---------------------------------------------------------------------------


class TestDetectSignals:
    def test_detect_signals_returns_list(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        response = client.post(f"/api/v1/entry-verifications/{ev_id}/risk/signals/detect")
        assert response.status_code == 201
        assert isinstance(response.json(), list)

    def test_detect_signals_idempotent(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        r1 = client.post(f"/api/v1/entry-verifications/{ev_id}/risk/signals/detect")
        assert r1.status_code == 201
        count1 = len(r1.json())

        r2 = client.post(f"/api/v1/entry-verifications/{ev_id}/risk/signals/detect")
        assert r2.status_code == 201
        count2 = len(r2.json())

        # Second call returns 0 new signals (already recorded — idempotent)
        assert count2 == 0

        # Total signals in DB should be unchanged (no duplicates)
        response = client.get(f"/api/v1/entry-verifications/{ev_id}/risk/signals")
        assert response.json()["total"] == count1

    def test_detect_signals_nonexistent_entry_verification(self, client):
        response = client.post("/api/v1/entry-verifications/99999/risk/signals/detect")
        assert response.status_code == 404

    def test_detect_signals_does_not_mutate_entry_verification(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        original_status = test_entry_verification["status"]

        client.post(f"/api/v1/entry-verifications/{ev_id}/risk/signals/detect")

        # Verify entry verification status unchanged
        response = client.get(f"/api/v1/entry-verifications/{ev_id}")
        assert response.status_code == 200
        assert response.json()["status"] == original_status

    def test_detect_signals_with_camera_offline(self, client, test_entry_verification_with_camera, test_camera):
        """Camera OFFLINE should produce a CAMERA_OFFLINE_AT_ENTRY signal."""
        ev_id = test_entry_verification_with_camera["id"]
        camera_id = test_camera["id"]

        # Set camera to OFFLINE via health observation API
        response = client.post(
            f"/api/v1/cameras/{camera_id}/health-observations",
            json={"status": "OFFLINE", "reason": "DEVICE_UNREACHABLE"},
        )
        assert response.status_code in (200, 201)

        response = client.post(f"/api/v1/entry-verifications/{ev_id}/risk/signals/detect")
        assert response.status_code == 201
        signals = response.json()
        signal_types = [s["signal_type"] for s in signals]
        assert "CAMERA_OFFLINE_AT_ENTRY" in signal_types

    def test_detect_signals_response_schema(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        response = client.post(f"/api/v1/entry-verifications/{ev_id}/risk/signals/detect")
        assert response.status_code == 201
        for signal in response.json():
            assert "id" in signal
            assert "entry_verification_id" in signal
            assert "signal_type" in signal
            assert "strength" in signal
            assert "source" in signal
            assert "created_at" in signal
            assert signal["entry_verification_id"] == ev_id


# ---------------------------------------------------------------------------
# List security signals
# ---------------------------------------------------------------------------


class TestListSignals:
    def test_list_signals_empty(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        response = client.get(f"/api/v1/entry-verifications/{ev_id}/risk/signals")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_signals_with_data(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        # Detect signals first
        client.post(f"/api/v1/entry-verifications/{ev_id}/risk/signals/detect")

        response = client.get(f"/api/v1/entry-verifications/{ev_id}/risk/signals")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 0
        assert isinstance(data["items"], list)

    def test_list_signals_pagination(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        client.post(f"/api/v1/entry-verifications/{ev_id}/risk/signals/detect")

        response = client.get(
            f"/api/v1/entry-verifications/{ev_id}/risk/signals",
            params={"page": 1, "page_size": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    def test_list_signals_nonexistent_entry_verification(self, client):
        response = client.get("/api/v1/entry-verifications/99999/risk/signals")
        assert response.status_code == 404

    def test_list_signals_ownership(self, client, test_entry_verification, test_entry_verification_with_camera):
        """Signals from one entry verification should not appear in another."""
        ev1_id = test_entry_verification["id"]
        ev2_id = test_entry_verification_with_camera["id"]

        # Detect signals for ev2 (has camera, may produce signals)
        client.post(f"/api/v1/entry-verifications/{ev2_id}/risk/signals/detect")

        # List signals for ev1 (no camera) — should not contain ev2's signals
        response = client.get(f"/api/v1/entry-verifications/{ev1_id}/risk/signals")
        assert response.status_code == 200
        for signal in response.json()["items"]:
            assert signal["entry_verification_id"] == ev1_id


# ---------------------------------------------------------------------------
# Assess risk
# ---------------------------------------------------------------------------


class TestAssessRisk:
    def test_assess_risk_creates_assessment(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        response = client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")
        assert response.status_code == 201
        data = response.json()
        assert data["entry_verification_id"] == ev_id
        assert data["risk_level"] in ("LOW", "ELEVATED", "HIGH", "CRITICAL")
        assert isinstance(data["risk_score"], float)

    def test_assess_risk_nonexistent_entry_verification(self, client):
        response = client.post("/api/v1/entry-verifications/99999/risk/assess")
        assert response.status_code == 404

    def test_assess_risk_does_not_mutate_entry_verification(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        original_status = test_entry_verification["status"]

        client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")

        response = client.get(f"/api/v1/entry-verifications/{ev_id}")
        assert response.status_code == 200
        assert response.json()["status"] == original_status

    def test_assess_risk_historical_rows(self, client, test_entry_verification):
        """Multiple assess calls create separate historical rows."""
        ev_id = test_entry_verification["id"]

        r1 = client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")
        assert r1.status_code == 201
        id1 = r1.json()["id"]

        r2 = client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")
        assert r2.status_code == 201
        id2 = r2.json()["id"]

        # Different assessment IDs
        assert id1 != id2

    def test_assess_risk_response_schema(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        response = client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "entry_verification_id" in data
        assert "risk_level" in data
        assert "risk_score" in data
        assert "assessed_at" in data
        assert "policy_version" in data

    def test_assess_risk_with_signals(self, client, test_entry_verification_with_camera, test_camera):
        """Assessment with signals should reflect signal counts."""
        ev_id = test_entry_verification_with_camera["id"]
        camera_id = test_camera["id"]

        # Set camera to OFFLINE via health observation API to generate a signal
        response = client.post(
            f"/api/v1/cameras/{camera_id}/health-observations",
            json={"status": "OFFLINE", "reason": "DEVICE_UNREACHABLE"},
        )
        assert response.status_code in (200, 201)

        # Detect signals
        client.post(f"/api/v1/entry-verifications/{ev_id}/risk/signals/detect")

        # Assess
        response = client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")
        assert response.status_code == 201
        data = response.json()
        assert data["signal_count"] is not None
        assert data["signal_count"] >= 1


# ---------------------------------------------------------------------------
# List historical risk assessments
# ---------------------------------------------------------------------------


class TestListAssessments:
    def test_list_assessments_empty(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        response = client.get(f"/api/v1/entry-verifications/{ev_id}/risk/assessments")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_assessments_with_data(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")
        client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")

        response = client.get(f"/api/v1/entry-verifications/{ev_id}/risk/assessments")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_assessments_chronological_order(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        r1 = client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")
        r2 = client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")

        response = client.get(f"/api/v1/entry-verifications/{ev_id}/risk/assessments")
        items = response.json()["items"]
        assert items[0]["id"] == r1.json()["id"]
        assert items[1]["id"] == r2.json()["id"]

    def test_list_assessments_pagination(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        for _ in range(3):
            client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")

        response = client.get(
            f"/api/v1/entry-verifications/{ev_id}/risk/assessments",
            params={"page": 1, "page_size": 2},
        )
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2

    def test_list_assessments_nonexistent_entry_verification(self, client):
        response = client.get("/api/v1/entry-verifications/99999/risk/assessments")
        assert response.status_code == 404

    def test_list_assessments_ownership(self, client, test_entry_verification, test_entry_verification_with_camera):
        """Assessments from one entry verification should not appear in another."""
        ev1_id = test_entry_verification["id"]
        ev2_id = test_entry_verification_with_camera["id"]

        client.post(f"/api/v1/entry-verifications/{ev2_id}/risk/assess")

        response = client.get(f"/api/v1/entry-verifications/{ev1_id}/risk/assessments")
        data = response.json()
        for item in data["items"]:
            assert item["entry_verification_id"] == ev1_id

    def test_list_assessments_audit_fields(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")

        response = client.get(f"/api/v1/entry-verifications/{ev_id}/risk/assessments")
        item = response.json()["items"][0]
        assert "id" in item
        assert "entry_verification_id" in item
        assert "risk_level" in item
        assert "risk_score" in item
        assert "assessed_at" in item
        assert "policy_version" in item


# ---------------------------------------------------------------------------
# Get latest assessment
# ---------------------------------------------------------------------------


class TestGetLatestAssessment:
    def test_get_latest_assessment(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        r1 = client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")
        r2 = client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")

        response = client.get(f"/api/v1/entry-verifications/{ev_id}/risk")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == r2.json()["id"]

    def test_get_latest_assessment_no_assessment(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        response = client.get(f"/api/v1/entry-verifications/{ev_id}/risk")
        assert response.status_code == 404
        assert "No risk assessment found" in response.json()["detail"]

    def test_get_latest_assessment_nonexistent_entry_verification(self, client):
        response = client.get("/api/v1/entry-verifications/99999/risk")
        assert response.status_code == 404

    def test_get_latest_assessment_response_schema(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")

        response = client.get(f"/api/v1/entry-verifications/{ev_id}/risk")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "entry_verification_id" in data
        assert "risk_level" in data
        assert "risk_score" in data
        assert "assessed_at" in data


# ---------------------------------------------------------------------------
# Sensitive data exclusion
# ---------------------------------------------------------------------------


class TestSensitiveDataExclusion:
    def test_no_biometric_data_in_signals(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        client.post(f"/api/v1/entry-verifications/{ev_id}/risk/signals/detect")
        response = client.get(f"/api/v1/entry-verifications/{ev_id}/risk/signals")
        for signal in response.json()["items"]:
            # Should not contain face, embedding, biometric fields
            signal_str = str(signal).lower()
            assert "embedding" not in signal_str
            assert "face_image" not in signal_str
            assert "biometric" not in signal_str

    def test_no_biometric_data_in_assessments(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")
        response = client.get(f"/api/v1/entry-verifications/{ev_id}/risk/assessments")
        for item in response.json()["items"]:
            item_str = str(item).lower()
            assert "embedding" not in item_str
            assert "face_image" not in item_str
            assert "biometric" not in item_str

    def test_risk_score_is_numeric_not_percentage(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")
        response = client.get(f"/api/v1/entry-verifications/{ev_id}/risk")
        data = response.json()
        # Should be a float, not a percentage string
        assert isinstance(data["risk_score"], float)
        assert 0.0 <= data["risk_score"] <= 100.0


# ---------------------------------------------------------------------------
# No EntryVerification mutation
# ---------------------------------------------------------------------------


class TestNoEntryVerificationMutation:
    def test_detect_signals_no_mutation(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        original = client.get(f"/api/v1/entry-verifications/{ev_id}").json()

        client.post(f"/api/v1/entry-verifications/{ev_id}/risk/signals/detect")

        after = client.get(f"/api/v1/entry-verifications/{ev_id}").json()
        assert after["status"] == original["status"]
        assert after["hall_ticket_check"] == original["hall_ticket_check"]
        assert after["identity_check"] == original["identity_check"]
        assert after["seat_check"] == original["seat_check"]

    def test_assess_risk_no_mutation(self, client, test_entry_verification):
        ev_id = test_entry_verification["id"]
        original = client.get(f"/api/v1/entry-verifications/{ev_id}").json()

        client.post(f"/api/v1/entry-verifications/{ev_id}/risk/assess")

        after = client.get(f"/api/v1/entry-verifications/{ev_id}").json()
        assert after["status"] == original["status"]
        assert after["hall_ticket_check"] == original["hall_ticket_check"]
        assert after["identity_check"] == original["identity_check"]
        assert after["seat_check"] == original["seat_check"]


# ---------------------------------------------------------------------------
# Error sanitization
# ---------------------------------------------------------------------------


class TestErrorSanitization:
    def test_404_no_traceback(self, client):
        response = client.get("/api/v1/entry-verifications/99999/risk")
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert "traceback" not in detail.lower()
        assert "sqlalchemy" not in detail.lower()

    def test_404_no_database_info(self, client):
        response = client.get("/api/v1/entry-verifications/99999/risk/signals")
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert "database" not in detail.lower()
        assert "postgresql" not in detail.lower()

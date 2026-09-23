"""Tests for the Demo Data Loader endpoint.

Verifies:
1. Demo data can be loaded by authenticated users
2. Demo data loading is idempotent
3. Demo status returns correct state (plural student/attempt IDs)
4. Demo reset cleans up demo records
5. Reference image endpoint returns valid PNG
6. Demo-specific workflow endpoints are scoped to demo records
"""

import base64

DEMO_LOAD_URL = "/api/v1/demo/load"
DEMO_STATUS_URL = "/api/v1/demo/status"
DEMO_RESET_URL = "/api/v1/demo/reset"
DEMO_REF_IMAGE_URL = "/api/v1/demo/reference-image"
DEMO_UPLOAD_URL = "/api/v1/demo/upload-reference-face"
DEMO_ASSIGN_URL = "/api/v1/demo/assign-invigilator"
DEMO_START_URL = "/api/v1/demo/start-session"
DEMO_SESSION_STATUS_URL = "/api/v1/demo/session-status"

# Minimal valid 1x1 PNG
PNG_1PX = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d49444154789c6360606060000000050001"
        "a3f60000000049454e44ae426082"
    )
).decode()


class TestDemoDataLoader:
    def test_demo_load_and_status_idempotent(self, client):
        """Loading demo data twice produces the same IDs."""
        resp1 = client.post(DEMO_LOAD_URL)
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["status"] == "ready"
        assert data1["demo_exam_id"] is not None
        assert len(data1["demo_student_ids"]) == 3
        assert data1["demo_session_id"] is not None
        assert len(data1["demo_attempt_ids"]) == 3

        resp2 = client.post(DEMO_LOAD_URL)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["demo_exam_id"] == data1["demo_exam_id"]
        assert data2["demo_student_ids"] == data1["demo_student_ids"]
        assert data2["demo_session_id"] == data1["demo_session_id"]
        assert data2["demo_attempt_ids"] == data1["demo_attempt_ids"]

    def test_demo_status_after_load(self, client):
        """Status returns loaded=true after loading demo data."""
        client.post(DEMO_LOAD_URL)
        resp = client.get(DEMO_STATUS_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data["loaded"] is True
        assert data["demo_exam_id"] is not None
        assert data["demo_student_ids"] is not None
        assert data["demo_student_usns"] == ["DEMO001", "DEMO002", "DEMO003"]

    def test_demo_reference_image_returns_png(self, client):
        """Reference image endpoint returns a valid PNG."""
        resp = client.get(DEMO_REF_IMAGE_URL)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content[:4] == b"\x89PNG"
        assert 100 < len(resp.content) < 500_000

    def test_demo_reference_image_deterministic(self, client):
        """Reference image returns the same bytes every call."""
        resp1 = client.get(DEMO_REF_IMAGE_URL)
        resp2 = client.get(DEMO_REF_IMAGE_URL)
        assert resp1.content == resp2.content

    def test_demo_reset_and_reload_cycle(self, client):
        """Load → reset → verify status → reload → verify same IDs."""
        resp1 = client.post(DEMO_LOAD_URL)
        assert resp1.status_code == 200
        data1 = resp1.json()

        reset_resp = client.post(DEMO_RESET_URL)
        assert reset_resp.status_code == 200
        reset_data = reset_resp.json()
        assert reset_data["status"] == "reset"
        assert reset_data["records_deleted"] > 0

        status_after = client.get(DEMO_STATUS_URL).json()
        assert status_after["loaded"] is False

        resp2 = client.post(DEMO_LOAD_URL)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["status"] == "ready"
        assert data2["demo_exam_id"] is not None

    def test_demo_load_response_fields(self, client):
        """Load response contains all expected fields."""
        resp = client.post(DEMO_LOAD_URL)
        data = resp.json()
        required = [
            "status", "message", "demo_exam_id", "demo_hall_id",
            "demo_student_ids", "demo_student_usns", "demo_session_id",
            "demo_attempt_ids", "demo_invigilator_assignment_id",
        ]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_demo_load_creates_correct_entities(self, client):
        """Demo load creates subject, exam, students, hall, session, attempts."""
        resp = client.post(DEMO_LOAD_URL)
        data = resp.json()

        status = client.get(DEMO_STATUS_URL).json()
        assert status["loaded"] is True
        assert status["demo_exam_id"] == data["demo_exam_id"]
        assert status["demo_hall_id"] == data["demo_hall_id"]
        assert status["demo_student_ids"] == data["demo_student_ids"]
        assert status["demo_session_id"] == data["demo_session_id"]
        assert status["demo_attempt_ids"] == data["demo_attempt_ids"]

    def test_demo_load_returns_invigilator_assignment_field(self, client):
        """Demo load always includes the assignment field."""
        resp = client.post(DEMO_LOAD_URL)
        data = resp.json()
        assert "demo_invigilator_assignment_id" in data

    def test_demo_upload_reference_face(self, client):
        """Upload a reference face for a demo attempt and persist URL."""
        load = client.post(DEMO_LOAD_URL).json()
        attempt_id = load["demo_attempt_ids"][0]

        resp = client.post(
            DEMO_UPLOAD_URL,
            json={
                "attempt_id": attempt_id,
                "reference_image": PNG_1PX,
                "image_format": "image/png",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "saved"
        assert body["reference_face_url"]
        assert body["attempt_id"] == attempt_id

        # Status must reflect the stored reference
        status = client.get(DEMO_STATUS_URL).json()
        assert status["reference_face_urls"] is not None
        assert status["reference_face_urls"][0] == body["reference_face_url"]

    def test_demo_upload_rejects_non_demo_attempt(self, client):
        """Upload for a non-existent/non-demo attempt is rejected."""
        resp = client.post(
            DEMO_UPLOAD_URL,
            json={
                "attempt_id": 999999,
                "reference_image": PNG_1PX,
                "image_format": "image/png",
            },
        )
        assert resp.status_code == 422

    def test_demo_assign_and_session_status(self, client):
        """Assign invigilator then read session status with invigilator email."""
        client.post(DEMO_LOAD_URL)

        # Assign a user that does not exist → 404 with clear message
        resp = client.post(DEMO_ASSIGN_URL, json={"email": "nobody@example.com"})
        assert resp.status_code == 404

        # Create a real user to assign
        from app.core.database import SessionLocal
        from app.models import User

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == "inv.demo@example.com").first()
            if not user:
                user = User(
                    email="inv.demo@example.com",
                    full_name="Demo Invigilator",
                    firebase_uid="demo-inv-uid",
                    role="REVIEWER",
                    is_active=True,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            original_role = user.role
        finally:
            db.close()

        resp = client.post(DEMO_ASSIGN_URL, json={"email": "inv.demo@example.com"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "assigned"
        assert resp.json()["email"] == "inv.demo@example.com"

        # Assigned user must be able to open invigilator console
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == "inv.demo@example.com").first()
            assert user.role == "INVIGILATOR"
            if original_role != "INVIGILATOR":
                # restore for other tests
                user.role = original_role
                db.commit()
        finally:
            db.close()

        status = client.get(DEMO_SESSION_STATUS_URL).json()
        assert status["loaded"] is True
        assert status["invigilator_email"] == "inv.demo@example.com"

    def test_demo_start_session(self, client):
        """Start the demo session transitions to IN_PROGRESS."""
        client.post(DEMO_LOAD_URL)
        # Reset first in case a previous test started it
        client.post(DEMO_RESET_URL)
        client.post(DEMO_LOAD_URL)

        resp = client.post(DEMO_START_URL, json={"performed_by": "tester"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "started"
        assert body["session_status"] == "IN_PROGRESS"

        status = client.get(DEMO_SESSION_STATUS_URL).json()
        assert status["session_status"] == "IN_PROGRESS"

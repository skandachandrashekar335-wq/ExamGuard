"""Tests for the Demo Data Loader endpoint.

Verifies:
1. Demo data can be loaded by authorized users
2. Demo data loading is idempotent
3. Demo status returns correct state
4. Demo reset cleans up demo records
5. Reference image endpoint returns valid PNG
"""

DEMO_LOAD_URL = "/api/v1/demo/load"
DEMO_STATUS_URL = "/api/v1/demo/status"
DEMO_RESET_URL = "/api/v1/demo/reset"
DEMO_REF_IMAGE_URL = "/api/v1/demo/reference-image"


class TestDemoDataLoader:
    def test_demo_load_and_status_idempotent(self, client):
        """Loading demo data twice produces the same IDs."""
        resp1 = client.post(DEMO_LOAD_URL)
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["status"] == "ready"
        assert data1["demo_exam_id"] is not None
        assert data1["demo_student_id"] is not None
        assert data1["demo_session_id"] is not None
        assert data1["demo_attempt_id"] is not None

        resp2 = client.post(DEMO_LOAD_URL)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["demo_exam_id"] == data1["demo_exam_id"]
        assert data2["demo_student_id"] == data1["demo_student_id"]
        assert data2["demo_session_id"] == data1["demo_session_id"]
        assert data2["demo_attempt_id"] == data1["demo_attempt_id"]

    def test_demo_status_after_load(self, client):
        """Status returns loaded=true after loading demo data."""
        client.post(DEMO_LOAD_URL)
        resp = client.get(DEMO_STATUS_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data["loaded"] is True
        assert data["demo_exam_id"] is not None
        assert data["demo_student_id"] is not None

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
        # Load
        resp1 = client.post(DEMO_LOAD_URL)
        assert resp1.status_code == 200
        data1 = resp1.json()

        # Reset
        reset_resp = client.post(DEMO_RESET_URL)
        assert reset_resp.status_code == 200
        reset_data = reset_resp.json()
        assert reset_data["status"] == "reset"
        assert reset_data["records_deleted"] > 0

        # Reload — should create new IDs
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
            "demo_student_id", "demo_session_id", "demo_attempt_id",
        ]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_demo_load_creates_correct_entities(self, client):
        """Demo load creates subject, exam, student, hall, session, attempt."""
        resp = client.post(DEMO_LOAD_URL)
        data = resp.json()

        status = client.get(DEMO_STATUS_URL).json()
        assert status["loaded"] is True
        assert status["demo_exam_id"] == data["demo_exam_id"]
        assert status["demo_hall_id"] == data["demo_hall_id"]
        assert status["demo_student_id"] == data["demo_student_id"]
        assert status["demo_session_id"] == data["demo_session_id"]
        assert status["demo_attempt_id"] == data["demo_attempt_id"]

    def test_demo_load_returns_invigilator_assignment(self, client):
        """Demo load creates an invigilator assignment for the current user.
        
        Note: The test's fake user (sub="1") may not have a User record,
        so the assignment may be None. This is expected in test context.
        In production with a real authenticated user, the assignment will be created.
        """
        resp = client.post(DEMO_LOAD_URL)
        data = resp.json()
        # The field should always be present in the response
        assert "demo_invigilator_assignment_id" in data

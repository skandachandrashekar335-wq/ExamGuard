import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

from app.core.database import SessionLocal
from app.main import app
from app.models.student import Student


@pytest.fixture(autouse=True)
def clean_test_students():
    """Remove test students before each test to avoid USN conflicts."""
    db = SessionLocal()
    try:
        test_prefixes = (
            "API00", "DUP", "NORM", "GET00", "UPD0", "LIST",
            "SRCH", "DEL00", "HID00", "UPD00", "UPD01",
        )
        for prefix in test_prefixes:
            db.execute(
                delete(Student).where(Student.usn.ilike(f"{prefix}%"))
            )
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


class TestStudentAPI:
    def test_create_student(self, client):
        response = client.post(
            "/api/v1/students",
            json={"usn": "API001", "name": "API Test Student One"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["usn"] == "API001"
        assert data["name"] == "API Test Student One"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_student_missing_required(self, client):
        response = client.post("/api/v1/students", json={"usn": "ONLY"})
        assert response.status_code == 422

    def test_create_student_duplicate_usn(self, client):
        client.post(
            "/api/v1/students",
            json={"usn": "DUPAPI001", "name": "First"},
        )
        response = client.post(
            "/api/v1/students",
            json={"usn": "DUPAPI001", "name": "Second"},
        )
        assert response.status_code == 409

    def test_usn_whitespace_normalization(self, client):
        response = client.post(
            "/api/v1/students",
            json={"usn": "  NORM001  ", "name": "Normalized Student"},
        )
        assert response.status_code == 201
        assert response.json()["usn"] == "NORM001"

    def test_usn_duplicate_after_normalization(self, client):
        client.post(
            "/api/v1/students",
            json={"usn": "NORM002", "name": "Norm Two"},
        )
        response = client.post(
            "/api/v1/students",
            json={"usn": "  NORM002  ", "name": "Norm Two Dup"},
        )
        assert response.status_code == 409

    def test_get_student(self, client):
        create = client.post(
            "/api/v1/students",
            json={"usn": "GET001", "name": "Get Test Student"},
        )
        student_id = create.json()["id"]
        response = client.get(f"/api/v1/students/{student_id}")
        assert response.status_code == 200
        assert response.json()["usn"] == "GET001"

    def test_get_student_not_found(self, client):
        response = client.get("/api/v1/students/999999")
        assert response.status_code == 404

    def test_update_student(self, client):
        create = client.post(
            "/api/v1/students",
            json={"usn": "UPD001", "name": "Original Name"},
        )
        student_id = create.json()["id"]
        response = client.patch(
            f"/api/v1/students/{student_id}",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"
        assert response.json()["usn"] == "UPD001"

    def test_update_student_duplicate_usn(self, client):
        client.post(
            "/api/v1/students",
            json={"usn": "UPD002", "name": "Existing"},
        )
        create = client.post(
            "/api/v1/students",
            json={"usn": "UPD003", "name": "To Update"},
        )
        student_id = create.json()["id"]
        response = client.patch(
            f"/api/v1/students/{student_id}",
            json={"usn": "UPD002"},
        )
        assert response.status_code == 409

    def test_list_students(self, client):
        client.post(
            "/api/v1/students",
            json={"usn": "LIST001", "name": "List Student One"},
        )
        client.post(
            "/api/v1/students",
            json={"usn": "LIST002", "name": "List Student Two"},
        )
        response = client.get("/api/v1/students")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert data["total"] >= 2

    def test_pagination(self, client):
        response = client.get("/api/v1/students?page=1&page_size=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 1
        assert data["page"] == 1
        assert data["page_size"] == 1

    def test_search_by_usn(self, client):
        client.post(
            "/api/v1/students",
            json={"usn": "SRCH101", "name": "Searchable Student"},
        )
        response = client.get("/api/v1/students?search=SRCH101")
        assert response.status_code == 200
        assert response.json()["total"] >= 1
        assert any(s["usn"] == "SRCH101" for s in response.json()["items"])

    def test_search_by_name(self, client):
        client.post(
            "/api/v1/students",
            json={"usn": "SRCH201", "name": "Uniquefinder Name"},
        )
        response = client.get("/api/v1/students?search=Uniquefinder")
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    def test_deactivate_student(self, client):
        create = client.post(
            "/api/v1/students",
            json={"usn": "DEL001", "name": "To Deactivate"},
        )
        student_id = create.json()["id"]
        response = client.delete(f"/api/v1/students/{student_id}")
        assert response.status_code == 200
        assert response.json()["is_active"] is False

        get_response = client.get(f"/api/v1/students/{student_id}")
        assert get_response.status_code == 200

    def test_deactivated_student_hidden_from_list(self, client):
        create = client.post(
            "/api/v1/students",
            json={"usn": "HID001", "name": "Hidden Student"},
        )
        student_id = create.json()["id"]
        client.delete(f"/api/v1/students/{student_id}")

        response = client.get("/api/v1/students")
        items = response.json()["items"]
        assert not any(s["usn"] == "HID001" for s in items)

    def test_deactivated_student_visible_with_include_inactive(self, client):
        create = client.post(
            "/api/v1/students",
            json={"usn": "HID002", "name": "Hidden Two"},
        )
        student_id = create.json()["id"]
        client.delete(f"/api/v1/students/{student_id}")

        response = client.get("/api/v1/students?include_inactive=true")
        items = response.json()["items"]
        assert any(s["usn"] == "HID002" for s in items)

    def test_deactivate_nonexistent_student(self, client):
        response = client.delete("/api/v1/students/999999")
        assert response.status_code == 404

    def test_empty_usn_rejected(self, client):
        response = client.post(
            "/api/v1/students",
            json={"usn": "", "name": "Empty USN"},
        )
        assert response.status_code == 422

    def test_empty_name_rejected(self, client):
        response = client.post(
            "/api/v1/students",
            json={"usn": "VALID01", "name": ""},
        )
        assert response.status_code == 422

    def test_health_still_works(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

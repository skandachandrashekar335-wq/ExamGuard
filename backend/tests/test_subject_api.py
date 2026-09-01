import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.subject import Subject


@pytest.fixture(autouse=True)
def clean_test_subjects():
    """Remove test subjects before each test to avoid conflicts."""
    db = SessionLocal()
    try:
        test_prefixes = ("SUB", "GET", "DUP", "FILT", "SRCH", "DEL", "UPD", "API")
        for prefix in test_prefixes:
            db.execute(
                delete(Subject).where(Subject.code.ilike(f"{prefix}%"))
            )
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


class TestSubjectAPI:
    def test_create_subject(self, client):
        response = client.post(
            "/api/v1/subjects",
            json={
                "code": "SUB001",
                "name": "API Test Subject",
                "department": "Computer Science",
                "semester": 5,
                "credits": 4,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "SUB001"
        assert data["name"] == "API Test Subject"
        assert data["department"] == "Computer Science"
        assert data["semester"] == 5
        assert data["credits"] == 4
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_subject_minimal(self, client):
        response = client.post(
            "/api/v1/subjects",
            json={
                "code": "SUB002",
                "name": "Minimal Subject",
                "department": "Electronics",
                "semester": 3,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["credits"] is None

    def test_create_subject_missing_required(self, client):
        response = client.post(
            "/api/v1/subjects",
            json={"code": "SUB003"},
        )
        assert response.status_code == 422

    def test_create_subject_duplicate(self, client):
        client.post(
            "/api/v1/subjects",
            json={
                "code": "DUP001",
                "name": "First",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        response = client.post(
            "/api/v1/subjects",
            json={
                "code": "DUP001",
                "name": "Second",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        assert response.status_code == 409

    def test_create_subject_same_code_different_dept(self, client):
        client.post(
            "/api/v1/subjects",
            json={
                "code": "DUP002",
                "name": "CS Version",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        response = client.post(
            "/api/v1/subjects",
            json={
                "code": "DUP002",
                "name": "EE Version",
                "department": "Electrical Engineering",
                "semester": 5,
            },
        )
        assert response.status_code == 201

    def test_get_subject(self, client):
        create = client.post(
            "/api/v1/subjects",
            json={
                "code": "GET001",
                "name": "Get Test Subject",
                "department": "Mechanical",
                "semester": 4,
            },
        )
        subject_id = create.json()["id"]

        response = client.get(f"/api/v1/subjects/{subject_id}")
        assert response.status_code == 200
        assert response.json()["id"] == subject_id
        assert response.json()["code"] == "GET001"

    def test_get_subject_not_found(self, client):
        response = client.get("/api/v1/subjects/999999")
        assert response.status_code == 404

    def test_list_subjects(self, client):
        client.post(
            "/api/v1/subjects",
            json={
                "code": "LIST01",
                "name": "List Subject 1",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        client.post(
            "/api/v1/subjects",
            json={
                "code": "LIST02",
                "name": "List Subject 2",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        response = client.get("/api/v1/subjects")
        assert response.status_code == 200
        assert response.json()["total"] >= 2

    def test_pagination(self, client):
        for i in range(5):
            client.post(
                "/api/v1/subjects",
                json={
                    "code": f"FILT{i:02d}",
                    "name": f"Filter Subject {i}",
                    "department": "Physics",
                    "semester": 2,
                },
            )

        response = client.get("/api/v1/subjects?page=1&page_size=2")
        data = response.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_search_by_code(self, client):
        client.post(
            "/api/v1/subjects",
            json={
                "code": "SRCH01",
                "name": "Searchable Subject",
                "department": "Chemistry",
                "semester": 3,
            },
        )
        response = client.get("/api/v1/subjects?search=SRCH01")
        data = response.json()
        assert any(s["code"] == "SRCH01" for s in data["items"])

    def test_search_by_name(self, client):
        client.post(
            "/api/v1/subjects",
            json={
                "code": "SRCH02",
                "name": "Unique Name XYZ",
                "department": "Biology",
                "semester": 4,
            },
        )
        response = client.get("/api/v1/subjects?search=Unique+Name+XYZ")
        data = response.json()
        assert any(s["name"] == "Unique Name XYZ" for s in data["items"])

    def test_filter_by_department(self, client):
        client.post(
            "/api/v1/subjects",
            json={
                "code": "FILT01",
                "name": "Filter Dept Subject",
                "department": "Mathematics",
                "semester": 1,
            },
        )
        response = client.get("/api/v1/subjects?department=Mathematics")
        data = response.json()
        assert all(s["department"] == "Mathematics" for s in data["items"])

    def test_filter_by_semester(self, client):
        client.post(
            "/api/v1/subjects",
            json={
                "code": "FILT02",
                "name": "Filter Sem Subject",
                "department": "Physics",
                "semester": 7,
            },
        )
        response = client.get("/api/v1/subjects?semester=7")
        data = response.json()
        assert all(s["semester"] == 7 for s in data["items"])

    def test_update_subject(self, client):
        create = client.post(
            "/api/v1/subjects",
            json={
                "code": "UPD001",
                "name": "Original Name",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        subject_id = create.json()["id"]

        response = client.patch(
            f"/api/v1/subjects/{subject_id}",
            json={"name": "Updated Name", "credits": 3},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"
        assert response.json()["credits"] == 3

    def test_update_subject_not_found(self, client):
        response = client.patch(
            "/api/v1/subjects/999999",
            json={"name": "Updated"},
        )
        assert response.status_code == 404

    def test_update_subject_duplicate_code(self, client):
        client.post(
            "/api/v1/subjects",
            json={
                "code": "UPD002",
                "name": "Subject A",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        create2 = client.post(
            "/api/v1/subjects",
            json={
                "code": "UPD003",
                "name": "Subject B",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        subject_id = create2.json()["id"]

        response = client.patch(
            f"/api/v1/subjects/{subject_id}",
            json={"code": "UPD002"},
        )
        assert response.status_code == 409

    def test_soft_delete(self, client):
        create = client.post(
            "/api/v1/subjects",
            json={
                "code": "DEL001",
                "name": "Delete Test",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        subject_id = create.json()["id"]

        response = client.delete(f"/api/v1/subjects/{subject_id}")
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_deleted_subject_hidden_from_list(self, client):
        create = client.post(
            "/api/v1/subjects",
            json={
                "code": "DEL002",
                "name": "Hidden Subject",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        subject_id = create.json()["id"]
        client.delete(f"/api/v1/subjects/{subject_id}")

        response = client.get("/api/v1/subjects")
        data = response.json()
        assert not any(s["id"] == subject_id for s in data["items"])

    def test_deleted_subject_visible_with_include_inactive(self, client):
        create = client.post(
            "/api/v1/subjects",
            json={
                "code": "DEL003",
                "name": "Visible Hidden Subject",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        subject_id = create.json()["id"]
        client.delete(f"/api/v1/subjects/{subject_id}")

        response = client.get("/api/v1/subjects?include_inactive=true")
        data = response.json()
        assert any(s["id"] == subject_id for s in data["items"])

    def test_get_deleted_subject(self, client):
        create = client.post(
            "/api/v1/subjects",
            json={
                "code": "DEL004",
                "name": "Get Deleted",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        subject_id = create.json()["id"]
        client.delete(f"/api/v1/subjects/{subject_id}")

        response = client.get(f"/api/v1/subjects/{subject_id}")
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_delete_nonexistent(self, client):
        response = client.delete("/api/v1/subjects/999999")
        assert response.status_code == 404

    def test_empty_code_rejected(self, client):
        response = client.post(
            "/api/v1/subjects",
            json={
                "code": "",
                "name": "Empty Code",
                "department": "CS",
                "semester": 5,
            },
        )
        assert response.status_code == 422

    def test_empty_name_rejected(self, client):
        response = client.post(
            "/api/v1/subjects",
            json={
                "code": "API004",
                "name": "",
                "department": "CS",
                "semester": 5,
            },
        )
        assert response.status_code == 422

    def test_invalid_semester_rejected(self, client):
        response = client.post(
            "/api/v1/subjects",
            json={
                "code": "API005",
                "name": "Bad Semester",
                "department": "CS",
                "semester": 9,
            },
        )
        assert response.status_code == 422

    def test_invalid_credits_rejected(self, client):
        response = client.post(
            "/api/v1/subjects",
            json={
                "code": "API006",
                "name": "Bad Credits",
                "department": "CS",
                "semester": 5,
                "credits": -1,
            },
        )
        assert response.status_code == 422

    def test_whitespace_trimming(self, client):
        response = client.post(
            "/api/v1/subjects",
            json={
                "code": "  API007  ",
                "name": "  Trimmed Name  ",
                "department": "  CS  ",
                "semester": 5,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "API007"
        assert data["name"] == "Trimmed Name"
        assert data["department"] == "CS"

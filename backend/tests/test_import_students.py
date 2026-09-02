import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.student import Student


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        db.execute(delete(Student).where(Student.usn.ilike("IMP%")))
        db.execute(delete(Student).where(Student.usn.ilike("DUPIMP%")))
        db.execute(delete(Student).where(Student.usn.ilike("MIXIMP%")))
        db.execute(delete(Student).where(Student.usn.ilike("NORMIMP%")))
        db.execute(delete(Student).where(Student.usn.ilike("MAXIMP%")))
        db.execute(delete(Student).where(Student.usn.ilike("INVIMP%")))
        db.execute(delete(Student).where(Student.usn.ilike("EMPTYIMP%")))
        db.execute(delete(Student).where(Student.usn.ilike("DBLIMP%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


class TestImportStudentsSchema:
    def test_empty_list_rejected(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={"students": []},
        )
        assert response.status_code == 422

    def test_missing_students_key(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={},
        )
        assert response.status_code == 422

    def test_item_missing_usn(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"name": "No USN"}]},
        )
        assert response.status_code == 422

    def test_item_missing_name(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "IMP001"}]},
        )
        assert response.status_code == 422

    def test_item_empty_usn(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "", "name": "Empty USN"}]},
        )
        assert response.status_code == 422

    def test_item_empty_name(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "IMP002", "name": ""}]},
        )
        assert response.status_code == 422

    def test_usn_too_long(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "A" * 21, "name": "Long USN"}]},
        )
        assert response.status_code == 422

    def test_name_too_long(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "IMP003", "name": "N" * 256}]},
        )
        assert response.status_code == 422


class TestImportStudentsAllValid:
    def test_single_valid_student(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "IMP101", "name": "Imported Student One"}]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 1
        assert data["created"] == 1
        assert data["skipped"] == 0
        assert data["failed"] == 0
        assert data["results"][0]["status"] == "created"
        assert data["results"][0]["usn"] == "IMP101"
        assert data["results"][0]["error"] is None

    def test_multiple_valid_students(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={
                "students": [
                    {"usn": "IMP201", "name": "Student Alpha"},
                    {"usn": "IMP202", "name": "Student Beta"},
                    {"usn": "IMP203", "name": "Student Gamma"},
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 3
        assert data["created"] == 3
        assert data["skipped"] == 0
        assert data["failed"] == 0


class TestImportStudentsAllDuplicates:
    def test_all_duplicates(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "DUPIMP01", "name": "Dup One"}]},
        )
        response = client.post(
            "/api/v1/import/students",
            json={
                "students": [
                    {"usn": "DUPIMP01", "name": "Dup One Again"},
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 1
        assert data["created"] == 0
        assert data["skipped"] == 1
        assert data["results"][0]["status"] == "skipped"
        assert "already exists" in data["results"][0]["error"]

    def test_multiple_duplicates(self, client):
        client.post(
            "/api/v1/import/students",
            json={
                "students": [
                    {"usn": "DUPIMP02", "name": "Dup Alpha"},
                    {"usn": "DUPIMP03", "name": "Dup Beta"},
                ]
            },
        )
        response = client.post(
            "/api/v1/import/students",
            json={
                "students": [
                    {"usn": "DUPIMP02", "name": "Dup Alpha Again"},
                    {"usn": "DUPIMP03", "name": "Dup Beta Again"},
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 2
        assert data["created"] == 0
        assert data["skipped"] == 2


class TestImportStudentsMixed:
    def test_mixed_valid_duplicate(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "MIXIMP01", "name": "Existing Mixed"}]},
        )
        response = client.post(
            "/api/v1/import/students",
            json={
                "students": [
                    {"usn": "MIXIMP01", "name": "Existing Mixed Dup"},
                    {"usn": "MIXIMP02", "name": "New Mixed Student"},
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 2
        assert data["created"] == 1
        assert data["skipped"] == 1
        statuses = [r["status"] for r in data["results"]]
        assert "created" in statuses
        assert "skipped" in statuses

    def test_mixed_valid_invalid_rejected(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={
                "students": [
                    {"usn": "MIXIMP03", "name": "Valid Mixed"},
                    {"usn": "", "name": "Bad USN"},
                ]
            },
        )
        assert response.status_code == 422


class TestImportStudentsWhitespace:
    def test_usn_whitespace_trimmed(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "  NORMIMP01  ", "name": "Trimmed Student"}]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["results"][0]["usn"] == "NORMIMP01"
        assert data["created"] == 1

    def test_name_whitespace_trimmed(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "NORMIMP02", "name": "  Trimmed Name  "}]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 1

    def test_duplicate_after_normalization(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "NORMIMP03", "name": "Norm Existing"}]},
        )
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "  NORMIMP03  ", "name": "Norm Dup"}]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["skipped"] == 1
        assert data["created"] == 0


class TestImportStudentsDatabaseSafety:
    def test_integrity_error_handled(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "DBLIMP01", "name": "First DBL"}]},
        )
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "DBLIMP01", "name": "Second DBL"}]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["failed"] == 0
        assert data["results"][0]["status"] == "skipped"

    def test_no_raw_db_errors_exposed(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={
                "students": [
                    {"usn": "INVIMP01", "name": "Valid"},
                    {"usn": "INVIMP01", "name": "Dup"},
                ]
            },
        )
        assert response.status_code == 201
        for result in response.json()["results"]:
            if result["error"]:
                assert "unique" not in result["error"].lower()
                assert "constraint" not in result["error"].lower()
                assert "integrity" not in result["error"].lower()

    def test_existing_student_not_modified(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "DBLIMP02", "name": "Original Name"}]},
        )
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "DBLIMP02", "name": "Different Name"}]},
        )
        assert response.status_code == 201
        assert response.json()["results"][0]["status"] == "skipped"
        get_resp = client.get("/api/v1/students?search=DBLIMP02")
        items = get_resp.json()["items"]
        assert any(s["usn"] == "DBLIMP02" and s["name"] == "Original Name" for s in items)


class TestImportStudentsPerRowResults:
    def test_per_row_results_match_input(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={
                "students": [
                    {"usn": "IMP401", "name": "Row One"},
                    {"usn": "IMP402", "name": "Row Two"},
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["results"]) == 2
        assert data["results"][0]["usn"] == "IMP401"
        assert data["results"][1]["usn"] == "IMP402"

    def test_skipped_has_error_message(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "IMP501", "name": "Error Row Student"}]},
        )
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "IMP501", "name": "Dup"}]},
        )
        data = response.json()
        assert data["results"][0]["error"] is not None
        assert len(data["results"][0]["error"]) > 0

    def test_created_has_no_error(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "IMP601", "name": "No Error Student"}]},
        )
        data = response.json()
        assert data["results"][0]["error"] is None

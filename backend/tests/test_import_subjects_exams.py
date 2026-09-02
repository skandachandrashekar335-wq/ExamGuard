import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.exam import Exam
from app.models.subject import Subject


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        db.execute(delete(Exam).where(Exam.exam_name.ilike("IMP_EX%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("IMP_SUB%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("DUP_EX%")))
        db.commit()
    except Exception:
        db.rollback()
    try:
        db.execute(delete(Subject).where(Subject.code.ilike("IMPSUB%")))
        db.execute(delete(Subject).where(Subject.code.ilike("DUPSUB%")))
        db.execute(delete(Subject).where(Subject.code.ilike("MIXSUB%")))
        db.execute(delete(Subject).where(Subject.code.ilike("NORMSUB%")))
        db.commit()
    except Exception:
        db.rollback()
    try:
        db.execute(delete(Subject).where(Subject.code.ilike("EXSUB%")))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


class TestImportSubjectsOnly:
    def test_single_subject(self, client):
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "subjects": [
                    {
                        "code": "IMPSUB01",
                        "name": "Imported Subject One",
                        "department": "Computer Science",
                        "semester": 5,
                        "credits": 4,
                    }
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["subject_total"] == 1
        assert data["subject_created"] == 1
        assert data["subject_skipped"] == 0
        assert data["subject_failed"] == 0
        assert data["exam_total"] == 0
        assert data["subject_results"][0]["status"] == "created"
        assert data["subject_results"][0]["code"] == "IMPSUB01"

    def test_multiple_subjects(self, client):
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "subjects": [
                    {
                        "code": "IMPSUB02",
                        "name": "Subject Alpha",
                        "department": "Computer Science",
                        "semester": 5,
                    },
                    {
                        "code": "IMPSUB03",
                        "name": "Subject Beta",
                        "department": "Mathematics",
                        "semester": 3,
                        "credits": 3,
                    },
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["subject_total"] == 2
        assert data["subject_created"] == 2

    def test_duplicate_subject_skipped(self, client):
        client.post(
            "/api/v1/import/subjects-exams",
            json={
                "subjects": [
                    {
                        "code": "DUPSUB01",
                        "name": "Dup Subject",
                        "department": "Computer Science",
                        "semester": 5,
                    }
                ]
            },
        )
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "subjects": [
                    {
                        "code": "DUPSUB01",
                        "name": "Dup Subject Again",
                        "department": "Computer Science",
                        "semester": 5,
                    }
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["subject_created"] == 0
        assert data["subject_skipped"] == 1
        assert data["subject_results"][0]["status"] == "skipped"
        assert "already exists" in data["subject_results"][0]["error"]

    def test_subject_same_code_different_dept_allowed(self, client):
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "subjects": [
                    {
                        "code": "IMPSUB04",
                        "name": "CS Version",
                        "department": "Computer Science",
                        "semester": 5,
                    },
                    {
                        "code": "IMPSUB04",
                        "name": "Civil Version",
                        "department": "Civil Engineering",
                        "semester": 3,
                    },
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["subject_created"] == 2

    def test_subject_whitespace_trimmed(self, client):
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "subjects": [
                    {
                        "code": "  NORMSUB01  ",
                        "name": "  Trimmed Subject  ",
                        "department": "  Computer Science  ",
                        "semester": 5,
                    }
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["subject_results"][0]["code"] == "NORMSUB01"
        assert data["subject_created"] == 1


class TestImportExamsOnly:
    def test_exam_with_existing_subject(self, client):
        client.post(
            "/api/v1/subjects",
            json={
                "code": "EXSUB01",
                "name": "Existing Subject for Exams",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "exams": [
                    {
                        "subject_code": "EXSUB01",
                        "exam_name": "IMP_EX End Semester",
                        "exam_date": "2026-09-15",
                        "start_time": "10:00",
                        "end_time": "13:00",
                        "semester": 5,
                        "department": "Computer Science",
                    }
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["subject_total"] == 0
        assert data["exam_total"] == 1
        assert data["exam_created"] == 1
        assert data["exam_results"][0]["status"] == "created"

    def test_exam_subject_not_found(self, client):
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "exams": [
                    {
                        "subject_code": "NONEXIST",
                        "exam_name": "IMP_EX No Subject",
                        "exam_date": "2026-09-15",
                        "start_time": "10:00",
                        "end_time": "13:00",
                        "semester": 5,
                        "department": "Computer Science",
                    }
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["exam_failed"] == 1
        assert data["exam_results"][0]["status"] == "failed"
        assert "not found" in data["exam_results"][0]["error"]

    def test_exam_duplicate_skipped(self, client):
        client.post(
            "/api/v1/subjects",
            json={
                "code": "EXSUB02",
                "name": "Dup Exam Subject",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        client.post(
            "/api/v1/import/subjects-exams",
            json={
                "exams": [
                    {
                        "subject_code": "EXSUB02",
                        "exam_name": "DUP_EX First",
                        "exam_date": "2026-09-15",
                        "start_time": "10:00",
                        "end_time": "13:00",
                        "semester": 5,
                        "department": "Computer Science",
                    }
                ]
            },
        )
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "exams": [
                    {
                        "subject_code": "EXSUB02",
                        "exam_name": "DUP_EX Second",
                        "exam_date": "2026-09-15",
                        "start_time": "10:00",
                        "end_time": "13:00",
                        "semester": 5,
                        "department": "Computer Science",
                    }
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["exam_skipped"] == 1
        assert "already exists" in data["exam_results"][0]["error"]

    def test_exam_start_after_end_rejected(self, client):
        client.post(
            "/api/v1/subjects",
            json={
                "code": "EXSUB03",
                "name": "Time Test Subject",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "exams": [
                    {
                        "subject_code": "EXSUB03",
                        "exam_name": "IMP_EX Bad Time",
                        "exam_date": "2026-09-15",
                        "start_time": "13:00",
                        "end_time": "10:00",
                        "semester": 5,
                        "department": "Computer Science",
                    }
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["exam_failed"] == 1
        assert "start_time" in data["exam_results"][0]["error"]

    def test_exam_invalid_date_format(self, client):
        client.post(
            "/api/v1/subjects",
            json={
                "code": "EXSUB04",
                "name": "Date Test Subject",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "exams": [
                    {
                        "subject_code": "EXSUB04",
                        "exam_name": "IMP_EX Bad Date",
                        "exam_date": "15-09-2026",
                        "start_time": "10:00",
                        "end_time": "13:00",
                        "semester": 5,
                        "department": "Computer Science",
                    }
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["exam_failed"] == 1
        assert data["exam_results"][0]["status"] == "failed"
        assert data["exam_results"][0]["error"] is not None

    def test_exam_invalid_time_format(self, client):
        client.post(
            "/api/v1/subjects",
            json={
                "code": "EXSUB05",
                "name": "Time Format Subject",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "exams": [
                    {
                        "subject_code": "EXSUB05",
                        "exam_name": "IMP_EX Bad Time Format",
                        "exam_date": "2026-09-15",
                        "start_time": "abc",
                        "end_time": "13:00",
                        "semester": 5,
                        "department": "Computer Science",
                    }
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["exam_failed"] == 1


class TestImportCombined:
    def test_subjects_then_exams(self, client):
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "subjects": [
                    {
                        "code": "MIXSUB01",
                        "name": "Combined Subject",
                        "department": "Computer Science",
                        "semester": 5,
                    }
                ],
                "exams": [
                    {
                        "subject_code": "MIXSUB01",
                        "exam_name": "IMP_SUB Combined Exam",
                        "exam_date": "2026-09-15",
                        "start_time": "10:00",
                        "end_time": "13:00",
                        "semester": 5,
                        "department": "Computer Science",
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["subject_created"] == 1
        assert data["exam_created"] == 1

    def test_exam_references_just_imported_subject(self, client):
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "subjects": [
                    {
                        "code": "MIXSUB02",
                        "name": "Ref Subject",
                        "department": "Mathematics",
                        "semester": 3,
                    }
                ],
                "exams": [
                    {
                        "subject_code": "MIXSUB02",
                        "exam_name": "IMP_SUB Ref Exam",
                        "exam_date": "2026-10-01",
                        "start_time": "09:00",
                        "end_time": "12:00",
                        "semester": 3,
                        "department": "Mathematics",
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["subject_created"] == 1
        assert data["exam_created"] == 1

    def test_mixed_results(self, client):
        client.post(
            "/api/v1/import/subjects-exams",
            json={
                "subjects": [
                    {
                        "code": "MIXSUB03",
                        "name": "Existing Mix Subject",
                        "department": "Computer Science",
                        "semester": 5,
                    }
                ]
            },
        )
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "subjects": [
                    {
                        "code": "MIXSUB03",
                        "name": "Dup Mix Subject",
                        "department": "Computer Science",
                        "semester": 5,
                    },
                    {
                        "code": "MIXSUB04",
                        "name": "New Mix Subject",
                        "department": "Physics",
                        "semester": 4,
                    },
                ],
                "exams": [
                    {
                        "subject_code": "MIXSUB03",
                        "exam_name": "IMP_SUB Mix Exam Existing",
                        "exam_date": "2026-09-20",
                        "start_time": "10:00",
                        "end_time": "13:00",
                        "semester": 5,
                        "department": "Computer Science",
                    },
                    {
                        "subject_code": "NONEXIST",
                        "exam_name": "IMP_SUB Mix Exam No Subject",
                        "exam_date": "2026-09-20",
                        "start_time": "10:00",
                        "end_time": "13:00",
                        "semester": 5,
                        "department": "Computer Science",
                    },
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["subject_created"] == 1
        assert data["subject_skipped"] == 1
        assert data["exam_created"] == 1
        assert data["exam_failed"] == 1


class TestImportSchemaValidation:
    def test_empty_request_rejected(self, client):
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={},
        )
        assert response.status_code == 422

    def test_both_empty_rejected(self, client):
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={"subjects": [], "exams": []},
        )
        assert response.status_code == 422

    def test_subject_missing_required_field(self, client):
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={"subjects": [{"code": "X"}]},
        )
        assert response.status_code == 422

    def test_exam_missing_required_field(self, client):
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={"exams": [{"subject_code": "X"}]},
        )
        assert response.status_code == 422

    def test_subject_invalid_semester(self, client):
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "subjects": [
                    {
                        "code": "IMPSUB05",
                        "name": "Bad Sem",
                        "department": "CS",
                        "semester": 9,
                    }
                ]
            },
        )
        assert response.status_code == 422

    def test_exam_invalid_semester(self, client):
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "exams": [
                    {
                        "subject_code": "X",
                        "exam_name": "Bad",
                        "exam_date": "2026-09-15",
                        "start_time": "10:00",
                        "end_time": "13:00",
                        "semester": 0,
                        "department": "CS",
                    }
                ]
            },
        )
        assert response.status_code == 422


class TestImportDatabaseSafety:
    def test_no_raw_db_errors_exposed(self, client):
        client.post(
            "/api/v1/import/subjects-exams",
            json={
                "subjects": [
                    {
                        "code": "DUPSUB02",
                        "name": "First",
                        "department": "CS",
                        "semester": 5,
                    }
                ]
            },
        )
        response = client.post(
            "/api/v1/import/subjects-exams",
            json={
                "subjects": [
                    {
                        "code": "DUPSUB02",
                        "name": "Second",
                        "department": "CS",
                        "semester": 5,
                    }
                ]
            },
        )
        assert response.status_code == 201
        for result in response.json()["subject_results"]:
            if result["error"]:
                assert "unique" not in result["error"].lower()
                assert "constraint" not in result["error"].lower()
                assert "integrity" not in result["error"].lower()

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.exam import Exam
from app.models.exam_registration import ExamRegistration
from app.models.student import Student
from app.models.subject import Subject


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("BREGSTU%"))
            )
        ))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("BREGEXAM%")))
        db.execute(delete(Subject).where(Subject.code.ilike("BREGSUB%")))
        db.execute(delete(Student).where(Student.usn.ilike("BREGSTU%")))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def test_exam(client):
    """Create a test exam for registration tests."""
    student_resp = client.post(
        "/api/v1/students",
        json={"usn": "BREGSTU01", "name": "Registration Test Student"},
    )
    assert student_resp.status_code == 201
    student = student_resp.json()

    subject_resp = client.post(
        "/api/v1/subjects",
        json={
            "code": "BREGSUB01",
            "name": "Registration Test Subject",
            "department": "Computer Science",
            "semester": 5,
        },
    )
    assert subject_resp.status_code == 201
    subject = subject_resp.json()

    exam_resp = client.post(
        "/api/v1/exams",
        json={
            "subject_id": subject["id"],
            "exam_name": "BREGEXAM End Semester",
            "exam_date": "2026-09-15",
            "start_time": "10:00:00",
            "end_time": "13:00:00",
            "semester": 5,
            "department": "Computer Science",
        },
    )
    assert exam_resp.status_code == 201
    return {"exam": exam_resp.json(), "student": student}


class TestBulkRegisterAllValid:
    def test_single_registration(self, client, test_exam):
        response = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [test_exam["student"]["id"]],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 1
        assert data["created"] == 1
        assert data["skipped"] == 0
        assert data["failed"] == 0
        assert data["results"][0]["status"] == "created"
        assert data["results"][0]["registration_id"] is not None
        assert data["results"][0]["error"] is None

    def test_multiple_registrations(self, client, test_exam):
        students = []
        for i in range(2, 5):
            resp = client.post(
                "/api/v1/students",
                json={"usn": f"BREGSTU{i:02d}", "name": f"Student {i}"},
            )
            assert resp.status_code == 201
            students.append(resp.json()["id"])

        response = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": students,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 3
        assert data["created"] == 3
        assert data["skipped"] == 0
        assert data["failed"] == 0


class TestBulkRegisterDuplicates:
    def test_duplicate_registration_skipped(self, client, test_exam):
        client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [test_exam["student"]["id"]],
            },
        )
        response = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [test_exam["student"]["id"]],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 0
        assert data["skipped"] == 1
        assert data["results"][0]["status"] == "skipped"
        assert "already registered" in data["results"][0]["error"]

    def test_mixed_valid_duplicate(self, client, test_exam):
        client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [test_exam["student"]["id"]],
            },
        )
        new_student = client.post(
            "/api/v1/students",
            json={"usn": "BREGSTU10", "name": "New Student"},
        )
        assert new_student.status_code == 201

        response = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [
                    test_exam["student"]["id"],
                    new_student.json()["id"],
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 2
        assert data["created"] == 1
        assert data["skipped"] == 1


class TestBulkRegisterInvalid:
    def test_nonexistent_student(self, client, test_exam):
        response = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [999999],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["failed"] == 1
        assert data["results"][0]["status"] == "failed"
        assert "not found" in data["results"][0]["error"]

    def test_nonexistent_exam(self, client):
        student_resp = client.post(
            "/api/v1/students",
            json={"usn": "BREGSTU20", "name": "No Exam Student"},
        )
        assert student_resp.status_code == 201

        response = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": 999999,
                "student_ids": [student_resp.json()["id"]],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["failed"] == 1
        assert "not found" in data["results"][0]["error"]

    def test_inactive_student(self, client, test_exam):
        inactive = client.post(
            "/api/v1/students",
            json={"usn": "BREGSTU30", "name": "Inactive Student"},
        )
        assert inactive.status_code == 201
        client.delete(f"/api/v1/students/{inactive.json()['id']}")

        response = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [inactive.json()["id"]],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["failed"] == 1
        assert "not active" in data["results"][0]["error"]

    def test_inactive_exam(self, client):
        student_resp = client.post(
            "/api/v1/students",
            json={"usn": "BREGSTU40", "name": "Inactive Exam Student"},
        )
        assert student_resp.status_code == 201

        subject_resp = client.post(
            "/api/v1/subjects",
            json={
                "code": "BREGSUB02",
                "name": "Inactive Exam Subject",
                "department": "Computer Science",
                "semester": 5,
            },
        )
        assert subject_resp.status_code == 201

        exam_resp = client.post(
            "/api/v1/exams",
            json={
                "subject_id": subject_resp.json()["id"],
                "exam_name": "BREGEXAM Inactive",
                "exam_date": "2026-09-20",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        assert exam_resp.status_code == 201
        client.delete(f"/api/v1/exams/{exam_resp.json()['id']}")

        response = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": exam_resp.json()["id"],
                "student_ids": [student_resp.json()["id"]],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["failed"] == 1
        assert "not active" in data["results"][0]["error"]


class TestBulkRegisterMixed:
    def test_mixed_valid_duplicate_notfound(self, client, test_exam):
        client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [test_exam["student"]["id"]],
            },
        )
        new_student = client.post(
            "/api/v1/students",
            json={"usn": "BREGSTU50", "name": "Mixed Student"},
        )
        assert new_student.status_code == 201

        response = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [
                    test_exam["student"]["id"],
                    new_student.json()["id"],
                    999999,
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 3
        assert data["skipped"] == 1
        assert data["created"] == 1
        assert data["failed"] == 1

        statuses = [r["status"] for r in data["results"]]
        assert "skipped" in statuses
        assert "created" in statuses
        assert "failed" in statuses


class TestBulkRegisterSchemaValidation:
    def test_empty_student_ids(self, client, test_exam):
        response = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [],
            },
        )
        assert response.status_code == 422

    def test_missing_exam_id(self, client):
        response = client.post(
            "/api/v1/import/registrations",
            json={"student_ids": [1]},
        )
        assert response.status_code == 422

    def test_missing_student_ids(self, client, test_exam):
        response = client.post(
            "/api/v1/import/registrations",
            json={"exam_id": test_exam["exam"]["id"]},
        )
        assert response.status_code == 422

    def test_invalid_exam_id(self, client):
        response = client.post(
            "/api/v1/import/registrations",
            json={"exam_id": 0, "student_ids": [1]},
        )
        assert response.status_code == 422

    def test_invalid_student_id(self, client, test_exam):
        response = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [-1],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["failed"] == 1
        assert "not found" in data["results"][0]["error"]


class TestBulkCancel:
    def test_cancel_single(self, client, test_exam):
        reg_resp = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [test_exam["student"]["id"]],
            },
        )
        assert reg_resp.status_code == 201
        reg_id = reg_resp.json()["results"][0]["registration_id"]

        response = client.post(
            "/api/v1/import/registrations/cancel",
            json={"registration_ids": [reg_id]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["cancelled"] == 1
        assert data["results"][0]["status"] == "cancelled"

    def test_cancel_multiple(self, client, test_exam):
        students = []
        for i in range(6, 9):
            resp = client.post(
                "/api/v1/students",
                json={"usn": f"BREGSTU{i:02d}", "name": f"Cancel Student {i}"},
            )
            assert resp.status_code == 201
            students.append(resp.json()["id"])

        reg_resp = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": students,
            },
        )
        assert reg_resp.status_code == 201
        reg_ids = [r["registration_id"] for r in reg_resp.json()["results"]]

        response = client.post(
            "/api/v1/import/registrations/cancel",
            json={"registration_ids": reg_ids},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["cancelled"] == 3

    def test_cancel_nonexistent(self, client):
        response = client.post(
            "/api/v1/import/registrations/cancel",
            json={"registration_ids": [999999]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["failed"] == 1
        assert "not found" in data["results"][0]["error"]

    def test_cancel_already_cancelled(self, client, test_exam):
        reg_resp = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [test_exam["student"]["id"]],
            },
        )
        assert reg_resp.status_code == 201
        reg_id = reg_resp.json()["results"][0]["registration_id"]

        client.post(
            "/api/v1/import/registrations/cancel",
            json={"registration_ids": [reg_id]},
        )

        response = client.post(
            "/api/v1/import/registrations/cancel",
            json={"registration_ids": [reg_id]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["skipped"] == 1
        assert "already cancelled" in data["results"][0]["error"]

    def test_cancel_mixed_valid_notfound(self, client, test_exam):
        reg_resp = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [test_exam["student"]["id"]],
            },
        )
        assert reg_resp.status_code == 201
        reg_id = reg_resp.json()["results"][0]["registration_id"]

        response = client.post(
            "/api/v1/import/registrations/cancel",
            json={"registration_ids": [reg_id, 999999]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["cancelled"] == 1
        assert data["failed"] == 1

    def test_cancel_schema_validation(self, client):
        response = client.post(
            "/api/v1/import/registrations/cancel",
            json={"registration_ids": []},
        )
        assert response.status_code == 422

    def test_cancel_missing_field(self, client):
        response = client.post(
            "/api/v1/import/registrations/cancel",
            json={},
        )
        assert response.status_code == 422


class TestBulkRegisterDatabaseSafety:
    def test_no_raw_db_errors(self, client, test_exam):
        client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [test_exam["student"]["id"]],
            },
        )
        response = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [test_exam["student"]["id"]],
            },
        )
        assert response.status_code == 201
        for result in response.json()["results"]:
            if result["error"]:
                assert "unique" not in result["error"].lower()
                assert "constraint" not in result["error"].lower()
                assert "integrity" not in result["error"].lower()

    def test_registration_not_hard_deleted(self, client, test_exam):
        reg_resp = client.post(
            "/api/v1/import/registrations",
            json={
                "exam_id": test_exam["exam"]["id"],
                "student_ids": [test_exam["student"]["id"]],
            },
        )
        assert reg_resp.status_code == 201
        reg_id = reg_resp.json()["results"][0]["registration_id"]

        client.post(
            "/api/v1/import/registrations/cancel",
            json={"registration_ids": [reg_id]},
        )

        get_resp = client.get(f"/api/v1/exam-registrations/{reg_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "CANCELLED"

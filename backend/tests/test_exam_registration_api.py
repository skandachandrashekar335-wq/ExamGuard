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
def clean_test_data():
    """Remove test data before each test to avoid conflicts."""
    db = SessionLocal()
    try:
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("REGSTU%"))
            )
        ))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("REGEXAM%")))
        db.execute(delete(Subject).where(Subject.code.ilike("REGSUB%")))
        db.execute(delete(Student).where(Student.usn.ilike("REGSTU%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def test_student(client):
    """Create a test student for registration tests."""
    response = client.post(
        "/api/v1/students",
        json={
            "usn": "REGSTU01",
            "name": "Registration Test Student",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_subject(client):
    """Create a test subject for exam creation."""
    response = client.post(
        "/api/v1/subjects",
        json={
            "code": "REGSUB01",
            "name": "Registration Test Subject",
            "department": "Computer Science",
            "semester": 5,
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_exam(client, test_subject):
    """Create a test exam for registration tests."""
    response = client.post(
        "/api/v1/exams",
        json={
            "subject_id": test_subject["id"],
            "exam_name": "REGEXAM Final Exam",
            "exam_date": "2026-12-15",
            "start_time": "10:00:00",
            "end_time": "13:00:00",
            "semester": 5,
            "department": "Computer Science",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def inactive_student(client):
    """Create an inactive student."""
    response = client.post(
        "/api/v1/students",
        json={
            "usn": "REGSTU02",
            "name": "Inactive Test Student",
        },
    )
    assert response.status_code == 201
    student_id = response.json()["id"]
    client.patch(f"/api/v1/students/{student_id}", json={"is_active": False})
    return response.json()


@pytest.fixture()
def inactive_exam(client, test_subject):
    """Create an inactive exam."""
    response = client.post(
        "/api/v1/exams",
        json={
            "subject_id": test_subject["id"],
            "exam_name": "REGEXAM Inactive Exam",
            "exam_date": "2026-12-20",
            "start_time": "10:00:00",
            "end_time": "13:00:00",
            "semester": 5,
            "department": "Computer Science",
        },
    )
    assert response.status_code == 201
    exam_id = response.json()["id"]
    client.delete(f"/api/v1/exams/{exam_id}")
    return response.json()


class TestExamRegistrationAPI:
    def test_create_registration(self, client, test_student, test_exam):
        response = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["student_id"] == test_student["id"]
        assert data["exam_id"] == test_exam["id"]
        assert data["status"] == "REGISTERED"
        assert "id" in data
        assert "registered_at" in data

    def test_get_registration(self, client, test_student, test_exam):
        create = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        reg_id = create.json()["id"]

        response = client.get(f"/api/v1/exam-registrations/{reg_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == reg_id
        assert data["student_usn"] == "REGSTU01"
        assert data["student_name"] == "Registration Test Student"
        assert data["exam_name"] == "REGEXAM Final Exam"

    def test_get_registration_not_found(self, client):
        response = client.get("/api/v1/exam-registrations/999999")
        assert response.status_code == 404

    def test_list_registrations(self, client, test_student, test_exam):
        client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        response = client.get("/api/v1/exam-registrations")
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    def test_pagination(self, client, test_student, test_exam):
        client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        response = client.get("/api/v1/exam-registrations?page=1&page_size=2")
        data = response.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_filter_by_student(self, client, test_student, test_exam):
        client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        response = client.get(
            f"/api/v1/exam-registrations?student_id={test_student['id']}"
        )
        data = response.json()
        assert all(
            r["student_id"] == test_student["id"] for r in data["items"]
        )

    def test_filter_by_exam(self, client, test_student, test_exam):
        client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        response = client.get(
            f"/api/v1/exam-registrations?exam_id={test_exam['id']}"
        )
        data = response.json()
        assert all(
            r["exam_id"] == test_exam["id"] for r in data["items"]
        )

    def test_filter_by_status(self, client, test_student, test_exam):
        client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        response = client.get(
            "/api/v1/exam-registrations?status=REGISTERED"
        )
        data = response.json()
        assert all(
            r["status"] == "REGISTERED" for r in data["items"]
        )

    def test_duplicate_registration_rejected(self, client, test_student, test_exam):
        client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        response = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        assert response.status_code == 409

    def test_database_uniqueness_enforcement(self, client, test_student, test_exam):
        client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        response = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    def test_missing_student_rejected(self, client, test_exam):
        response = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": 999999,
                "exam_id": test_exam["id"],
            },
        )
        assert response.status_code == 404

    def test_missing_exam_rejected(self, client, test_student):
        response = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": 999999,
            },
        )
        assert response.status_code == 404

    def test_inactive_student_rejected(self, client, inactive_student, test_exam):
        response = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": inactive_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        assert response.status_code == 409

    def test_inactive_exam_rejected(self, client, test_student, inactive_exam):
        response = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": inactive_exam["id"],
            },
        )
        assert response.status_code == 409

    def test_cancel_registration(self, client, test_student, test_exam):
        create = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        reg_id = create.json()["id"]

        response = client.delete(f"/api/v1/exam-registrations/{reg_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"

    def test_cancelled_registration_remains_in_database(self, client, test_student, test_exam):
        create = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        reg_id = create.json()["id"]
        client.delete(f"/api/v1/exam-registrations/{reg_id}")

        db = SessionLocal()
        try:
            reg = db.query(ExamRegistration).filter(
                ExamRegistration.id == reg_id
            ).first()
            assert reg is not None
            assert reg.status == "CANCELLED"
        finally:
            db.close()

    def test_cancelled_registration_visible_through_status_filter(
        self, client, test_student, test_exam
    ):
        create = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        reg_id = create.json()["id"]
        client.delete(f"/api/v1/exam-registrations/{reg_id}")

        response = client.get(
            "/api/v1/exam-registrations?status=CANCELLED"
        )
        data = response.json()
        assert any(r["id"] == reg_id for r in data["items"])

    def test_reactivate_cancelled_registration(self, client, test_student, test_exam):
        create = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        reg_id = create.json()["id"]
        client.delete(f"/api/v1/exam-registrations/{reg_id}")

        response = client.patch(
            f"/api/v1/exam-registrations/{reg_id}",
            json={"status": "REGISTERED"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "REGISTERED"

    def test_reactivate_does_not_create_duplicate_row(
        self, client, test_student, test_exam
    ):
        create = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        reg_id = create.json()["id"]
        client.delete(f"/api/v1/exam-registrations/{reg_id}")

        client.patch(
            f"/api/v1/exam-registrations/{reg_id}",
            json={"status": "REGISTERED"},
        )

        db = SessionLocal()
        try:
            count = db.query(ExamRegistration).filter(
                ExamRegistration.student_id == test_student["id"],
                ExamRegistration.exam_id == test_exam["id"],
            ).count()
            assert count == 1
        finally:
            db.close()

    def test_invalid_status_rejected(self, client, test_student, test_exam):
        create = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": test_exam["id"],
            },
        )
        reg_id = create.json()["id"]

        response = client.patch(
            f"/api/v1/exam-registrations/{reg_id}",
            json={"status": "INVALID_STATUS"},
        )
        assert response.status_code == 422

    def test_update_registration_not_found(self, client):
        response = client.patch(
            "/api/v1/exam-registrations/999999",
            json={"status": "CANCELLED"},
        )
        assert response.status_code == 404

    def test_cancel_nonexistent_registration(self, client):
        response = client.delete("/api/v1/exam-registrations/999999")
        assert response.status_code == 404

    def test_missing_required_fields(self, client):
        response = client.post("/api/v1/exam-registrations", json={})
        assert response.status_code == 422

    def test_foreign_key_enforcement(self, client):
        response = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": 999999,
                "exam_id": 999999,
            },
        )
        assert response.status_code == 404

    def test_same_student_different_exams_allowed(
        self, client, test_student, test_subject
    ):
        exam1_response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "REGEXAM Exam A",
                "exam_date": "2026-12-16",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        exam2_response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "REGEXAM Exam B",
                "exam_date": "2026-12-17",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        exam1_id = exam1_response.json()["id"]
        exam2_id = exam2_response.json()["id"]

        resp1 = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": exam1_id,
            },
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": test_student["id"],
                "exam_id": exam2_id,
            },
        )
        assert resp2.status_code == 201

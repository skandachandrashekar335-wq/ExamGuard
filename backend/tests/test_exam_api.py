from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.auth import Role, get_current_user
from app.core.database import SessionLocal
from app.main import app
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.examination_session import ExaminationSession
from app.models.invigilator_assignment import InvigilatorAssignment
from app.models.subject import Subject
from app.models.user import User


@pytest.fixture(autouse=True)
def clean_test_data():
    """Remove test data before each test to avoid conflicts."""
    db = SessionLocal()
    try:
        test_exam_ids = db.query(Exam.id).filter(
            Exam.exam_name.ilike("EXAM%")
            | Exam.exam_name.ilike("Test%")
            | Exam.exam_name.ilike("Dup%")
            | Exam.exam_name.ilike("Filter%")
            | Exam.exam_name.ilike("Search%")
        )
        db.execute(delete(InvigilatorAssignment).where(
            InvigilatorAssignment.exam_id.in_(test_exam_ids)
        ))
        db.execute(delete(ExaminationSession).where(
            ExaminationSession.exam_id.in_(test_exam_ids)
        ))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("EXAM%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("Test%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("Dup%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("Filter%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("Search%")))
        db.execute(delete(ExamHall).where(
            ExamHall.building.ilike("EXAMSETUP%")
        ))
        db.execute(delete(User).where(User.email.ilike("examsetup-%")))
        db.execute(delete(Subject).where(Subject.code.ilike("EXSUB%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def test_subject(client):
    """Create a test subject for exam tests."""
    response = client.post(
        "/api/v1/subjects",
        json={
            "code": "EXSUB01",
            "name": "Test Subject for Exams",
            "department": "Computer Science",
            "semester": 5,
        },
    )
    assert response.status_code == 201
    return response.json()


class TestExamAPI:
    def test_create_exam(self, client, test_subject):
        response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM End Semester",
                "exam_date": "2026-09-15",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["exam_name"] == "EXAM End Semester"
        assert data["exam_date"] == "2026-09-15"
        assert data["semester"] == 5
        assert data["is_active"] is True
        assert "id" in data

    def test_operator_can_create_exam(self, client, test_subject, monkeypatch):
        monkeypatch.setitem(
            app.dependency_overrides,
            get_current_user,
            lambda: {
                "sub": "operator-setup",
                "role": Role.OPERATOR,
                "email": "operator@example.com",
            },
        )
        response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Operator Create",
                "exam_date": "2026-11-01",
                "start_time": "10:00",
                "end_time": "12:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        assert response.status_code == 201, response.text

    def test_reviewer_with_active_assignment_cannot_create_exam(
        self, client, test_subject, monkeypatch
    ):
        db = SessionLocal()
        try:
            exam = Exam(
                subject_id=test_subject["id"],
                exam_name="EXAMSETUP Assigned Reviewer's Existing Exam",
                exam_date=date(2026, 11, 2),
                start_time=time(10, 0),
                end_time=time(12, 0),
                semester=5,
                department="Computer Science",
            )
            hall = ExamHall(
                building="EXAMSETUP Block A",
                room_number="101",
                capacity=40,
            )
            user = User(
                email="examsetup-reviewer@example.com",
                full_name="Assigned Reviewer",
                role=Role.REVIEWER,
                is_active=True,
            )
            db.add_all([exam, hall, user])
            db.commit()
            db.refresh(exam)
            db.refresh(hall)
            db.refresh(user)
            db.add(InvigilatorAssignment(
                user_id=user.id,
                exam_id=exam.id,
                exam_hall_id=hall.id,
                is_active=True,
            ))
            db.commit()
            user_id = user.id
        finally:
            db.close()

        monkeypatch.setitem(
            app.dependency_overrides,
            get_current_user,
            lambda: {
                "sub": str(user_id),
                "role": Role.REVIEWER,
                "email": "examsetup-reviewer@example.com",
            },
        )
        response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Reviewer Must Not Create",
                "exam_date": "2026-11-03",
                "start_time": "10:00",
                "end_time": "12:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        assert response.status_code == 403

    def test_exam_can_be_persisted_with_hall_and_not_started_session(
        self, client, test_subject
    ):
        exam_response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Setup Persistence",
                "exam_date": "2026-11-04",
                "start_time": "09:30",
                "end_time": "12:30",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        assert exam_response.status_code == 201, exam_response.text
        exam = exam_response.json()
        hall_response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "EXAMSETUP Block B",
                "room_number": "202",
                "capacity": 50,
            },
        )
        assert hall_response.status_code == 201, hall_response.text

        session_response = client.post(
            "/api/v1/examination-sessions",
            json={
                "exam_id": exam["id"],
                "exam_hall_id": hall_response.json()["id"],
                "expected_capacity": 50,
            },
        )
        assert session_response.status_code == 201, session_response.text
        session = session_response.json()
        assert session["exam_id"] == exam["id"]
        assert session["exam_hall_id"] == hall_response.json()["id"]
        assert session["status"] == "NOT_STARTED"
        assert session["gate_status"] == "GATES_CLOSED"

        details = client.get(f"/api/v1/exams/{exam['id']}")
        assert details.status_code == 200
        assert details.json()["exam_name"] == "EXAM Setup Persistence"
        assert details.json()["exam_date"] == "2026-11-04"
        assert details.json()["start_time"].startswith("09:30")
        assert details.json()["end_time"].startswith("12:30")

    def test_get_exam(self, client, test_subject):
        create = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Get Test",
                "exam_date": "2026-09-16",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        exam_id = create.json()["id"]

        response = client.get(f"/api/v1/exams/{exam_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == exam_id
        assert data["subject_code"] == "EXSUB01"
        assert data["subject_name"] == "Test Subject for Exams"

    def test_get_exam_not_found(self, client):
        response = client.get("/api/v1/exams/999999")
        assert response.status_code == 404

    def test_list_exams(self, client, test_subject):
        client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM List 1",
                "exam_date": "2026-09-17",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM List 2",
                "exam_date": "2026-09-18",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        response = client.get("/api/v1/exams")
        assert response.status_code == 200
        assert response.json()["total"] >= 2

    def test_pagination(self, client, test_subject):
        for i in range(5):
            client.post(
                "/api/v1/exams",
                json={
                    "subject_id": test_subject["id"],
                    "exam_name": f"EXAM Page {i}",
                    "exam_date": f"2026-09-{20 + i}",
                    "start_time": "10:00:00",
                    "end_time": "13:00:00",
                    "semester": 5,
                    "department": "Computer Science",
                },
            )

        response = client.get("/api/v1/exams?page=1&page_size=2")
        data = response.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_search_by_exam_name(self, client, test_subject):
        client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Search Unique XYZ",
                "exam_date": "2026-09-25",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        response = client.get("/api/v1/exams?search=Search+Unique+XYZ")
        data = response.json()
        assert any(e["exam_name"] == "EXAM Search Unique XYZ" for e in data["items"])

    def test_filter_by_subject(self, client, test_subject):
        client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Filter Subject",
                "exam_date": "2026-09-26",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        response = client.get(f"/api/v1/exams?subject_id={test_subject['id']}")
        data = response.json()
        assert all(e["subject_id"] == test_subject["id"] for e in data["items"])

    def test_filter_by_department(self, client, test_subject):
        client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Filter Dept",
                "exam_date": "2026-09-27",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        response = client.get("/api/v1/exams?department=Computer+Science")
        data = response.json()
        assert all(e["department"] == "Computer Science" for e in data["items"])

    def test_filter_by_semester(self, client, test_subject):
        client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Filter Sem",
                "exam_date": "2026-09-28",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        response = client.get("/api/v1/exams?semester=5")
        data = response.json()
        assert all(e["semester"] == 5 for e in data["items"])

    def test_filter_by_date(self, client, test_subject):
        client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Filter Date",
                "exam_date": "2026-09-29",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        response = client.get("/api/v1/exams?exam_date=2026-09-29")
        data = response.json()
        assert all(e["exam_date"] == "2026-09-29" for e in data["items"])

    def test_update_exam(self, client, test_subject):
        create = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Update Original",
                "exam_date": "2026-09-30",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        exam_id = create.json()["id"]

        response = client.patch(
            f"/api/v1/exams/{exam_id}",
            json={"exam_name": "EXAM Update Changed"},
        )
        assert response.status_code == 200
        assert response.json()["exam_name"] == "EXAM Update Changed"

    def test_update_exam_not_found(self, client):
        response = client.patch(
            "/api/v1/exams/999999",
            json={"exam_name": "Updated"},
        )
        assert response.status_code == 404

    def test_duplicate_exam_rejected(self, client, test_subject):
        client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "Dup First",
                "exam_date": "2026-10-01",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "Dup Second",
                "exam_date": "2026-10-01",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        assert response.status_code == 409

    def test_invalid_subject_rejected(self, client):
        response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": 999999,
                "exam_name": "Test Invalid Subject",
                "exam_date": "2026-10-02",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        assert response.status_code == 404

    def test_empty_exam_name_rejected(self, client, test_subject):
        response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "",
                "exam_date": "2026-10-03",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        assert response.status_code == 422

    def test_empty_department_rejected(self, client, test_subject):
        response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "Test Empty Dept",
                "exam_date": "2026-10-04",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "",
            },
        )
        assert response.status_code == 422

    def test_invalid_semester_rejected(self, client, test_subject):
        response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "Test Invalid Sem",
                "exam_date": "2026-10-05",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 9,
                "department": "Computer Science",
            },
        )
        assert response.status_code == 422

    def test_start_time_after_end_time_rejected(self, client, test_subject):
        response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "Test Bad Times",
                "exam_date": "2026-10-06",
                "start_time": "13:00:00",
                "end_time": "10:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        assert response.status_code == 422

    def test_invalid_exam_date_rejected(self, client, test_subject):
        response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "Test Invalid Date",
                "exam_date": "not-a-date",
                "start_time": "10:00",
                "end_time": "13:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        assert response.status_code == 422

    def test_partial_time_update_cannot_invert_exam_range(self, client, test_subject):
        created = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Invalid Partial Time Update",
                "exam_date": "2026-11-05",
                "start_time": "10:00",
                "end_time": "13:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        response = client.patch(
            f"/api/v1/exams/{created.json()['id']}",
            json={"start_time": "14:00"},
        )
        assert response.status_code == 409
        assert "start_time must be before end_time" in response.json()["detail"]

    def test_equal_start_end_time_rejected(self, client, test_subject):
        response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "Test Equal Times",
                "exam_date": "2026-10-07",
                "start_time": "10:00:00",
                "end_time": "10:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        assert response.status_code == 422

    def test_whitespace_trimming(self, client, test_subject):
        response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "  EXAM Trimmed  ",
                "exam_date": "2026-10-08",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "  Computer Science  ",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["exam_name"] == "EXAM Trimmed"
        assert data["department"] == "Computer Science"

    def test_soft_delete(self, client, test_subject):
        create = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Delete Test",
                "exam_date": "2026-10-09",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        exam_id = create.json()["id"]

        response = client.delete(f"/api/v1/exams/{exam_id}")
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_deleted_exam_hidden_from_list(self, client, test_subject):
        create = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Hidden Deleted",
                "exam_date": "2026-10-10",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        exam_id = create.json()["id"]
        client.delete(f"/api/v1/exams/{exam_id}")

        response = client.get("/api/v1/exams")
        data = response.json()
        assert not any(e["id"] == exam_id for e in data["items"])

    def test_deleted_exam_visible_with_include_inactive(self, client, test_subject):
        create = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Visible Deleted",
                "exam_date": "2026-10-11",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        exam_id = create.json()["id"]
        client.delete(f"/api/v1/exams/{exam_id}")

        response = client.get("/api/v1/exams?include_inactive=true")
        data = response.json()
        assert any(e["id"] == exam_id for e in data["items"])

    def test_get_deleted_exam(self, client, test_subject):
        create = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Get Deleted",
                "exam_date": "2026-10-12",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        exam_id = create.json()["id"]
        client.delete(f"/api/v1/exams/{exam_id}")

        response = client.get(f"/api/v1/exams/{exam_id}")
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_delete_nonexistent(self, client):
        response = client.delete("/api/v1/exams/999999")
        assert response.status_code == 404

    def test_missing_required_fields(self, client):
        response = client.post("/api/v1/exams", json={"exam_name": "Test"})
        assert response.status_code == 422

    def test_same_time_different_dates_allowed(self, client, test_subject):
        client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Date 1",
                "exam_date": "2026-10-13",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Date 2",
                "exam_date": "2026-10-14",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        assert response.status_code == 201

    def test_same_date_different_times_allowed(self, client, test_subject):
        client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Time 1",
                "exam_date": "2026-10-15",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        response = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "EXAM Time 2",
                "exam_date": "2026-10-15",
                "start_time": "14:00:00",
                "end_time": "17:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        assert response.status_code == 201

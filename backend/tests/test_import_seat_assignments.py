import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration
from app.models.seat_assignment import SeatAssignment
from app.models.student import Student
from app.models.subject import Subject


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        db.execute(delete(SeatAssignment).where(
            SeatAssignment.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("BSEATSTU%"))
            )
        ))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("BSEATSTU%"))
            )
        ))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("BSEATEXAM%")))
        db.execute(delete(ExamHall).where(ExamHall.building.ilike("BSEATHALL%")))
        db.execute(delete(Subject).where(Subject.code.ilike("BSEATSUB%")))
        db.execute(delete(Student).where(Student.usn.ilike("BSEATSTU%")))
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
def full_setup(client):
    """Create a complete setup: student, subject, exam, hall, registration."""
    student_resp = client.post(
        "/api/v1/students",
        json={"usn": "BSEATSTU01", "name": "Seat Test Student"},
    )
    assert student_resp.status_code == 201
    student = student_resp.json()

    subject_resp = client.post(
        "/api/v1/subjects",
        json={
            "code": "BSEATSUB01",
            "name": "Seat Test Subject",
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
            "exam_name": "BSEATEXAM End Semester",
            "exam_date": "2026-09-15",
            "start_time": "10:00:00",
            "end_time": "13:00:00",
            "semester": 5,
            "department": "Computer Science",
        },
    )
    assert exam_resp.status_code == 201
    exam = exam_resp.json()

    hall_resp = client.post(
        "/api/v1/exam-halls",
        json={
            "building": "BSEATHALL A",
            "room_number": "101",
            "capacity": 5,
            "rows": 2,
            "columns": 3,
        },
    )
    assert hall_resp.status_code == 201
    hall = hall_resp.json()

    reg_resp = client.post(
        "/api/v1/exam-registrations",
        json={
            "student_id": student["id"],
            "exam_id": exam["id"],
        },
    )
    assert reg_resp.status_code == 201
    registration = reg_resp.json()

    return {
        "student": student,
        "subject": subject,
        "exam": exam,
        "hall": hall,
        "registration": registration,
    }


class TestBulkSeatAssignmentAllValid:
    def test_single_assignment(self, client, full_setup):
        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 1
        assert data["assigned"] == 1
        assert data["skipped"] == 0
        assert data["failed"] == 0
        assert data["results"][0]["status"] == "assigned"
        assert data["results"][0]["assignment_id"] is not None
        assert data["results"][0]["error"] is None

    def test_multiple_assignments(self, client, full_setup):
        students = []
        for i in range(2, 5):
            resp = client.post(
                "/api/v1/students",
                json={"usn": f"BSEATSTU{i:02d}", "name": f"Student {i}"},
            )
            assert resp.status_code == 201
            reg_resp = client.post(
                "/api/v1/exam-registrations",
                json={
                    "student_id": resp.json()["id"],
                    "exam_id": full_setup["exam"]["id"],
                },
            )
            assert reg_resp.status_code == 201
            students.append(reg_resp.json())

        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": reg["id"],
                        "seat_number": f"A{i}",
                    }
                    for i, reg in enumerate(students, start=1)
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 3
        assert data["assigned"] == 3

    def test_assignment_with_row_column(self, client, full_setup):
        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "R1-C1",
                        "row_number": 1,
                        "column_number": 1,
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["assigned"] == 1


class TestBulkSeatAssignmentValidation:
    def test_duplicate_seat_in_same_request(self, client, full_setup):
        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                    },
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                    },
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["assigned"] == 1
        assert data["failed"] == 1
        assert "already assigned" in data["results"][1]["error"]

    def test_nonexistent_hall(self, client, full_setup):
        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": 999999,
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["failed"] == 1
        assert "not found" in data["results"][0]["error"]

    def test_inactive_hall(self, client, full_setup):
        client.delete(f"/api/v1/exam-halls/{full_setup['hall']['id']}")

        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["failed"] == 1
        assert "not active" in data["results"][0]["error"]

    def test_nonexistent_registration(self, client, full_setup):
        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": 999999,
                        "seat_number": "A1",
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["failed"] == 1
        assert "not found" in data["results"][0]["error"]

    def test_cancelled_registration(self, client, full_setup):
        client.delete(
            f"/api/v1/exam-registrations/{full_setup['registration']['id']}"
        )

        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["failed"] == 1
        assert "not active" in data["results"][0]["error"]

    def test_registration_already_has_active_seat(self, client, full_setup):
        client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                    }
                ],
            },
        )

        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A2",
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["failed"] == 1
        assert "already has an active seat" in data["results"][0]["error"]

    def test_hall_full(self, client, full_setup):
        small_hall_resp = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "BSEATHALL B",
                "room_number": "201",
                "capacity": 2,
                "rows": 1,
                "columns": 2,
            },
        )
        assert small_hall_resp.status_code == 201
        small_hall = small_hall_resp.json()

        registrations = []
        for i in range(1, 4):
            stu_resp = client.post(
                "/api/v1/students",
                json={"usn": f"BSEATSTU{i+10:02d}", "name": f"Full Hall Student {i}"},
            )
            assert stu_resp.status_code == 201
            reg_resp = client.post(
                "/api/v1/exam-registrations",
                json={
                    "student_id": stu_resp.json()["id"],
                    "exam_id": full_setup["exam"]["id"],
                },
            )
            assert reg_resp.status_code == 201
            registrations.append(reg_resp.json())

        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": small_hall["id"],
                "assignments": [
                    {
                        "exam_registration_id": reg["id"],
                        "seat_number": f"S{i}",
                    }
                    for i, reg in enumerate(registrations, start=1)
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["assigned"] == 2
        assert data["failed"] == 1
        assert "capacity" in data["results"][2]["error"]

    def test_row_exceeds_hall_dimensions(self, client, full_setup):
        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                        "row_number": 99,
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["failed"] == 1
        assert "exceeds" in data["results"][0]["error"]

    def test_column_exceeds_hall_dimensions(self, client, full_setup):
        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                        "column_number": 99,
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["failed"] == 1
        assert "exceeds" in data["results"][0]["error"]


class TestBulkSeatAssignmentMixed:
    def test_mixed_valid_invalid(self, client, full_setup):
        new_student = client.post(
            "/api/v1/students",
            json={"usn": "BSEATSTU20", "name": "Mixed Student"},
        )
        assert new_student.status_code == 201
        new_reg = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": new_student.json()["id"],
                "exam_id": full_setup["exam"]["id"],
            },
        )
        assert new_reg.status_code == 201

        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                    },
                    {
                        "exam_registration_id": new_reg.json()["id"],
                        "seat_number": "A2",
                    },
                    {
                        "exam_registration_id": 999999,
                        "seat_number": "A3",
                    },
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 3
        assert data["assigned"] == 2
        assert data["failed"] == 1

        statuses = [r["status"] for r in data["results"]]
        assert "assigned" in statuses
        assert "failed" in statuses


class TestBulkSeatAssignmentSchemaValidation:
    def test_empty_assignments(self, client, full_setup):
        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [],
            },
        )
        assert response.status_code == 422

    def test_missing_exam_hall_id(self, client):
        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "assignments": [
                    {"exam_registration_id": 1, "seat_number": "A1"}
                ],
            },
        )
        assert response.status_code == 422

    def test_missing_assignments(self, client, full_setup):
        response = client.post(
            "/api/v1/import/seat-assignments",
            json={"exam_hall_id": full_setup["hall"]["id"]},
        )
        assert response.status_code == 422

    def test_assignment_missing_seat_number(self, client, full_setup):
        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [{"exam_registration_id": 1}],
            },
        )
        assert response.status_code == 422


class TestBulkSeatAssignmentCancellation:
    def test_cancel_single(self, client, full_setup):
        assign_resp = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                    }
                ],
            },
        )
        assert assign_resp.status_code == 201
        assignment_id = assign_resp.json()["results"][0]["assignment_id"]

        response = client.post(
            "/api/v1/import/seat-assignments/cancel",
            json={"assignment_ids": [assignment_id]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["cancelled"] == 1
        assert data["results"][0]["status"] == "cancelled"

    def test_cancel_multiple(self, client, full_setup):
        students = []
        for i in range(20, 23):
            resp = client.post(
                "/api/v1/students",
                json={"usn": f"BSEATSTU{i:02d}", "name": f"Cancel Student {i}"},
            )
            assert resp.status_code == 201
            reg_resp = client.post(
                "/api/v1/exam-registrations",
                json={
                    "student_id": resp.json()["id"],
                    "exam_id": full_setup["exam"]["id"],
                },
            )
            assert reg_resp.status_code == 201
            students.append(reg_resp.json())

        assign_resp = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": reg["id"],
                        "seat_number": f"C{i}",
                    }
                    for i, reg in enumerate(students, start=1)
                ],
            },
        )
        assert assign_resp.status_code == 201
        assignment_ids = [r["assignment_id"] for r in assign_resp.json()["results"]]

        response = client.post(
            "/api/v1/import/seat-assignments/cancel",
            json={"assignment_ids": assignment_ids},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["cancelled"] == 3

    def test_cancel_nonexistent(self, client):
        response = client.post(
            "/api/v1/import/seat-assignments/cancel",
            json={"assignment_ids": [999999]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["failed"] == 1
        assert "not found" in data["results"][0]["error"]

    def test_cancel_already_cancelled(self, client, full_setup):
        assign_resp = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                    }
                ],
            },
        )
        assert assign_resp.status_code == 201
        assignment_id = assign_resp.json()["results"][0]["assignment_id"]

        client.post(
            "/api/v1/import/seat-assignments/cancel",
            json={"assignment_ids": [assignment_id]},
        )

        response = client.post(
            "/api/v1/import/seat-assignments/cancel",
            json={"assignment_ids": [assignment_id]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["skipped"] == 1
        assert "already cancelled" in data["results"][0]["error"]

    def test_cancel_mixed_valid_notfound(self, client, full_setup):
        assign_resp = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                    }
                ],
            },
        )
        assert assign_resp.status_code == 201
        assignment_id = assign_resp.json()["results"][0]["assignment_id"]

        response = client.post(
            "/api/v1/import/seat-assignments/cancel",
            json={"assignment_ids": [assignment_id, 999999]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["cancelled"] == 1
        assert data["failed"] == 1

    def test_cancel_schema_validation(self, client):
        response = client.post(
            "/api/v1/import/seat-assignments/cancel",
            json={"assignment_ids": []},
        )
        assert response.status_code == 422


class TestBulkSeatAssignmentDatabaseSafety:
    def test_no_raw_db_errors(self, client, full_setup):
        client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                    }
                ],
            },
        )

        new_student = client.post(
            "/api/v1/students",
            json={"usn": "BSEATSTU30", "name": "Dup Seat Student"},
        )
        assert new_student.status_code == 201
        new_reg = client.post(
            "/api/v1/exam-registrations",
            json={
                "student_id": new_student.json()["id"],
                "exam_id": full_setup["exam"]["id"],
            },
        )
        assert new_reg.status_code == 201

        response = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": new_reg.json()["id"],
                        "seat_number": "A1",
                    }
                ],
            },
        )
        assert response.status_code == 201
        for result in response.json()["results"]:
            if result["error"]:
                assert "unique" not in result["error"].lower()
                assert "constraint" not in result["error"].lower()
                assert "integrity" not in result["error"].lower()

    def test_assignment_not_hard_deleted(self, client, full_setup):
        assign_resp = client.post(
            "/api/v1/import/seat-assignments",
            json={
                "exam_hall_id": full_setup["hall"]["id"],
                "assignments": [
                    {
                        "exam_registration_id": full_setup["registration"]["id"],
                        "seat_number": "A1",
                    }
                ],
            },
        )
        assert assign_resp.status_code == 201
        assignment_id = assign_resp.json()["results"][0]["assignment_id"]

        client.post(
            "/api/v1/import/seat-assignments/cancel",
            json={"assignment_ids": [assignment_id]},
        )

        get_resp = client.get(f"/api/v1/seat-assignments/{assignment_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "CANCELLED"

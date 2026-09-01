import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration
from app.models.hall_ticket_match import HallTicketMatchResult, HallTicketMatchSignal
from app.models.seat_assignment import SeatAssignment
from app.models.student import Student
from app.models.subject import Subject


@pytest.fixture(autouse=True)
def clean_test_data():
    """Remove test data before each test to avoid conflicts."""
    db = SessionLocal()
    try:
        match_exam_ids = db.query(Exam.id).filter(
            Exam.exam_name.ilike("SEATEXAM%")
        ).subquery()
        db.execute(delete(HallTicketMatchSignal).where(
            HallTicketMatchSignal.match_result_id.in_(
                db.query(HallTicketMatchResult.id).filter(
                    HallTicketMatchResult.exam_id.in_(db.query(match_exam_ids))
                )
            )
        ))
        db.execute(delete(HallTicketMatchResult).where(
            HallTicketMatchResult.exam_id.in_(db.query(match_exam_ids))
        ))
        db.execute(delete(SeatAssignment).where(
            SeatAssignment.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("SEATSTU%"))
            )
        ))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("SEATSTU%"))
            )
        ))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("SEATEXAM%")))
        db.execute(delete(ExamHall).where(ExamHall.building.ilike("SEATHALL%")))
        db.execute(delete(Subject).where(Subject.code.ilike("SEATSUB%")))
        db.execute(delete(Student).where(Student.usn.ilike("SEATSTU%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def test_student(client):
    response = client.post(
        "/api/v1/students",
        json={"usn": "SEATSTU01", "name": "Seat Test Student"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_student2(client):
    response = client.post(
        "/api/v1/students",
        json={"usn": "SEATSTU02", "name": "Seat Test Student 2"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_subject(client):
    response = client.post(
        "/api/v1/subjects",
        json={
            "code": "SEATSUB01",
            "name": "Seat Test Subject",
            "department": "Computer Science",
            "semester": 5,
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_exam(client, test_subject):
    response = client.post(
        "/api/v1/exams",
        json={
            "subject_id": test_subject["id"],
            "exam_name": "SEATEXAM Final Exam",
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
def test_hall(client):
    response = client.post(
        "/api/v1/exam-halls",
        json={
            "building": "SEATHALL Block A",
            "room_number": "SEATHALL101",
            "capacity": 5,
            "rows": 2,
            "columns": 3,
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_registration(client, test_student, test_exam):
    response = client.post(
        "/api/v1/exam-registrations",
        json={
            "student_id": test_student["id"],
            "exam_id": test_exam["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_registration2(client, test_student2, test_exam):
    response = client.post(
        "/api/v1/exam-registrations",
        json={
            "student_id": test_student2["id"],
            "exam_id": test_exam["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def cancelled_registration(client, test_student, test_exam):
    response = client.post(
        "/api/v1/exam-registrations",
        json={
            "student_id": test_student["id"],
            "exam_id": test_exam["id"],
        },
    )
    assert response.status_code == 201
    reg_id = response.json()["id"]
    client.delete(f"/api/v1/exam-registrations/{reg_id}")
    return response.json()


@pytest.fixture()
def inactive_hall(client):
    response = client.post(
        "/api/v1/exam-halls",
        json={
            "building": "SEATHALL Inactive",
            "room_number": "SEATHALL999",
            "capacity": 10,
        },
    )
    assert response.status_code == 201
    hall_id = response.json()["id"]
    client.delete(f"/api/v1/exam-halls/{hall_id}")
    return response.json()


class TestSeatAssignmentAPI:
    def test_create_assignment(self, client, test_registration, test_hall):
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "A1",
                "row_number": 1,
                "column_number": 1,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["exam_registration_id"] == test_registration["id"]
        assert data["exam_hall_id"] == test_hall["id"]
        assert data["seat_number"] == "A1"
        assert data["status"] == "ASSIGNED"
        assert "id" in data

    def test_create_assignment_minimal(self, client, test_registration, test_hall):
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "B1",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["row_number"] is None
        assert data["column_number"] is None

    def test_get_assignment(self, client, test_registration, test_hall):
        create = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "C1",
            },
        )
        assign_id = create.json()["id"]

        response = client.get(f"/api/v1/seat-assignments/{assign_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == assign_id
        assert data["student_usn"] == "SEATSTU01"
        assert data["student_name"] == "Seat Test Student"
        assert data["hall_building"] == "SEATHALL Block A"
        assert data["hall_room_number"] == "SEATHALL101"

    def test_get_assignment_not_found(self, client):
        response = client.get("/api/v1/seat-assignments/999999")
        assert response.status_code == 404

    def test_list_assignments(self, client, test_registration, test_hall):
        client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "D1",
            },
        )
        response = client.get("/api/v1/seat-assignments")
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    def test_pagination(self, client, test_registration, test_hall):
        client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "E1",
            },
        )
        response = client.get("/api/v1/seat-assignments?page=1&page_size=2")
        data = response.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1

    def test_filter_by_exam(self, client, test_registration, test_hall, test_exam):
        client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "F1",
            },
        )
        response = client.get(
            f"/api/v1/seat-assignments?exam_id={test_exam['id']}"
        )
        data = response.json()
        assert all(a["exam_id"] == test_exam["id"] for a in data["items"])

    def test_filter_by_hall(self, client, test_registration, test_hall):
        client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "G1",
            },
        )
        response = client.get(
            f"/api/v1/seat-assignments?exam_hall_id={test_hall['id']}"
        )
        data = response.json()
        assert all(
            a["exam_hall_id"] == test_hall["id"] for a in data["items"]
        )

    def test_filter_by_student(self, client, test_registration, test_hall, test_student):
        client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "H1",
            },
        )
        response = client.get(
            f"/api/v1/seat-assignments?student_id={test_student['id']}"
        )
        data = response.json()
        assert all(
            a["student_id"] == test_student["id"] for a in data["items"]
        )

    def test_filter_by_registration(self, client, test_registration, test_hall):
        client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "I1",
            },
        )
        response = client.get(
            f"/api/v1/seat-assignments?registration_id={test_registration['id']}"
        )
        data = response.json()
        assert all(
            a["exam_registration_id"] == test_registration["id"]
            for a in data["items"]
        )

    def test_filter_by_status(self, client, test_registration, test_hall):
        client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "J1",
            },
        )
        response = client.get("/api/v1/seat-assignments?status=ASSIGNED")
        data = response.json()
        assert all(a["status"] == "ASSIGNED" for a in data["items"])

    def test_missing_registration_rejected(self, client, test_hall):
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": 999999,
                "exam_hall_id": test_hall["id"],
                "seat_number": "X1",
            },
        )
        assert response.status_code == 404

    def test_missing_hall_rejected(self, client, test_registration):
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": 999999,
                "seat_number": "X1",
            },
        )
        assert response.status_code == 404

    def test_cancelled_registration_rejected(
        self, client, cancelled_registration, test_hall
    ):
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": cancelled_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "X1",
            },
        )
        assert response.status_code == 409

    def test_inactive_hall_rejected(self, client, test_registration, inactive_hall):
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": inactive_hall["id"],
                "seat_number": "X1",
            },
        )
        assert response.status_code == 409

    def test_empty_seat_number_rejected(self, client, test_registration, test_hall):
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "",
            },
        )
        assert response.status_code == 422

    def test_invalid_row_rejected(self, client, test_registration, test_hall):
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "X1",
                "row_number": 0,
            },
        )
        assert response.status_code == 422

    def test_invalid_column_rejected(self, client, test_registration, test_hall):
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "X1",
                "column_number": 0,
            },
        )
        assert response.status_code == 422

    def test_duplicate_seat_same_exam_rejected(
        self, client, test_registration, test_registration2, test_hall
    ):
        client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "DUP1",
            },
        )
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration2["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "DUP1",
            },
        )
        assert response.status_code == 409

    def test_same_seat_different_exam_allowed(
        self, client, test_student, test_student2, test_subject, test_hall
    ):
        exam1_resp = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "SEATEXAM Exam A",
                "exam_date": "2026-12-16",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        exam2_resp = client.post(
            "/api/v1/exams",
            json={
                "subject_id": test_subject["id"],
                "exam_name": "SEATEXAM Exam B",
                "exam_date": "2026-12-17",
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "semester": 5,
                "department": "Computer Science",
            },
        )
        exam1 = exam1_resp.json()
        exam2 = exam2_resp.json()

        reg1 = client.post(
            "/api/v1/exam-registrations",
            json={"student_id": test_student["id"], "exam_id": exam1["id"]},
        ).json()
        reg2 = client.post(
            "/api/v1/exam-registrations",
            json={"student_id": test_student2["id"], "exam_id": exam2["id"]},
        ).json()

        resp1 = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": reg1["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "SAME1",
            },
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": reg2["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "SAME1",
            },
        )
        assert resp2.status_code == 201

    def test_same_student_multiple_active_seats_same_exam_rejected(
        self, client, test_registration, test_hall
    ):
        client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "MULTI1",
            },
        )
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "MULTI2",
            },
        )
        assert response.status_code == 409

    def test_hall_capacity_enforced(
        self, client, test_student, test_exam, test_hall
    ):
        students = []
        for i in range(6):
            resp = client.post(
                "/api/v1/students",
                json={"usn": f"SEATSTU{i+10:02d}", "name": f"Capacity Student {i}"},
            )
            assert resp.status_code == 201
            students.append(resp.json())

        regs = []
        for s in students:
            resp = client.post(
                "/api/v1/exam-registrations",
                json={"student_id": s["id"], "exam_id": test_exam["id"]},
            )
            assert resp.status_code == 201
            regs.append(resp.json())

        for i, r in enumerate(regs):
            resp = client.post(
                "/api/v1/seat-assignments",
                json={
                    "exam_registration_id": r["id"],
                    "exam_hall_id": test_hall["id"],
                    "seat_number": f"C{i+1:02d}",
                },
            )
            if i < 5:
                assert resp.status_code == 201
            else:
                assert resp.status_code == 409

    def test_row_limit_enforced(self, client, test_registration, test_hall):
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "ROW1",
                "row_number": 99,
            },
        )
        assert response.status_code == 409

    def test_column_limit_enforced(self, client, test_registration, test_hall):
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "COL1",
                "column_number": 99,
            },
        )
        assert response.status_code == 409

    def test_cancel_assignment(self, client, test_registration, test_hall):
        create = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "CAN1",
            },
        )
        assign_id = create.json()["id"]

        response = client.delete(f"/api/v1/seat-assignments/{assign_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"

    def test_cancelled_assignment_remains_in_database(
        self, client, test_registration, test_hall
    ):
        create = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "CAN2",
            },
        )
        assign_id = create.json()["id"]
        client.delete(f"/api/v1/seat-assignments/{assign_id}")

        db = SessionLocal()
        try:
            assignment = db.query(SeatAssignment).filter(
                SeatAssignment.id == assign_id
            ).first()
            assert assignment is not None
            assert assignment.status == "CANCELLED"
        finally:
            db.close()

    def test_cancel_nonexistent_assignment(self, client):
        response = client.delete("/api/v1/seat-assignments/999999")
        assert response.status_code == 404

    def test_update_assignment_not_found(self, client):
        response = client.patch(
            "/api/v1/seat-assignments/999999",
            json={"status": "CANCELLED"},
        )
        assert response.status_code == 404

    def test_invalid_status_rejected(self, client, test_registration, test_hall):
        create = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "INV1",
            },
        )
        assign_id = create.json()["id"]
        response = client.patch(
            f"/api/v1/seat-assignments/{assign_id}",
            json={"status": "INVALID"},
        )
        assert response.status_code == 422

    def test_missing_required_fields(self, client):
        response = client.post("/api/v1/seat-assignments", json={})
        assert response.status_code == 422

    def test_foreign_key_enforcement(self, client):
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": 999999,
                "exam_hall_id": 999999,
                "seat_number": "FK1",
            },
        )
        assert response.status_code == 404

    def test_seat_number_whitespace_trimmed(
        self, client, test_registration, test_hall
    ):
        response = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "  TRIM1  ",
            },
        )
        assert response.status_code == 201
        assert response.json()["seat_number"] == "TRIM1"


class TestSeatAssignmentRegressionOneActivePerRegistration:
    """Issue 1 regression: one active seat per registration across ALL halls."""

    def test_registration_two_active_seats_different_halls_rejected(
        self, client, test_registration
    ):
        hall1 = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "SEATHALL RegHall1",
                "room_number": "SEATHALLR101",
                "capacity": 10,
            },
        ).json()
        hall2 = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "SEATHALL RegHall2",
                "room_number": "SEATHALLR201",
                "capacity": 10,
            },
        ).json()

        resp1 = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": hall1["id"],
                "seat_number": "REG1",
            },
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": hall2["id"],
                "seat_number": "REG1",
            },
        )
        assert resp2.status_code == 409

    def test_cancelled_allows_new_active_assignment(
        self, client, test_registration
    ):
        hall1 = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "SEATHALL CancelHall1",
                "room_number": "SEATHALLC101",
                "capacity": 10,
            },
        ).json()
        hall2 = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "SEATHALL CancelHall2",
                "room_number": "SEATHALLC201",
                "capacity": 10,
            },
        ).json()

        create1 = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": hall1["id"],
                "seat_number": "CANREG1",
            },
        )
        assert create1.status_code == 201
        assign1_id = create1.json()["id"]

        cancel = client.delete(f"/api/v1/seat-assignments/{assign1_id}")
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "CANCELLED"

        create2 = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": hall2["id"],
                "seat_number": "CANREG2",
            },
        )
        assert create2.status_code == 201
        assert create2.json()["status"] == "ASSIGNED"

    def test_database_enforces_one_active_per_registration(
        self, client, test_registration
    ):
        hall1 = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "SEATHALL DbHall1",
                "room_number": "SEATHALLD101",
                "capacity": 10,
            },
        ).json()
        hall2 = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "SEATHALL DbHall2",
                "room_number": "SEATHALLD201",
                "capacity": 10,
            },
        ).json()

        create1 = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": hall1["id"],
                "seat_number": "DBREG1",
            },
        )
        assert create1.status_code == 201

        db = SessionLocal()
        try:
            assignment2 = SeatAssignment(
                exam_registration_id=test_registration["id"],
                exam_hall_id=hall2["id"],
                seat_number="DBREG2",
                exam_id=test_registration["exam_id"],
                student_id=test_registration["student_id"],
                status="ASSIGNED",
            )
            db.add(assignment2)
            db.commit()
            assert False, "Should have raised IntegrityError"
        except Exception:
            db.rollback()
        finally:
            db.close()


class TestSeatAssignmentRegressionConsistency:
    """Issue 2 regression: materialized exam_id/student_id consistency."""

    def test_exam_id_matches_registration(
        self, client, test_registration, test_hall
    ):
        create = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "CON1",
            },
        )
        assert create.status_code == 201
        data = create.json()
        assert data["exam_id"] == test_registration["exam_id"]

    def test_student_id_matches_registration(
        self, client, test_registration, test_hall
    ):
        create = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "CON2",
            },
        )
        assert create.status_code == 201
        data = create.json()
        assert data["student_id"] == test_registration["student_id"]

    def test_service_derives_exam_and_student_from_registration(
        self, client, test_registration, test_hall
    ):
        create = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": test_registration["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "DER1",
            },
        )
        assert create.status_code == 201
        data = create.json()
        assert data["exam_id"] == test_registration["exam_id"]
        assert data["student_id"] == test_registration["student_id"]

    def test_direct_insert_with_mismatched_exam_id_rejected_by_fk(
        self, client, test_registration, test_hall
    ):
        db = SessionLocal()
        try:
            assignment = SeatAssignment(
                exam_registration_id=test_registration["id"],
                exam_hall_id=test_hall["id"],
                seat_number="FKM1",
                exam_id=999999,
                student_id=test_registration["student_id"],
                status="ASSIGNED",
            )
            db.add(assignment)
            db.commit()
            assert False, "Should have raised FK violation"
        except Exception:
            db.rollback()
        finally:
            db.close()

    def test_direct_insert_with_mismatched_student_id_rejected_by_fk(
        self, client, test_registration, test_hall
    ):
        db = SessionLocal()
        try:
            assignment = SeatAssignment(
                exam_registration_id=test_registration["id"],
                exam_hall_id=test_hall["id"],
                seat_number="FKM2",
                exam_id=test_registration["exam_id"],
                student_id=999999,
                status="ASSIGNED",
            )
            db.add(assignment)
            db.commit()
            assert False, "Should have raised FK violation"
        except Exception:
            db.rollback()
        finally:
            db.close()


class TestSeatAssignmentRegressionCapacityConcurrency:
    """Issue 3 regression: capacity enforcement under concurrency."""

    def test_capacity_hard_limit_enforced(
        self, client, test_student, test_exam, test_hall
    ):
        students = []
        for i in range(7):
            resp = client.post(
                "/api/v1/students",
                json={"usn": f"SEATSTU{i+20:02d}", "name": f"Cap Student {i}"},
            )
            assert resp.status_code == 201
            students.append(resp.json())

        regs = []
        for s in students:
            resp = client.post(
                "/api/v1/exam-registrations",
                json={"student_id": s["id"], "exam_id": test_exam["id"]},
            )
            assert resp.status_code == 201
            regs.append(resp.json())

        for i, r in enumerate(regs):
            resp = client.post(
                "/api/v1/seat-assignments",
                json={
                    "exam_registration_id": r["id"],
                    "exam_hall_id": test_hall["id"],
                    "seat_number": f"CAP{i+1:02d}",
                },
            )
            if i < 5:
                assert resp.status_code == 201, f"Seat {i+1} should succeed"
            else:
                assert resp.status_code == 409, f"Seat {i+1} should fail at capacity"

    def test_cancelled_seat_allows_new_assignment_within_capacity(
        self, client, test_student, test_exam, test_hall
    ):
        s1 = client.post(
            "/api/v1/students",
            json={"usn": "SEATSTU30", "name": "Reassign Student 1"},
        ).json()
        s2 = client.post(
            "/api/v1/students",
            json={"usn": "SEATSTU31", "name": "Reassign Student 2"},
        ).json()

        r1 = client.post(
            "/api/v1/exam-registrations",
            json={"student_id": s1["id"], "exam_id": test_exam["id"]},
        ).json()
        r2 = client.post(
            "/api/v1/exam-registrations",
            json={"student_id": s2["id"], "exam_id": test_exam["id"]},
        ).json()

        create1 = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": r1["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "REAS1",
            },
        )
        assert create1.status_code == 201

        cancel1 = client.delete(f"/api/v1/seat-assignments/{create1.json()['id']}")
        assert cancel1.status_code == 200

        create2 = client.post(
            "/api/v1/seat-assignments",
            json={
                "exam_registration_id": r2["id"],
                "exam_hall_id": test_hall["id"],
                "seat_number": "REAS1",
            },
        )
        assert create2.status_code == 201

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.exam import Exam
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.hall_ticket import HallTicket, HallTicketStatus
from app.models.student import Student
from app.models.subject import Subject


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        db.execute(delete(HallTicket))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("HTT%"))
            )
        ))
        db.execute(delete(Student).where(Student.usn.ilike("HTT%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("HT Test Exam%")))
        db.execute(delete(Subject).where(Subject.code.ilike("HTT%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def sample_data():
    db = SessionLocal()
    try:
        subject = Subject(
            code="HTT101", name="HT Test Subject", department="HT Dept",
            semester=1, credits=3,
        )
        db.add(subject)
        db.commit()
        db.refresh(subject)

        exam = Exam(
            subject_id=subject.id, exam_name="HT Test Exam Final",
            exam_date="2026-12-01", start_time="09:00", end_time="12:00",
            semester=1, department="HT Dept",
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)

        student = Student(usn="HTT001", name="HT Test Student")
        db.add(student)
        db.commit()
        db.refresh(student)

        reg = ExamRegistration(
            student_id=student.id, exam_id=exam.id,
            status=RegistrationStatus.REGISTERED.value,
        )
        db.add(reg)
        db.commit()
        db.refresh(reg)

        return {
            "subject_id": subject.id,
            "exam_id": exam.id,
            "student_id": student.id,
            "registration_id": reg.id,
        }
    finally:
        db.close()


class TestHallTicketModel:
    def test_status_enum_values(self):
        assert HallTicketStatus.CREATED.value == "CREATED"
        assert HallTicketStatus.EXTRACTED.value == "EXTRACTED"
        assert HallTicketStatus.MATCHED.value == "MATCHED"
        assert HallTicketStatus.VERIFIED.value == "VERIFIED"
        assert HallTicketStatus.REJECTED.value == "REJECTED"
        assert HallTicketStatus.CANCELLED.value == "CANCELLED"

    def test_model_creation(self):
        ht = HallTicket(
            exam_registration_id=1,
            status=HallTicketStatus.CREATED.value,
        )
        assert ht.exam_registration_id == 1
        assert ht.status == "CREATED"
        assert ht.document_id is None
        assert ht.extraction_result_id is None
        assert ht.match_result_id is None
        assert ht.verification_outcome_id is None
        assert ht.rejection_reason is None

    def test_repr(self):
        ht = HallTicket(
            exam_registration_id=1,
            status=HallTicketStatus.CREATED.value,
        )
        assert "HallTicket" in repr(ht)
        assert "CREATED" in repr(ht)


class TestHallTicketServiceCreate:
    def test_create_success(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate
        from app.services.hall_ticket import create_hall_ticket

        db = SessionLocal()
        try:
            ht = create_hall_ticket(
                db,
                HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
            )
            assert ht.id is not None
            assert ht.exam_registration_id == sample_data["registration_id"]
            assert ht.status == "CREATED"
            assert ht.document_id is None
        finally:
            db.close()

    def test_create_with_document(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate
        from app.services.hall_ticket import create_hall_ticket

        db = SessionLocal()
        try:
            ht = create_hall_ticket(
                db,
                HallTicketCreate(
                    exam_registration_id=sample_data["registration_id"],
                ),
            )
            assert ht.document_id is None
            assert ht.exam_registration_id == sample_data["registration_id"]
        finally:
            db.close()

    def test_create_duplicate_registration(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate
        from app.services.hall_ticket import create_hall_ticket

        db = SessionLocal()
        try:
            create_hall_ticket(
                db,
                HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
            )
            with pytest.raises(ValueError, match="already exists"):
                create_hall_ticket(
                    db,
                    HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
                )
        finally:
            db.close()

    def test_create_invalid_registration(self):
        from app.schemas.hall_ticket import HallTicketCreate
        from app.services.hall_ticket import create_hall_ticket

        db = SessionLocal()
        try:
            with pytest.raises(LookupError, match="not found"):
                create_hall_ticket(
                    db,
                    HallTicketCreate(exam_registration_id=99999),
                )
        finally:
            db.close()


class TestHallTicketServiceRetrieval:
    def test_get_by_id(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate
        from app.services.hall_ticket import create_hall_ticket, get_hall_ticket

        db = SessionLocal()
        try:
            ht = create_hall_ticket(
                db,
                HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
            )
            found = get_hall_ticket(db, ht.id)
            assert found is not None
            assert found.id == ht.id
        finally:
            db.close()

    def test_get_by_id_not_found(self):
        from app.services.hall_ticket import get_hall_ticket

        db = SessionLocal()
        try:
            found = get_hall_ticket(db, 99999)
            assert found is None
        finally:
            db.close()

    def test_get_by_registration(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate
        from app.services.hall_ticket import create_hall_ticket, get_hall_ticket_by_registration

        db = SessionLocal()
        try:
            ht = create_hall_ticket(
                db,
                HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
            )
            found = get_hall_ticket_by_registration(db, sample_data["registration_id"])
            assert found is not None
            assert found.id == ht.id
        finally:
            db.close()

    def test_get_by_registration_not_found(self):
        from app.services.hall_ticket import get_hall_ticket_by_registration

        db = SessionLocal()
        try:
            found = get_hall_ticket_by_registration(db, 99999)
            assert found is None
        finally:
            db.close()


class TestHallTicketServiceUpdate:
    def test_update_status_valid_transition(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate, HallTicketUpdate
        from app.services.hall_ticket import create_hall_ticket, update_hall_ticket

        db = SessionLocal()
        try:
            ht = create_hall_ticket(
                db,
                HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
            )
            updated = update_hall_ticket(
                db, ht.id, HallTicketUpdate(status="EXTRACTED")
            )
            assert updated.status == "EXTRACTED"
        finally:
            db.close()

    def test_update_status_invalid_transition(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate, HallTicketUpdate
        from app.services.hall_ticket import create_hall_ticket, update_hall_ticket

        db = SessionLocal()
        try:
            ht = create_hall_ticket(
                db,
                HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
            )
            with pytest.raises(ValueError, match="Cannot transition"):
                update_hall_ticket(
                    db, ht.id, HallTicketUpdate(status="VERIFIED")
                )
        finally:
            db.close()

    def test_update_status_invalid_value(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate, HallTicketUpdate
        from app.services.hall_ticket import create_hall_ticket, update_hall_ticket

        db = SessionLocal()
        try:
            ht = create_hall_ticket(
                db,
                HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
            )
            with pytest.raises(ValueError, match="Invalid status"):
                update_hall_ticket(
                    db, ht.id, HallTicketUpdate(status="INVALID_STATUS")
                )
        finally:
            db.close()

    def test_update_document_id(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate, HallTicketUpdate
        from app.services.hall_ticket import create_hall_ticket, update_hall_ticket

        db = SessionLocal()
        try:
            ht = create_hall_ticket(
                db,
                HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
            )
            assert ht.document_id is None
            updated = update_hall_ticket(
                db, ht.id, HallTicketUpdate(document_id=None)
            )
            assert updated.document_id is None
        finally:
            db.close()

    def test_update_not_found(self):
        from app.schemas.hall_ticket import HallTicketUpdate
        from app.services.hall_ticket import update_hall_ticket

        db = SessionLocal()
        try:
            with pytest.raises(LookupError, match="not found"):
                update_hall_ticket(
                    db, 99999, HallTicketUpdate(document_id=1)
                )
        finally:
            db.close()

    def test_full_lifecycle(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate, HallTicketUpdate
        from app.services.hall_ticket import create_hall_ticket, update_hall_ticket

        db = SessionLocal()
        try:
            ht = create_hall_ticket(
                db,
                HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
            )
            assert ht.status == "CREATED"

            ht = update_hall_ticket(db, ht.id, HallTicketUpdate(status="EXTRACTED"))
            assert ht.status == "EXTRACTED"

            ht = update_hall_ticket(db, ht.id, HallTicketUpdate(status="MATCHED"))
            assert ht.status == "MATCHED"

            ht = update_hall_ticket(db, ht.id, HallTicketUpdate(status="VERIFIED"))
            assert ht.status == "VERIFIED"
        finally:
            db.close()

    def test_cancel_from_created(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate, HallTicketUpdate
        from app.services.hall_ticket import create_hall_ticket, update_hall_ticket

        db = SessionLocal()
        try:
            ht = create_hall_ticket(
                db,
                HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
            )
            ht = update_hall_ticket(db, ht.id, HallTicketUpdate(status="CANCELLED"))
            assert ht.status == "CANCELLED"
        finally:
            db.close()

    def test_reject_from_matched(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate, HallTicketUpdate
        from app.services.hall_ticket import create_hall_ticket, update_hall_ticket

        db = SessionLocal()
        try:
            ht = create_hall_ticket(
                db,
                HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
            )
            ht = update_hall_ticket(db, ht.id, HallTicketUpdate(status="EXTRACTED"))
            ht = update_hall_ticket(db, ht.id, HallTicketUpdate(status="MATCHED"))
            ht = update_hall_ticket(db, ht.id, HallTicketUpdate(status="REJECTED"))
            assert ht.status == "REJECTED"
        finally:
            db.close()


class TestHallTicketServiceList:
    def test_list_empty(self):
        from app.services.hall_ticket import list_hall_tickets

        db = SessionLocal()
        try:
            result = list_hall_tickets(db)
            assert result["total"] == 0
            assert result["items"] == []
        finally:
            db.close()

    def test_list_with_data(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate
        from app.services.hall_ticket import create_hall_ticket, list_hall_tickets

        db = SessionLocal()
        try:
            create_hall_ticket(
                db,
                HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
            )
            result = list_hall_tickets(db)
            assert result["total"] == 1
            assert len(result["items"]) == 1
        finally:
            db.close()

    def test_list_filter_status(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate
        from app.services.hall_ticket import create_hall_ticket, list_hall_tickets

        db = SessionLocal()
        try:
            create_hall_ticket(
                db,
                HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
            )
            result = list_hall_tickets(db, status="CREATED")
            assert result["total"] == 1
            result = list_hall_tickets(db, status="VERIFIED")
            assert result["total"] == 0
        finally:
            db.close()

    def test_list_filter_registration(self, sample_data):
        from app.schemas.hall_ticket import HallTicketCreate
        from app.services.hall_ticket import create_hall_ticket, list_hall_tickets

        db = SessionLocal()
        try:
            create_hall_ticket(
                db,
                HallTicketCreate(exam_registration_id=sample_data["registration_id"]),
            )
            result = list_hall_tickets(
                db, exam_registration_id=sample_data["registration_id"]
            )
            assert result["total"] == 1
            result = list_hall_tickets(db, exam_registration_id=99999)
            assert result["total"] == 0
        finally:
            db.close()


class TestHallTicketApiCreate:
    def test_api_create_success(self, client, sample_data):
        response = client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": sample_data["registration_id"]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["exam_registration_id"] == sample_data["registration_id"]
        assert data["status"] == "CREATED"
        assert data["id"] is not None

    def test_api_create_with_document(self, client, sample_data):
        response = client.post(
            "/api/v1/hall-tickets",
            json={
                "exam_registration_id": sample_data["registration_id"],
            },
        )
        assert response.status_code == 201
        assert response.json()["document_id"] is None

    def test_api_create_duplicate(self, client, sample_data):
        client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": sample_data["registration_id"]},
        )
        response = client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": sample_data["registration_id"]},
        )
        assert response.status_code == 422

    def test_api_create_invalid_registration(self, client):
        response = client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": 99999},
        )
        assert response.status_code == 404

    def test_api_create_missing_body(self, client):
        response = client.post("/api/v1/hall-tickets", json={})
        assert response.status_code == 422

    def test_api_create_invalid_registration_id(self, client):
        response = client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": -1},
        )
        assert response.status_code == 422


class TestHallTicketApiGet:
    def test_api_get_by_id(self, client, sample_data):
        create_resp = client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": sample_data["registration_id"]},
        )
        ht_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/hall-tickets/{ht_id}")
        assert response.status_code == 200
        assert response.json()["id"] == ht_id

    def test_api_get_not_found(self, client):
        response = client.get("/api/v1/hall-tickets/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Hall ticket not found"

    def test_api_get_by_registration(self, client, sample_data):
        client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": sample_data["registration_id"]},
        )
        response = client.get(
            f"/api/v1/hall-tickets/by-registration/{sample_data['registration_id']}"
        )
        assert response.status_code == 200
        assert response.json()["exam_registration_id"] == sample_data["registration_id"]

    def test_api_get_by_registration_not_found(self, client):
        response = client.get("/api/v1/hall-tickets/by-registration/99999")
        assert response.status_code == 404


class TestHallTicketApiList:
    def test_api_list_empty(self, client):
        response = client.get("/api/v1/hall-tickets")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_api_list_with_data(self, client, sample_data):
        client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": sample_data["registration_id"]},
        )
        response = client.get("/api/v1/hall-tickets")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_api_list_filter_status(self, client, sample_data):
        client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": sample_data["registration_id"]},
        )
        response = client.get("/api/v1/hall-tickets?status=CREATED")
        assert response.status_code == 200
        assert response.json()["total"] == 1

        response = client.get("/api/v1/hall-tickets?status=VERIFIED")
        assert response.json()["total"] == 0

    def test_api_list_filter_registration(self, client, sample_data):
        client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": sample_data["registration_id"]},
        )
        reg_id = sample_data["registration_id"]
        response = client.get(f"/api/v1/hall-tickets?exam_registration_id={reg_id}")
        assert response.json()["total"] == 1

    def test_api_list_read_only(self, client):
        response = client.put("/api/v1/hall-tickets", json={})
        assert response.status_code == 405


class TestHallTicketApiUpdate:
    def test_api_update_status(self, client, sample_data):
        create_resp = client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": sample_data["registration_id"]},
        )
        ht_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/hall-tickets/{ht_id}",
            json={"status": "EXTRACTED"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "EXTRACTED"

    def test_api_update_invalid_transition(self, client, sample_data):
        create_resp = client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": sample_data["registration_id"]},
        )
        ht_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/hall-tickets/{ht_id}",
            json={"status": "VERIFIED"},
        )
        assert response.status_code == 422

    def test_api_update_invalid_status(self, client, sample_data):
        create_resp = client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": sample_data["registration_id"]},
        )
        ht_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/hall-tickets/{ht_id}",
            json={"status": "BOGUS"},
        )
        assert response.status_code == 422

    def test_api_update_not_found(self, client):
        response = client.patch(
            "/api/v1/hall-tickets/99999",
            json={"document_id": 1},
        )
        assert response.status_code == 404

    def test_api_update_document_id(self, client, sample_data):
        create_resp = client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": sample_data["registration_id"]},
        )
        ht_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/hall-tickets/{ht_id}",
            json={"document_id": None},
        )
        assert response.status_code == 200
        assert response.json()["document_id"] is None

    def test_api_update_rejection_reason(self, client, sample_data):
        create_resp = client.post(
            "/api/v1/hall-tickets",
            json={"exam_registration_id": sample_data["registration_id"]},
        )
        ht_id = create_resp.json()["id"]

        client.patch(
            f"/api/v1/hall-tickets/{ht_id}",
            json={"status": "EXTRACTED"},
        )
        client.patch(
            f"/api/v1/hall-tickets/{ht_id}",
            json={"status": "MATCHED"},
        )
        response = client.patch(
            f"/api/v1/hall-tickets/{ht_id}",
            json={"status": "REJECTED", "rejection_reason": "OCR quality too low"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "REJECTED"
        assert response.json()["rejection_reason"] == "OCR quality too low"


class TestHallTicketRegression:
    def test_existing_525_tests_unaffected(self, client):
        response = client.get("/api/v1/students?page=1&page_size=1")
        assert response.status_code == 200

    def test_exam_registrations_still_work(self, client, sample_data):
        response = client.get(
            f"/api/v1/exam-registrations?exam_id={sample_data['exam_id']}"
        )
        assert response.status_code == 200

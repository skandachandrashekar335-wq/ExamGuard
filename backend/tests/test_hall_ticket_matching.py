import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.document import Document, DocumentStatus, DocumentType
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration
from app.models.extraction import ExtractedField, ExtractionResult, ExtractionStatus
from app.models.hall_ticket_match import HallTicketMatchResult, HallTicketMatchSignal
from app.models.seat_assignment import SeatAssignment
from app.models.student import Student
from app.models.subject import Subject


@pytest.fixture(autouse=True)
def clean_test_data():
    db = SessionLocal()
    try:
        match_docs = db.query(Document.id).filter(
            Document.original_filename.ilike("MATCHTEST%")
        ).subquery()
        match_extractions = db.query(ExtractionResult.id).filter(
            ExtractionResult.document_id.in_(db.query(match_docs))
        ).subquery()
        match_results = db.query(HallTicketMatchResult.id).filter(
            HallTicketMatchResult.document_id.in_(db.query(match_docs))
        ).subquery()
        db.execute(delete(ExtractedField).where(
            ExtractedField.extraction_result_id.in_(db.query(match_extractions))
        ))
        db.execute(delete(HallTicketMatchSignal).where(
            HallTicketMatchSignal.match_result_id.in_(db.query(match_results))
        ))
        db.execute(delete(HallTicketMatchResult).where(
            HallTicketMatchResult.document_id.in_(db.query(match_docs))
        ))
        db.execute(delete(ExtractionResult).where(
            ExtractionResult.document_id.in_(db.query(match_docs))
        ))
        db.execute(delete(Document).where(
            Document.original_filename.ilike("MATCHTEST%")
        ))
        db.execute(delete(SeatAssignment).where(
            SeatAssignment.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("MATCHSTU%"))
            )
        ))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("MATCHSTU%"))
            )
        ))
        db.execute(delete(ExamHall).where(ExamHall.building.ilike("MATCHHALL%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("REATEXAM%")))
        db.execute(delete(Subject).where(Subject.code.ilike("MATCHSUB%")))
        db.execute(delete(Student).where(Student.usn.ilike("MATCHSTU%")))
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
        json={"usn": "MATCHSTU01", "name": "Match Test Student"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def test_subject(client):
    response = client.post(
        "/api/v1/subjects",
        json={
            "code": "MATCHSUB01",
            "name": "Match Test Subject",
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
            "exam_name": "REATEXAM Final Exam",
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
            "building": "MATCHHALL Block A",
            "room_number": "MATCHHALL101",
            "capacity": 50,
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
def test_seat_assignment(client, test_registration, test_hall):
    response = client.post(
        "/api/v1/seat-assignments",
        json={
            "exam_registration_id": test_registration["id"],
            "exam_hall_id": test_hall["id"],
            "seat_number": "A1",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_document(client, filename="MATCHTEST_ticket.pdf"):
    db = SessionLocal()
    try:
        doc = Document(
            original_filename=filename,
            stored_key=f"test/{filename}",
            content_type="application/pdf",
            file_size=1024,
            document_type=DocumentType.HALL_TICKET.value,
            status=DocumentStatus.PROCESSED.value,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc
    finally:
        db.close()


def _create_extraction_result(client, document_id):
    db = SessionLocal()
    try:
        result = ExtractionResult(
            document_id=document_id,
            raw_ocr_text="test",
            ocr_engine="tesseract",
            ocr_avg_confidence=85.0,
            status=ExtractionStatus.COMPLETED.value,
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        return result
    finally:
        db.close()


def _create_extracted_field(
    extraction_result_id,
    field_name,
    extracted_value=None,
    label_found=True,
    pattern_match=True,
):
    db = SessionLocal()
    try:
        field = ExtractedField(
            extraction_result_id=extraction_result_id,
            field_name=field_name,
            extracted_value=extracted_value,
            label_found=label_found,
            pattern_match=pattern_match,
            validation_status="VALID" if extracted_value else "MISSING",
            review_status="AUTO_APPROVED" if extracted_value else "REVIEW_REQUIRED",
        )
        db.add(field)
        db.commit()
        return field
    finally:
        db.close()


class TestStudentMatching:
    def test_matching_usn(self, client, test_student):
        doc = _create_document(client, "MATCHTEST_usn.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["student_id"] == test_student["id"]

        usn_signal = next(
            (s for s in data["signals"] if s["field_name"] == "usn"), None
        )
        assert usn_signal is not None
        assert usn_signal["matched"] is True
        assert usn_signal["extracted_value"] == "MATCHSTU01"

    def test_unknown_usn(self, client):
        doc = _create_document(client, "MATCHTEST_unknown_usn.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "UNKNOWN123")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["student_id"] is None

        usn_signal = next(
            (s for s in data["signals"] if s["field_name"] == "usn"), None
        )
        assert usn_signal is not None
        assert usn_signal["matched"] is False

    def test_name_matches(self, client, test_student):
        doc = _create_document(client, "MATCHTEST_name_match.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")
        _create_extracted_field(extraction.id, "name", "Match Test Student")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()

        name_signal = next(
            (s for s in data["signals"] if s["field_name"] == "name"), None
        )
        assert name_signal is not None
        assert name_signal["matched"] is True

    def test_name_mismatch(self, client, test_student):
        doc = _create_document(client, "MATCHTEST_name_mismatch.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")
        _create_extracted_field(extraction.id, "name", "Wrong Name")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()

        name_signal = next(
            (s for s in data["signals"] if s["field_name"] == "name"), None
        )
        assert name_signal is not None
        assert name_signal["matched"] is False

    def test_missing_usn(self, client):
        doc = _create_document(client, "MATCHTEST_missing_usn.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "name", "Some Name")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["student_id"] is None

        usn_signal = next(
            (s for s in data["signals"] if s["field_name"] == "usn"), None
        )
        assert usn_signal is not None
        assert usn_signal["matched"] is False
        assert usn_signal["extracted_value"] is None


class TestExamMatching:
    def test_exact_match(self, client, test_exam):
        doc = _create_document(client, "MATCHTEST_exact_exam.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "exam_name", "REATEXAM Final Exam")
        _create_extracted_field(extraction.id, "exam_date", "2026-12-15")
        _create_extracted_field(extraction.id, "start_time", "10:00")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["exam_id"] == test_exam["id"]

        exam_signal = next(
            (s for s in data["signals"] if s["field_name"] == "exam_name"), None
        )
        assert exam_signal is not None
        assert exam_signal["matched"] is True

    def test_wrong_date(self, client, test_exam):
        doc = _create_document(client, "MATCHTEST_wrong_date.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "exam_name", "REATEXAM Final Exam")
        _create_extracted_field(extraction.id, "exam_date", "2026-12-20")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["exam_id"] is None

    def test_wrong_start_time(self, client, test_exam):
        doc = _create_document(client, "MATCHTEST_wrong_time.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "exam_name", "REATEXAM Final Exam")
        _create_extracted_field(extraction.id, "exam_date", "2026-12-15")
        _create_extracted_field(extraction.id, "start_time", "14:00")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["exam_id"] is None

    def test_exam_not_found(self, client):
        doc = _create_document(client, "MATCHTEST_no_exam.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "exam_name", "Nonexistent Exam")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["exam_id"] is None

        exam_signal = next(
            (s for s in data["signals"] if s["field_name"] == "exam_name"), None
        )
        assert exam_signal is not None
        assert exam_signal["matched"] is False


class TestRegistrationVerification:
    def test_registered_student(self, client, test_registration):
        doc = _create_document(client, "MATCHTEST_registered.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")
        _create_extracted_field(extraction.id, "exam_name", "REATEXAM Final Exam")
        _create_extracted_field(extraction.id, "exam_date", "2026-12-15")
        _create_extracted_field(extraction.id, "start_time", "10:00")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["registration_id"] == test_registration["id"]

        reg_signal = next(
            (s for s in data["signals"] if s["field_name"] == "registration"), None
        )
        assert reg_signal is not None
        assert reg_signal["matched"] is True

    def test_cancelled_registration(self, client, test_registration):
        client.delete(f"/api/v1/exam-registrations/{test_registration['id']}")

        doc = _create_document(client, "MATCHTEST_cancelled_reg.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")
        _create_extracted_field(extraction.id, "exam_name", "REATEXAM Final Exam")
        _create_extracted_field(extraction.id, "exam_date", "2026-12-15")
        _create_extracted_field(extraction.id, "start_time", "10:00")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["registration_id"] is None

        reg_signal = next(
            (s for s in data["signals"] if s["field_name"] == "registration"), None
        )
        assert reg_signal is not None
        assert reg_signal["matched"] is False

    def test_missing_registration(self, client, test_student, test_exam):
        doc = _create_document(client, "MATCHTEST_no_reg.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")
        _create_extracted_field(extraction.id, "exam_name", "REATEXAM Final Exam")
        _create_extracted_field(extraction.id, "exam_date", "2026-12-15")
        _create_extracted_field(extraction.id, "start_time", "10:00")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["registration_id"] is None

        reg_signal = next(
            (s for s in data["signals"] if s["field_name"] == "registration"), None
        )
        assert reg_signal is not None
        assert reg_signal["matched"] is False


class TestSeatAssignmentVerification:
    def test_correct_seat(self, client, test_seat_assignment):
        doc = _create_document(client, "MATCHTEST_correct_seat.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")
        _create_extracted_field(extraction.id, "exam_name", "REATEXAM Final Exam")
        _create_extracted_field(extraction.id, "exam_date", "2026-12-15")
        _create_extracted_field(extraction.id, "start_time", "10:00")
        _create_extracted_field(extraction.id, "exam_hall", "MATCHHALL Block A")
        _create_extracted_field(extraction.id, "seat_number", "A1")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["seat_assignment_id"] == test_seat_assignment["id"]

        hall_signal = next(
            (s for s in data["signals"] if s["field_name"] == "exam_hall"), None
        )
        assert hall_signal is not None
        assert hall_signal["matched"] is True

        seat_signal = next(
            (s for s in data["signals"] if s["field_name"] == "seat_number"), None
        )
        assert seat_signal is not None
        assert seat_signal["matched"] is True

    def test_wrong_seat(self, client, test_seat_assignment):
        doc = _create_document(client, "MATCHTEST_wrong_seat.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")
        _create_extracted_field(extraction.id, "exam_name", "REATEXAM Final Exam")
        _create_extracted_field(extraction.id, "exam_date", "2026-12-15")
        _create_extracted_field(extraction.id, "start_time", "10:00")
        _create_extracted_field(extraction.id, "seat_number", "B99")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()

        seat_signal = next(
            (s for s in data["signals"] if s["field_name"] == "seat_number"), None
        )
        assert seat_signal is not None
        assert seat_signal["matched"] is False

    def test_wrong_hall(self, client, test_seat_assignment):
        doc = _create_document(client, "MATCHTEST_wrong_hall.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")
        _create_extracted_field(extraction.id, "exam_name", "REATEXAM Final Exam")
        _create_extracted_field(extraction.id, "exam_date", "2026-12-15")
        _create_extracted_field(extraction.id, "start_time", "10:00")
        _create_extracted_field(extraction.id, "exam_hall", "Wrong Hall 999")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()

        hall_signal = next(
            (s for s in data["signals"] if s["field_name"] == "exam_hall"), None
        )
        assert hall_signal is not None
        assert hall_signal["matched"] is False

    def test_no_seat_assignment(self, client, test_registration):
        doc = _create_document(client, "MATCHTEST_no_seat.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")
        _create_extracted_field(extraction.id, "exam_name", "REATEXAM Final Exam")
        _create_extracted_field(extraction.id, "exam_date", "2026-12-15")
        _create_extracted_field(extraction.id, "start_time", "10:00")
        _create_extracted_field(extraction.id, "seat_number", "A1")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["seat_assignment_id"] is None


class TestCombinedMatching:
    def test_complete_successful_match(self, client, test_seat_assignment):
        doc = _create_document(client, "MATCHTEST_complete.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")
        _create_extracted_field(extraction.id, "name", "Match Test Student")
        _create_extracted_field(extraction.id, "exam_name", "REATEXAM Final Exam")
        _create_extracted_field(extraction.id, "subject", "MATCHSUB01")
        _create_extracted_field(extraction.id, "exam_date", "2026-12-15")
        _create_extracted_field(extraction.id, "start_time", "10:00")
        _create_extracted_field(extraction.id, "exam_hall", "MATCHHALL Block A")
        _create_extracted_field(extraction.id, "seat_number", "A1")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["overall_status"] == "MATCHED"
        assert data["student_id"] is not None
        assert data["exam_id"] is not None
        assert data["registration_id"] is not None
        assert data["seat_assignment_id"] is not None

    def test_partial_match(self, client, test_student):
        doc = _create_document(client, "MATCHTEST_partial.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")
        _create_extracted_field(extraction.id, "exam_name", "Nonexistent Exam")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["overall_status"] == "PARTIAL_MATCH"

    def test_mismatch(self, client):
        doc = _create_document(client, "MATCHTEST_mismatch.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "UNKNOWN999")
        _create_extracted_field(extraction.id, "exam_name", "Fake Exam")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["overall_status"] == "NOT_FOUND"

    def test_missing_database_records(self, client):
        doc = _create_document(client, "MATCHTEST_no_records.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()

    def test_repeated_matching_creates_independent_results(
        self, client, test_student
    ):
        doc = _create_document(client, "MATCHTEST_repeated.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")

        resp1 = client.post(f"/api/v1/documents/{doc.id}/match")
        assert resp1.status_code == 201
        result1_id = resp1.json()["id"]

        resp2 = client.post(f"/api/v1/documents/{doc.id}/match")
        assert resp2.status_code == 201
        result2_id = resp2.json()["id"]

        assert result1_id != result2_id


class TestSecurityBoundary:
    def test_matching_does_not_mutate_student(self, client, test_student):
        original_name = test_student["name"]

        doc = _create_document(client, "MATCHTEST_no_mutate_student.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")
        _create_extracted_field(extraction.id, "name", "Different Name")

        client.post(f"/api/v1/documents/{doc.id}/match")

        response = client.get(f"/api/v1/students/{test_student['id']}")
        assert response.status_code == 200
        assert response.json()["name"] == original_name

    def test_matching_does_not_mutate_exam(self, client, test_exam):
        original_name = test_exam["exam_name"]

        doc = _create_document(client, "MATCHTEST_no_mutate_exam.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "exam_name", "Different Exam")

        client.post(f"/api/v1/documents/{doc.id}/match")

        response = client.get(f"/api/v1/exams/{test_exam['id']}")
        assert response.status_code == 200
        assert response.json()["exam_name"] == original_name

    def test_matching_does_not_create_registration(
        self, client, test_student, test_exam
    ):
        db = SessionLocal()
        try:
            initial_count = db.query(ExamRegistration).filter(
                ExamRegistration.student_id == test_student["id"],
                ExamRegistration.exam_id == test_exam["id"],
            ).count()
        finally:
            db.close()

        doc = _create_document(client, "MATCHTEST_no_create_reg.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")
        _create_extracted_field(extraction.id, "exam_name", "REATEXAM Final Exam")
        _create_extracted_field(extraction.id, "exam_date", "2026-12-15")
        _create_extracted_field(extraction.id, "start_time", "10:00")

        client.post(f"/api/v1/documents/{doc.id}/match")

        db = SessionLocal()
        try:
            final_count = db.query(ExamRegistration).filter(
                ExamRegistration.student_id == test_student["id"],
                ExamRegistration.exam_id == test_exam["id"],
            ).count()
            assert final_count == initial_count
        finally:
            db.close()

    def test_matching_does_not_create_seat_assignment(
        self, client, test_registration
    ):
        db = SessionLocal()
        try:
            initial_count = db.query(SeatAssignment).filter(
                SeatAssignment.exam_registration_id == test_registration["id"],
            ).count()
        finally:
            db.close()

        doc = _create_document(client, "MATCHTEST_no_create_seat.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")
        _create_extracted_field(extraction.id, "exam_name", "REATEXAM Final Exam")
        _create_extracted_field(extraction.id, "exam_date", "2026-12-15")
        _create_extracted_field(extraction.id, "start_time", "10:00")

        client.post(f"/api/v1/documents/{doc.id}/match")

        db = SessionLocal()
        try:
            final_count = db.query(SeatAssignment).filter(
                SeatAssignment.exam_registration_id == test_registration["id"],
            ).count()
            assert final_count == initial_count
        finally:
            db.close()

    def test_inactive_student_not_treated_as_valid(self, client):
        resp = client.post(
            "/api/v1/students",
            json={"usn": "MATCHSTU99", "name": "Inactive Student"},
        )
        assert resp.status_code == 201
        inactive_student = resp.json()
        client.delete(f"/api/v1/students/{inactive_student['id']}")

        doc = _create_document(client, "MATCHTEST_inactive_student.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU99")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 201
        data = response.json()
        assert data["student_id"] is None

        usn_signal = next(
            (s for s in data["signals"] if s["field_name"] == "usn"), None
        )
        assert usn_signal is not None
        assert usn_signal["matched"] is False


class TestMatchRetrieval:
    def test_get_match_result(self, client, test_student):
        doc = _create_document(client, "MATCHTEST_get_result.pdf")
        extraction = _create_extraction_result(client, doc.id)
        _create_extracted_field(extraction.id, "usn", "MATCHSTU01")

        create_resp = client.post(f"/api/v1/documents/{doc.id}/match")
        assert create_resp.status_code == 201

        get_resp = client.get(f"/api/v1/documents/{doc.id}/match")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["document_id"] == doc.id
        assert len(data["signals"]) > 0

    def test_get_match_not_found(self, client):
        response = client.get("/api/v1/documents/999999/match")
        assert response.status_code == 404

    def test_match_document_not_found(self, client):
        response = client.post("/api/v1/documents/999999/match")
        assert response.status_code == 404

    def test_match_without_extraction(self, client):
        doc = _create_document(client, "MATCHTEST_no_extraction.pdf")

        response = client.post(f"/api/v1/documents/{doc.id}/match")
        assert response.status_code == 404

"""Phase 10.2 — Entry Verification Service Layer.

Tests for entry verification service functions.
Covers: creation, validation, hall ticket check, seat check, identity check,
decision logic, escalation, state transitions, repeated operations,
idempotency, and privacy invariants.
"""

import pytest
from datetime import date, time
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Base
from app.models.camera import Camera, CameraStatus
from app.models.camera_entry_point import CameraEntryPointMapping
from app.models.entry_point import EntryPoint
from app.models.entry_verification import (
    EntryVerification,
    EntryVerificationStatus,
    HallTicketCheckStatus,
    IdentityCheckStatus,
    SeatCheckStatus,
)
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.hall_ticket import HallTicket, HallTicketStatus
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationDecision,
    IdentityVerificationMethod,
    IdentityVerificationStatus,
)
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.student import Student
from app.models.subject import Subject
from app.services.entry_verification import (
    create_entry_verification,
    begin_processing,
    evaluate_entry,
    escalate_for_review,
    get_entry_verification,
    list_entry_verifications,
    process_hall_ticket_check,
    process_identity_check,
    process_seat_check,
    resolve_escalation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture()
def student(db):
    s = Student(usn="TEST001", name="Test Student")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture()
def subject(db):
    s = Subject(code="SUB101", name="Test Subject", department="CS", semester=6)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture()
def exam(db, subject):
    e = Exam(
        subject_id=subject.id,
        exam_name="Test Exam",
        exam_date=date(2026, 9, 15),
        start_time=time(9, 0),
        end_time=time(12, 0),
        semester=6,
        department="CS",
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@pytest.fixture()
def hall(db):
    h = ExamHall(building="TestBuilding", room_number="101", capacity=50)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


@pytest.fixture()
def registration(db, student, exam):
    r = ExamRegistration(student_id=student.id, exam_id=exam.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@pytest.fixture()
def hall_ticket(db, registration):
    ht = HallTicket(
        exam_registration_id=registration.id,
        status=HallTicketStatus.VERIFIED.value,
    )
    db.add(ht)
    db.commit()
    db.refresh(ht)
    return ht


@pytest.fixture()
def entry_point(db, hall):
    ep = EntryPoint(name="Main Gate", code="MAIN_GATE", exam_hall_id=hall.id)
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


@pytest.fixture()
def camera(db, hall):
    c = Camera(
        name="Test Camera",
        device_identifier="CAM-TEST-001",
        exam_hall_id=hall.id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def mapping(db, camera, entry_point):
    m = CameraEntryPointMapping(
        camera_id=camera.id,
        entry_point_id=entry_point.id,
        is_enabled=True,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@pytest.fixture()
def seat(db, registration, hall, exam, student):
    s = SeatAssignment(
        exam_registration_id=registration.id,
        exam_hall_id=hall.id,
        exam_id=exam.id,
        student_id=student.id,
        seat_number="A1",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture()
def identity_attempt(db, student, registration, hall_ticket):
    att = IdentityVerificationAttempt(
        student_id=student.id,
        exam_registration_id=registration.id,
        hall_ticket_id=hall_ticket.id,
        status=IdentityVerificationStatus.COMPLETED.value,
        verification_method=IdentityVerificationMethod.FACE.value,
        decision=IdentityVerificationDecision.MATCH.value,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


@pytest.fixture()
def failed_identity_attempt(db, student, registration, hall_ticket):
    att = IdentityVerificationAttempt(
        student_id=student.id,
        exam_registration_id=registration.id,
        hall_ticket_id=hall_ticket.id,
        status=IdentityVerificationStatus.COMPLETED.value,
        verification_method=IdentityVerificationMethod.FACE.value,
        decision=IdentityVerificationDecision.NO_MATCH.value,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

class TestCreateEntryVerification:
    def test_valid_creation(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        assert ev.id is not None
        assert ev.student_id == student.id
        assert ev.exam_registration_id == registration.id
        assert ev.entry_point_id == entry_point.id
        assert ev.status == EntryVerificationStatus.PENDING.value
        assert ev.hall_ticket_check == HallTicketCheckStatus.PENDING.value
        assert ev.identity_check == IdentityCheckStatus.PENDING.value
        assert ev.seat_check == SeatCheckStatus.PENDING.value

    def test_valid_creation_with_camera(self, db, student, registration, entry_point, camera, mapping):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            camera_id=camera.id,
        )
        assert ev.camera_id == camera.id

    def test_valid_creation_with_hall_ticket(self, db, student, registration, entry_point, hall_ticket):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        assert ev.hall_ticket_id == hall_ticket.id

    def test_valid_creation_with_all_optionals(self, db, student, registration, entry_point, camera, mapping, hall_ticket):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            camera_id=camera.id,
            hall_ticket_id=hall_ticket.id,
        )
        assert ev.camera_id == camera.id
        assert ev.hall_ticket_id == hall_ticket.id

    def test_missing_student_raises(self, db, registration, entry_point):
        with pytest.raises(LookupError, match="Student with id 99999 not found"):
            create_entry_verification(
                db,
                student_id=99999,
                exam_registration_id=registration.id,
                entry_point_id=entry_point.id,
            )

    def test_missing_registration_raises(self, db, student, entry_point):
        with pytest.raises(LookupError, match="Exam registration with id 99999 not found"):
            create_entry_verification(
                db,
                student_id=student.id,
                exam_registration_id=99999,
                entry_point_id=entry_point.id,
            )

    def test_registration_student_mismatch_raises(self, db, student, entry_point, exam):
        other_reg = ExamRegistration(student_id=student.id + 100, exam_id=exam.id)
        db.add(other_reg)
        db.commit()
        db.refresh(other_reg)

        with pytest.raises(ValueError, match="belongs to student"):
            create_entry_verification(
                db,
                student_id=student.id,
                exam_registration_id=other_reg.id,
                entry_point_id=entry_point.id,
            )

    def test_cancelled_registration_raises(self, db, student, entry_point, exam):
        reg = ExamRegistration(
            student_id=student.id, exam_id=exam.id,
            status=RegistrationStatus.CANCELLED.value,
        )
        db.add(reg)
        db.commit()
        db.refresh(reg)

        with pytest.raises(ValueError, match="cancelled"):
            create_entry_verification(
                db,
                student_id=student.id,
                exam_registration_id=reg.id,
                entry_point_id=entry_point.id,
            )

    def test_inactive_entry_point_raises(self, db, student, registration, hall):
        ep = EntryPoint(
            name="Inactive Gate", code="INACTIVE",
            exam_hall_id=hall.id, is_active=False,
        )
        db.add(ep)
        db.commit()
        db.refresh(ep)

        with pytest.raises(ValueError, match="not active"):
            create_entry_verification(
                db,
                student_id=student.id,
                exam_registration_id=registration.id,
                entry_point_id=ep.id,
            )

    def test_entry_point_without_hall_raises(self, db, student, registration):
        ep = EntryPoint(name="No Hall Gate", code="NO_HALL")
        db.add(ep)
        db.commit()
        db.refresh(ep)

        with pytest.raises(ValueError, match="not associated with an exam hall"):
            create_entry_verification(
                db,
                student_id=student.id,
                exam_registration_id=registration.id,
                entry_point_id=ep.id,
            )

    def test_invalid_camera_raises(self, db, student, registration, entry_point):
        with pytest.raises(LookupError, match="Camera with id 99999 not found"):
            create_entry_verification(
                db,
                student_id=student.id,
                exam_registration_id=registration.id,
                entry_point_id=entry_point.id,
                camera_id=99999,
            )

    def test_camera_not_mapped_raises(self, db, student, registration, entry_point, camera):
        with pytest.raises(ValueError, match="not mapped to entry point"):
            create_entry_verification(
                db,
                student_id=student.id,
                exam_registration_id=registration.id,
                entry_point_id=entry_point.id,
                camera_id=camera.id,
            )

    def test_inactive_camera_raises(self, db, student, registration, entry_point, camera, mapping):
        camera.is_active = False
        db.commit()

        with pytest.raises(ValueError, match="not active"):
            create_entry_verification(
                db,
                student_id=student.id,
                exam_registration_id=registration.id,
                entry_point_id=entry_point.id,
                camera_id=camera.id,
            )

    def test_invalid_hall_ticket_raises(self, db, student, registration, entry_point):
        with pytest.raises(LookupError, match="Hall ticket with id 99999 not found"):
            create_entry_verification(
                db,
                student_id=student.id,
                exam_registration_id=registration.id,
                entry_point_id=entry_point.id,
                hall_ticket_id=99999,
            )

    def test_hall_ticket_wrong_registration_raises(self, db, student, registration, entry_point, subject):
        student2 = Student(usn="TEST002", name="Other Student")
        db.add(student2)
        db.commit()
        db.refresh(student2)

        exam2 = Exam(
            subject_id=subject.id,
            exam_name="Other Exam",
            exam_date=date(2026, 9, 16),
            start_time=time(9, 0),
            end_time=time(12, 0),
            semester=6,
            department="CS",
        )
        db.add(exam2)
        db.commit()
        db.refresh(exam2)

        other_reg = ExamRegistration(student_id=student2.id, exam_id=exam2.id)
        db.add(other_reg)
        db.commit()
        db.refresh(other_reg)

        ht = HallTicket(
            exam_registration_id=other_reg.id,
            status=HallTicketStatus.VERIFIED.value,
        )
        db.add(ht)
        db.commit()
        db.refresh(ht)

        with pytest.raises(ValueError, match="belongs to registration"):
            create_entry_verification(
                db,
                student_id=student.id,
                exam_registration_id=registration.id,
                entry_point_id=entry_point.id,
                hall_ticket_id=ht.id,
            )

    def test_sets_exam_hall_from_entry_point(self, db, student, registration, entry_point, hall):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        assert ev.exam_hall_id == hall.id


# ---------------------------------------------------------------------------
# GET / LIST
# ---------------------------------------------------------------------------

class TestGetListEntryVerification:
    def test_get_existing(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        loaded = get_entry_verification(db, ev.id)
        assert loaded is not None
        assert loaded.id == ev.id

    def test_get_nonexistent(self, db):
        assert get_entry_verification(db, 99999) is None

    def test_list_returns_results(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        result = list_entry_verifications(db)
        assert result["total"] >= 1
        assert any(item.id == ev.id for item in result["items"])

    def test_list_filter_by_status(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        result = list_entry_verifications(db, status=EntryVerificationStatus.PENDING.value)
        assert any(item.id == ev.id for item in result["items"])

        result = list_entry_verifications(db, status=EntryVerificationStatus.GRANTED.value)
        assert not any(item.id == ev.id for item in result["items"])


# ---------------------------------------------------------------------------
# BEGIN PROCESSING
# ---------------------------------------------------------------------------

class TestBeginProcessing:
    def test_pending_to_in_progress(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        result = begin_processing(db, ev.id)
        assert result.status == EntryVerificationStatus.IN_PROGRESS.value

    def test_in_progress_to_in_progress_raises(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        begin_processing(db, ev.id)
        with pytest.raises(ValueError, match="Cannot transition"):
            begin_processing(db, ev.id)

    def test_terminal_state_cannot_begin(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        escalate_for_review(db, ev.id, reason="Test escalation")
        resolve_escalation(db, ev.id, granted=True)
        with pytest.raises(ValueError, match="Cannot transition"):
            begin_processing(db, ev.id)


# ---------------------------------------------------------------------------
# HALL TICKET CHECK
# ---------------------------------------------------------------------------

class TestHallTicketCheck:
    def test_verified_ticket_passed(self, db, student, registration, entry_point, hall_ticket):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        result = process_hall_ticket_check(db, ev.id)
        assert result.hall_ticket_check == HallTicketCheckStatus.PASSED.value

    def test_no_ticket_linked_failed(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        result = process_hall_ticket_check(db, ev.id)
        assert result.hall_ticket_check == HallTicketCheckStatus.FAILED.value

    def test_unverified_ticket_failed(self, db, student, registration, entry_point):
        ht = HallTicket(
            exam_registration_id=registration.id,
            status=HallTicketStatus.MATCHED.value,
        )
        db.add(ht)
        db.commit()
        db.refresh(ht)

        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=ht.id,
        )
        result = process_hall_ticket_check(db, ev.id)
        assert result.hall_ticket_check == HallTicketCheckStatus.FAILED.value

    def test_ticket_wrong_registration_failed(self, db, student, registration, entry_point, subject):
        student2 = Student(usn="TEST003", name="Another Student")
        db.add(student2)
        db.commit()
        db.refresh(student2)

        exam2 = Exam(
            subject_id=subject.id,
            exam_name="Another Exam",
            exam_date=date(2026, 9, 17),
            start_time=time(9, 0),
            end_time=time(12, 0),
            semester=6,
            department="CS",
        )
        db.add(exam2)
        db.commit()
        db.refresh(exam2)

        other_reg = ExamRegistration(student_id=student2.id, exam_id=exam2.id)
        db.add(other_reg)
        db.commit()
        db.refresh(other_reg)

        ht = HallTicket(
            exam_registration_id=other_reg.id,
            status=HallTicketStatus.VERIFIED.value,
        )
        db.add(ht)
        db.commit()
        db.refresh(ht)

        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        ev.hall_ticket_id = ht.id
        db.commit()
        db.refresh(ev)

        result = process_hall_ticket_check(db, ev.id)
        assert result.hall_ticket_check == HallTicketCheckStatus.FAILED.value

    def test_repeated_check_safe(self, db, student, registration, entry_point, hall_ticket):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        r1 = process_hall_ticket_check(db, ev.id)
        r2 = process_hall_ticket_check(db, ev.id)
        assert r1.hall_ticket_check == r2.hall_ticket_check == HallTicketCheckStatus.PASSED.value

    def test_ticket_not_mutated(self, db, student, registration, entry_point, hall_ticket):
        original_status = hall_ticket.status
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        process_hall_ticket_check(db, ev.id)
        db.refresh(hall_ticket)
        assert hall_ticket.status == original_status

    def test_auto_links_ticket_from_registration(self, db, student, registration, entry_point, hall_ticket):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        assert ev.hall_ticket_id is None
        result = process_hall_ticket_check(db, ev.id)
        assert result.hall_ticket_id == hall_ticket.id
        assert result.hall_ticket_check == HallTicketCheckStatus.PASSED.value

    def test_check_on_terminal_status_raises(self, db, student, registration, entry_point, hall_ticket):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        escalate_for_review(db, ev.id, reason="test")
        resolve_escalation(db, ev.id, granted=True)
        with pytest.raises(ValueError, match="Cannot process hall ticket"):
            process_hall_ticket_check(db, ev.id)


# ---------------------------------------------------------------------------
# SEAT CHECK
# ---------------------------------------------------------------------------

class TestSeatCheck:
    def test_valid_assignment_passed(self, db, student, registration, entry_point, seat):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        result = process_seat_check(db, ev.id)
        assert result.seat_check == SeatCheckStatus.PASSED.value

    def test_no_assignment_failed(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        result = process_seat_check(db, ev.id)
        assert result.seat_check == SeatCheckStatus.FAILED.value

    def test_wrong_hall_failed(self, db, student, registration, exam, entry_point, hall):
        other_hall = ExamHall(building="Other", room_number="202", capacity=30)
        db.add(other_hall)
        db.commit()
        db.refresh(other_hall)

        seat = SeatAssignment(
            exam_registration_id=registration.id,
            exam_hall_id=other_hall.id,
            exam_id=exam.id,
            student_id=student.id,
            seat_number="B2",
        )
        db.add(seat)
        db.commit()
        db.refresh(seat)

        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        result = process_seat_check(db, ev.id)
        assert result.seat_check == SeatCheckStatus.FAILED.value

    def test_seat_not_mutated(self, db, student, registration, entry_point, seat):
        original_seat_number = seat.seat_number
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        process_seat_check(db, ev.id)
        db.refresh(seat)
        assert seat.seat_number == original_seat_number

    def test_repeated_check_safe(self, db, student, registration, entry_point, seat):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        r1 = process_seat_check(db, ev.id)
        r2 = process_seat_check(db, ev.id)
        assert r1.seat_check == r2.seat_check == SeatCheckStatus.PASSED.value

    def test_check_on_terminal_status_raises(self, db, student, registration, entry_point, seat):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        escalate_for_review(db, ev.id, reason="test")
        resolve_escalation(db, ev.id, granted=True)
        with pytest.raises(ValueError, match="Cannot process seat check"):
            process_seat_check(db, ev.id)


# ---------------------------------------------------------------------------
# IDENTITY CHECK
# ---------------------------------------------------------------------------

class TestIdentityCheck:
    def test_successful_identity_passed(self, db, student, registration, entry_point, identity_attempt):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        result = process_identity_check(db, ev.id, identity_attempt_id=identity_attempt.id)
        assert result.identity_check == IdentityCheckStatus.PASSED.value
        assert result.identity_verification_attempt_id == identity_attempt.id

    def test_failed_identity_failed(self, db, student, registration, entry_point, failed_identity_attempt):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        result = process_identity_check(db, ev.id, identity_attempt_id=failed_identity_attempt.id)
        assert result.identity_check == IdentityCheckStatus.FAILED.value

    def test_pending_identity_pending(self, db, student, registration, entry_point, hall_ticket):
        att = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            status=IdentityVerificationStatus.IN_PROGRESS.value,
            verification_method=IdentityVerificationMethod.FACE.value,
            decision=IdentityVerificationDecision.PENDING.value,
        )
        db.add(att)
        db.commit()
        db.refresh(att)

        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        result = process_identity_check(db, ev.id, identity_attempt_id=att.id)
        assert result.identity_check == IdentityCheckStatus.PENDING.value

    def test_no_camera_skipped(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        result = process_identity_check(db, ev.id)
        assert result.identity_check == IdentityCheckStatus.SKIPPED.value

    def test_camera_offline_skipped(self, db, student, registration, entry_point, camera, mapping):
        camera.status = CameraStatus.OFFLINE.value
        db.commit()

        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            camera_id=camera.id,
        )
        result = process_identity_check(db, ev.id)
        assert result.identity_check == IdentityCheckStatus.SKIPPED.value

    def test_camera_disabled_skipped(self, db, student, registration, entry_point, camera, mapping):
        camera.status = CameraStatus.DISABLED.value
        db.commit()

        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            camera_id=camera.id,
        )
        result = process_identity_check(db, ev.id)
        assert result.identity_check == IdentityCheckStatus.SKIPPED.value

    def test_camera_unknown_pending(self, db, student, registration, entry_point, camera, mapping):
        camera.status = CameraStatus.UNKNOWN.value
        db.commit()

        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            camera_id=camera.id,
        )
        result = process_identity_check(db, ev.id)
        assert result.identity_check == IdentityCheckStatus.PENDING.value

    def test_camera_online_no_attempt_pending(self, db, student, registration, entry_point, camera, mapping):
        camera.status = CameraStatus.ONLINE.value
        db.commit()

        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            camera_id=camera.id,
        )
        result = process_identity_check(db, ev.id)
        assert result.identity_check == IdentityCheckStatus.PENDING.value

    def test_inactive_camera_skipped(self, db, student, registration, entry_point, camera, mapping):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            camera_id=camera.id,
        )
        camera.is_active = False
        db.commit()

        result = process_identity_check(db, ev.id)
        assert result.identity_check == IdentityCheckStatus.SKIPPED.value

    def test_invalid_attempt_raises(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        with pytest.raises(LookupError, match="Identity verification attempt 99999 not found"):
            process_identity_check(db, ev.id, identity_attempt_id=99999)

    def test_check_on_terminal_status_raises(self, db, student, registration, entry_point, identity_attempt):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        escalate_for_review(db, ev.id, reason="test")
        resolve_escalation(db, ev.id, granted=True)
        with pytest.raises(ValueError, match="Cannot process identity check"):
            process_identity_check(db, ev.id, identity_attempt_id=identity_attempt.id)


# ---------------------------------------------------------------------------
# DECISION
# ---------------------------------------------------------------------------

class TestDecision:
    def test_all_pass_granted(self, db, student, registration, entry_point, hall_ticket, seat, identity_attempt):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        begin_processing(db, ev.id)
        process_hall_ticket_check(db, ev.id)
        process_seat_check(db, ev.id)
        process_identity_check(db, ev.id, identity_attempt_id=identity_attempt.id)

        result = evaluate_entry(db, ev.id)
        assert result.status == EntryVerificationStatus.GRANTED.value

    def test_hall_ticket_fail_denied(self, db, student, subject, seat):
        exam_no_ticket = Exam(
            subject_id=subject.id,
            exam_name="No Ticket Exam",
            exam_date=date(2026, 9, 20),
            start_time=time(9, 0),
            end_time=time(12, 0),
            semester=6,
            department="CS",
        )
        db.add(exam_no_ticket)
        db.commit()
        db.refresh(exam_no_ticket)

        reg_no_ticket = ExamRegistration(student_id=student.id, exam_id=exam_no_ticket.id)
        db.add(reg_no_ticket)
        db.commit()
        db.refresh(reg_no_ticket)

        hall2 = ExamHall(building="Other", room_number="303", capacity=40)
        db.add(hall2)
        db.commit()
        db.refresh(hall2)

        ep2 = EntryPoint(name="Side Gate", code="SIDE_GATE", exam_hall_id=hall2.id)
        db.add(ep2)
        db.commit()
        db.refresh(ep2)

        seat2 = SeatAssignment(
            exam_registration_id=reg_no_ticket.id,
            exam_hall_id=hall2.id,
            exam_id=exam_no_ticket.id,
            student_id=student.id,
            seat_number="C3",
        )
        db.add(seat2)
        db.commit()
        db.refresh(seat2)

        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=reg_no_ticket.id,
            entry_point_id=ep2.id,
        )
        begin_processing(db, ev.id)
        process_hall_ticket_check(db, ev.id)
        process_seat_check(db, ev.id)

        result = evaluate_entry(db, ev.id)
        assert result.status == EntryVerificationStatus.DENIED.value

    def test_seat_fail_denied(self, db, student, registration, entry_point, hall_ticket, identity_attempt):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        begin_processing(db, ev.id)
        process_hall_ticket_check(db, ev.id)
        process_seat_check(db, ev.id)
        process_identity_check(db, ev.id, identity_attempt_id=identity_attempt.id)

        result = evaluate_entry(db, ev.id)
        assert result.status == EntryVerificationStatus.DENIED.value

    def test_identity_fail_denied(self, db, student, registration, entry_point, hall_ticket, seat, failed_identity_attempt):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        begin_processing(db, ev.id)
        process_hall_ticket_check(db, ev.id)
        process_seat_check(db, ev.id)
        process_identity_check(db, ev.id, identity_attempt_id=failed_identity_attempt.id)

        result = evaluate_entry(db, ev.id)
        assert result.status == EntryVerificationStatus.DENIED.value

    def test_pending_identity_escalated(self, db, student, registration, entry_point, hall_ticket, seat, camera, mapping):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
            camera_id=camera.id,
        )
        begin_processing(db, ev.id)
        process_hall_ticket_check(db, ev.id)
        process_seat_check(db, ev.id)
        process_identity_check(db, ev.id)

        result = evaluate_entry(db, ev.id)
        assert result.status == EntryVerificationStatus.ESCALATED.value

    def test_skipped_identity_escalated(self, db, student, registration, entry_point, hall_ticket, seat):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        begin_processing(db, ev.id)
        process_hall_ticket_check(db, ev.id)
        process_seat_check(db, ev.id)
        process_identity_check(db, ev.id)

        result = evaluate_entry(db, ev.id)
        assert result.status == EntryVerificationStatus.ESCALATED.value

    def test_invalid_transition_rejected(self, db, student, registration, entry_point, hall_ticket, seat, identity_attempt):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        begin_processing(db, ev.id)
        process_hall_ticket_check(db, ev.id)
        process_seat_check(db, ev.id)
        process_identity_check(db, ev.id, identity_attempt_id=identity_attempt.id)
        evaluate_entry(db, ev.id)

        with pytest.raises(ValueError, match="Cannot evaluate"):
            evaluate_entry(db, ev.id)

    def test_terminal_state_cannot_evaluate(self, db, student, registration, entry_point, hall_ticket, seat, identity_attempt):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        begin_processing(db, ev.id)
        process_hall_ticket_check(db, ev.id)
        process_seat_check(db, ev.id)
        process_identity_check(db, ev.id, identity_attempt_id=identity_attempt.id)
        evaluate_entry(db, ev.id)

        with pytest.raises(ValueError, match="Cannot evaluate"):
            evaluate_entry(db, ev.id)


# ---------------------------------------------------------------------------
# ESCALATION
# ---------------------------------------------------------------------------

class TestEscalation:
    def test_escalation_stored(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        result = escalate_for_review(db, ev.id, reason="Camera offline, manual review needed")
        assert result.status == EntryVerificationStatus.ESCALATED.value
        assert result.escalation_reason == "Camera offline, manual review needed"

    def test_check_states_preserved(self, db, student, registration, entry_point, hall_ticket, seat):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        begin_processing(db, ev.id)
        process_hall_ticket_check(db, ev.id)
        process_seat_check(db, ev.id)

        result = escalate_for_review(db, ev.id, reason="test")
        assert result.hall_ticket_check == HallTicketCheckStatus.PASSED.value
        assert result.seat_check == SeatCheckStatus.PASSED.value
        assert result.identity_check == IdentityCheckStatus.PENDING.value

    def test_empty_reason_raises(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        with pytest.raises(ValueError, match="Escalation reason is required"):
            escalate_for_review(db, ev.id, reason="")

    def test_resolve_granted(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        escalate_for_review(db, ev.id, reason="test")
        result = resolve_escalation(db, ev.id, granted=True)
        assert result.status == EntryVerificationStatus.GRANTED.value
        assert result.resolved_at is not None

    def test_resolve_denied(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        escalate_for_review(db, ev.id, reason="test")
        result = resolve_escalation(db, ev.id, granted=False)
        assert result.status == EntryVerificationStatus.DENIED.value
        assert result.resolved_at is not None

    def test_resolve_non_escalated_raises(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        with pytest.raises(ValueError, match="Must be ESCALATED"):
            resolve_escalation(db, ev.id, granted=True)

    def test_escalation_from_in_progress(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        begin_processing(db, ev.id)
        result = escalate_for_review(db, ev.id, reason="manual review")
        assert result.status == EntryVerificationStatus.ESCALATED.value

    def test_escalation_from_terminal_raises(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        escalate_for_review(db, ev.id, reason="test")
        resolve_escalation(db, ev.id, granted=True)
        with pytest.raises(ValueError, match="Cannot transition"):
            escalate_for_review(db, ev.id, reason="test2")


# ---------------------------------------------------------------------------
# REPEATED OPERATIONS
# ---------------------------------------------------------------------------

class TestRepeatedOperations:
    def test_repeated_evaluation_safe(self, db, student, registration, entry_point, hall_ticket, seat, identity_attempt):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        begin_processing(db, ev.id)
        process_hall_ticket_check(db, ev.id)
        process_seat_check(db, ev.id)
        process_identity_check(db, ev.id, identity_attempt_id=identity_attempt.id)
        evaluate_entry(db, ev.id)

        with pytest.raises(ValueError, match="Cannot evaluate"):
            evaluate_entry(db, ev.id)

    def test_terminal_record_cannot_restart(self, db, student, registration, entry_point, hall_ticket, seat, identity_attempt):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        begin_processing(db, ev.id)
        process_hall_ticket_check(db, ev.id)
        process_seat_check(db, ev.id)
        process_identity_check(db, ev.id, identity_attempt_id=identity_attempt.id)
        evaluate_entry(db, ev.id)

        with pytest.raises(ValueError, match="Cannot transition"):
            begin_processing(db, ev.id)


# ---------------------------------------------------------------------------
# PRIVACY
# ---------------------------------------------------------------------------

class TestPrivacy:
    def test_no_biometric_data_in_model(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        assert not hasattr(ev, "face_image")
        assert not hasattr(ev, "embedding")
        assert not hasattr(ev, "biometric_template")

    def test_no_credential_logging(self, db, student, registration, entry_point):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        assert not hasattr(ev, "secret")
        assert not hasattr(ev, "credential")


# ---------------------------------------------------------------------------
# COMPLETE WORKFLOW
# ---------------------------------------------------------------------------

class TestCompleteWorkflow:
    def test_full_granted_workflow(self, db, student, registration, entry_point, hall_ticket, seat, identity_attempt):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        assert ev.status == EntryVerificationStatus.PENDING.value

        ev = begin_processing(db, ev.id)
        assert ev.status == EntryVerificationStatus.IN_PROGRESS.value

        ev = process_hall_ticket_check(db, ev.id)
        assert ev.hall_ticket_check == HallTicketCheckStatus.PASSED.value

        ev = process_seat_check(db, ev.id)
        assert ev.seat_check == SeatCheckStatus.PASSED.value

        ev = process_identity_check(db, ev.id, identity_attempt_id=identity_attempt.id)
        assert ev.identity_check == IdentityCheckStatus.PASSED.value

        ev = evaluate_entry(db, ev.id)
        assert ev.status == EntryVerificationStatus.GRANTED.value

    def test_full_denied_workflow(self, db, student, registration, entry_point, seat, failed_identity_attempt):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        ev = begin_processing(db, ev.id)
        ev = process_hall_ticket_check(db, ev.id)
        ev = process_seat_check(db, ev.id)
        ev = process_identity_check(db, ev.id, identity_attempt_id=failed_identity_attempt.id)
        ev = evaluate_entry(db, ev.id)
        assert ev.status == EntryVerificationStatus.DENIED.value

    def test_full_escalated_workflow(self, db, student, registration, entry_point, hall_ticket, seat):
        ev = create_entry_verification(
            db,
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        ev = begin_processing(db, ev.id)
        ev = process_hall_ticket_check(db, ev.id)
        ev = process_seat_check(db, ev.id)
        ev = process_identity_check(db, ev.id)
        ev = evaluate_entry(db, ev.id)
        assert ev.status == EntryVerificationStatus.ESCALATED.value
        assert ev.escalation_reason is not None

        ev = resolve_escalation(db, ev.id, granted=True)
        assert ev.status == EntryVerificationStatus.GRANTED.value

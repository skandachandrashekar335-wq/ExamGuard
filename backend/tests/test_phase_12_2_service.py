"""Phase 12.2 — Attendance Service Layer.

Tests for attendance service functions.
Covers: record_attendance (GRANTED, DENIED, ESCALATED, PENDING, IN_PROGRESS,
idempotency, re-entry, snapshots), mark_manual_attendance, get_attendance,
list_attendance, get_entry_events, get_exam_summary, list_student_attendance_history,
concurrency, validation, privacy, and architectural safety.
"""

import pytest
from datetime import date, time
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Base
from app.models.attendance import (
    AttendanceEvent,
    AttendanceEventType,
    AttendanceRecord,
    AttendanceStatus,
    EntryMethod,
)
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
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.student import Student
from app.models.subject import Subject
from app.services.attendance.service import (
    get_attendance,
    get_entry_events,
    get_exam_summary,
    list_attendance,
    list_student_attendance_history,
    mark_manual_attendance,
    record_attendance,
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
def student2(db):
    s = Student(usn="TEST002", name="Student Two")
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
def hall2(db):
    h = ExamHall(building="TestBuilding", room_number="102", capacity=50)
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
def registration2(db, student2, exam):
    r = ExamRegistration(student_id=student2.id, exam_id=exam.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@pytest.fixture()
def entry_point(db, hall):
    ep = EntryPoint(name="Main Gate", code="MAIN_GATE", exam_hall_id=hall.id)
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


@pytest.fixture()
def ev_granted(db, student, registration, hall, entry_point):
    ev = EntryVerification(
        student_id=student.id,
        exam_registration_id=registration.id,
        exam_hall_id=hall.id,
        entry_point_id=entry_point.id,
        status=EntryVerificationStatus.GRANTED.value,
        hall_ticket_check=HallTicketCheckStatus.PASSED.value,
        identity_check=IdentityCheckStatus.PASSED.value,
        seat_check=SeatCheckStatus.PASSED.value,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


@pytest.fixture()
def ev_denied(db, student, registration, hall, entry_point):
    ev = EntryVerification(
        student_id=student.id,
        exam_registration_id=registration.id,
        exam_hall_id=hall.id,
        entry_point_id=entry_point.id,
        status=EntryVerificationStatus.DENIED.value,
        hall_ticket_check=HallTicketCheckStatus.FAILED.value,
        identity_check=IdentityCheckStatus.PASSED.value,
        seat_check=SeatCheckStatus.PASSED.value,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


@pytest.fixture()
def ev_escalated(db, student, registration, hall, entry_point):
    ev = EntryVerification(
        student_id=student.id,
        exam_registration_id=registration.id,
        exam_hall_id=hall.id,
        entry_point_id=entry_point.id,
        status=EntryVerificationStatus.ESCALATED.value,
        hall_ticket_check=HallTicketCheckStatus.PASSED.value,
        identity_check=IdentityCheckStatus.PENDING.value,
        seat_check=SeatCheckStatus.PASSED.value,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


@pytest.fixture()
def ev_pending(db, student, registration, hall, entry_point):
    ev = EntryVerification(
        student_id=student.id,
        exam_registration_id=registration.id,
        exam_hall_id=hall.id,
        entry_point_id=entry_point.id,
        status=EntryVerificationStatus.PENDING.value,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


@pytest.fixture()
def ev_in_progress(db, student, registration, hall, entry_point):
    ev = EntryVerification(
        student_id=student.id,
        exam_registration_id=registration.id,
        exam_hall_id=hall.id,
        entry_point_id=entry_point.id,
        status=EntryVerificationStatus.IN_PROGRESS.value,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


@pytest.fixture()
def seat_assignment(db, registration, hall, exam, student):
    sa = SeatAssignment(
        exam_registration_id=registration.id,
        exam_hall_id=hall.id,
        seat_number="A1",
        exam_id=exam.id,
        student_id=student.id,
    )
    db.add(sa)
    db.commit()
    db.refresh(sa)
    return sa


# ---------------------------------------------------------------------------
# record_attendance — GRANTED
# ---------------------------------------------------------------------------

class TestRecordAttendanceGranted:
    def test_granted_creates_record(self, db, ev_granted, seat_assignment):
        record = record_attendance(db, ev_granted.id)
        assert record is not None
        assert record.status == AttendanceStatus.PRESENT.value
        assert record.student_id == ev_granted.student_id
        assert record.exam_registration_id == ev_granted.exam_registration_id
        assert record.entry_verification_id == ev_granted.id
        assert record.entry_method == EntryMethod.VERIFIED_ENTRY.value

    def test_granted_creates_event(self, db, ev_granted, seat_assignment):
        record = record_attendance(db, ev_granted.id)
        events = (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.entry_verification_id == ev_granted.id)
            .all()
        )
        assert len(events) == 1
        assert events[0].event_type == AttendanceEventType.ENTRY_GRANTED.value
        assert events[0].status_snapshot == AttendanceStatus.PRESENT.value
        assert events[0].recorded_by == "system"

    def test_granted_snapshots_hall(self, db, ev_granted, seat_assignment):
        record = record_attendance(db, ev_granted.id)
        assert record.hall_id == ev_granted.exam_hall_id

    def test_granted_snapshots_seat(self, db, ev_granted, seat_assignment):
        record = record_attendance(db, ev_granted.id)
        assert record.seat_number == "A1"

    def test_granted_without_seat(self, db, ev_granted):
        record = record_attendance(db, ev_granted.id)
        assert record is not None
        assert record.seat_number is None

    def test_granted_preserves_entry_time(self, db, ev_granted, seat_assignment):
        record = record_attendance(db, ev_granted.id)
        assert record.entry_time == ev_granted.created_at

    def test_granted_sets_recorded_at(self, db, ev_granted, seat_assignment):
        record = record_attendance(db, ev_granted.id)
        assert record.recorded_at is not None


# ---------------------------------------------------------------------------
# record_attendance — DENIED
# ---------------------------------------------------------------------------

class TestRecordAttendanceDenied:
    def test_denied_returns_none(self, db, ev_denied):
        result = record_attendance(db, ev_denied.id)
        assert result is None

    def test_denied_creates_event(self, db, ev_denied):
        record_attendance(db, ev_denied.id)
        events = (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.entry_verification_id == ev_denied.id)
            .all()
        )
        assert len(events) == 1
        assert events[0].event_type == AttendanceEventType.ENTRY_DENIED.value
        assert events[0].status_snapshot == "N/A"

    def test_denied_no_record_created(self, db, ev_denied):
        record_attendance(db, ev_denied.id)
        records = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == ev_denied.exam_registration_id)
            .all()
        )
        assert len(records) == 0


# ---------------------------------------------------------------------------
# record_attendance — ESCALATED / PENDING / IN_PROGRESS
# ---------------------------------------------------------------------------

class TestRecordAttendanceInvalidStatus:
    def test_escalated_raises(self, db, ev_escalated):
        with pytest.raises(ValueError, match="ESCALATED"):
            record_attendance(db, ev_escalated.id)

    def test_pending_raises(self, db, ev_pending):
        with pytest.raises(ValueError, match="PENDING"):
            record_attendance(db, ev_pending.id)

    def test_in_progress_raises(self, db, ev_in_progress):
        with pytest.raises(ValueError, match="IN_PROGRESS"):
            record_attendance(db, ev_in_progress.id)


# ---------------------------------------------------------------------------
# record_attendance — missing EV
# ---------------------------------------------------------------------------

class TestRecordAttendanceMissingEV:
    def test_missing_ev_raises(self, db):
        with pytest.raises(LookupError, match="not found"):
            record_attendance(db, 99999)


# ---------------------------------------------------------------------------
# record_attendance — idempotency
# ---------------------------------------------------------------------------

class TestRecordAttendanceIdempotency:
    def test_same_ev_twice_returns_same_record(self, db, ev_granted, seat_assignment):
        record1 = record_attendance(db, ev_granted.id)
        record2 = record_attendance(db, ev_granted.id)
        assert record1.id == record2.id

    def test_same_ev_twice_no_duplicate_event(self, db, ev_granted, seat_assignment):
        record_attendance(db, ev_granted.id)
        record_attendance(db, ev_granted.id)
        events = (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.entry_verification_id == ev_granted.id)
            .all()
        )
        assert len(events) == 1

    def test_same_ev_twice_no_duplicate_record(self, db, ev_granted, seat_assignment):
        record_attendance(db, ev_granted.id)
        record_attendance(db, ev_granted.id)
        records = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == ev_granted.exam_registration_id)
            .all()
        )
        assert len(records) == 1

    def test_denied_idempotent(self, db, ev_denied):
        result1 = record_attendance(db, ev_denied.id)
        result2 = record_attendance(db, ev_denied.id)
        assert result1 is None
        assert result2 is None
        events = (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.entry_verification_id == ev_denied.id)
            .all()
        )
        assert len(events) == 1


# ---------------------------------------------------------------------------
# record_attendance — re-entry
# ---------------------------------------------------------------------------

class TestRecordAttendanceReEntry:
    def test_two_granted_evs_same_registration(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        ev1 = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.GRANTED.value,
            hall_ticket_check=HallTicketCheckStatus.PASSED.value,
            identity_check=IdentityCheckStatus.PASSED.value,
            seat_check=SeatCheckStatus.PASSED.value,
        )
        db.add(ev1)
        db.commit()
        db.refresh(ev1)

        ev2 = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.GRANTED.value,
            hall_ticket_check=HallTicketCheckStatus.PASSED.value,
            identity_check=IdentityCheckStatus.PASSED.value,
            seat_check=SeatCheckStatus.PASSED.value,
        )
        db.add(ev2)
        db.commit()
        db.refresh(ev2)

        record1 = record_attendance(db, ev1.id)
        record2 = record_attendance(db, ev2.id)

        # Same record (re-entry updates existing)
        assert record1.id == record2.id
        assert record2.entry_verification_id == ev2.id

        # Two events (one per EV)
        events = (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.exam_registration_id == registration.id)
            .order_by(AttendanceEvent.id)
            .all()
        )
        assert len(events) == 2
        assert events[0].entry_verification_id == ev1.id
        assert events[1].entry_verification_id == ev2.id


# ---------------------------------------------------------------------------
# get_attendance
# ---------------------------------------------------------------------------

class TestGetAttendance:
    def test_returns_record(self, db, ev_granted, seat_assignment):
        record_attendance(db, ev_granted.id)
        result = get_attendance(db, ev_granted.exam_registration.exam_id, ev_granted.student_id)
        assert result is not None
        assert result.status == AttendanceStatus.PRESENT.value

    def test_returns_none_when_no_record(self, db, exam, student):
        result = get_attendance(db, exam.id, student.id)
        assert result is None


# ---------------------------------------------------------------------------
# list_attendance
# ---------------------------------------------------------------------------

class TestListAttendance:
    def test_lists_records(self, db, ev_granted, seat_assignment):
        record_attendance(db, ev_granted.id)
        result = list_attendance(db, ev_granted.exam_registration.exam_id)
        assert result["total"] == 1
        assert len(result["items"]) == 1

    def test_filter_by_hall(self, db, ev_granted, hall, seat_assignment):
        record_attendance(db, ev_granted.id)
        result = list_attendance(db, ev_granted.exam_registration.exam_id, hall_id=hall.id)
        assert result["total"] == 1

    def test_filter_by_hall_no_match(self, db, ev_granted, hall2, seat_assignment):
        record_attendance(db, ev_granted.id)
        result = list_attendance(db, ev_granted.exam_registration.exam_id, hall_id=hall2.id)
        assert result["total"] == 0

    def test_filter_by_status(self, db, ev_granted, seat_assignment):
        record_attendance(db, ev_granted.id)
        result = list_attendance(db, ev_granted.exam_registration.exam_id, status="PRESENT")
        assert result["total"] == 1

    def test_filter_by_status_no_match(self, db, ev_granted, seat_assignment):
        record_attendance(db, ev_granted.id)
        result = list_attendance(db, ev_granted.exam_registration.exam_id, status="EXCUSED")
        assert result["total"] == 0

    def test_pagination(self, db, ev_granted, seat_assignment):
        record_attendance(db, ev_granted.id)
        result = list_attendance(db, ev_granted.exam_registration.exam_id, page=1, page_size=1)
        assert result["page"] == 1
        assert result["page_size"] == 1
        assert result["total"] == 1


# ---------------------------------------------------------------------------
# get_entry_events
# ---------------------------------------------------------------------------

class TestGetEntryEvents:
    def test_returns_events(self, db, ev_granted, seat_assignment):
        record_attendance(db, ev_granted.id)
        result = get_entry_events(db, ev_granted.id)
        assert result["total"] == 1
        assert result["items"][0].event_type == AttendanceEventType.ENTRY_GRANTED.value

    def test_returns_empty_for_no_events(self, db, ev_granted):
        result = get_entry_events(db, ev_granted.id)
        assert result["total"] == 0

    def test_pagination(self, db, ev_granted, seat_assignment):
        record_attendance(db, ev_granted.id)
        result = get_entry_events(db, ev_granted.id, page=1, page_size=10)
        assert result["page"] == 1
        assert result["page_size"] == 10


# ---------------------------------------------------------------------------
# mark_manual_attendance
# ---------------------------------------------------------------------------

class TestMarkManualAttendance:
    def test_manual_present(self, db, registration, ev_granted):
        record = mark_manual_attendance(
            db, registration.id,
            status="PRESENT",
            reason="Student arrived late",
            recorded_by="admin01",
        )
        assert record.status == AttendanceStatus.PRESENT.value
        assert record.entry_method == EntryMethod.MANUAL_ENTRY.value

    def test_manual_excused(self, db, registration, ev_granted):
        record = mark_manual_attendance(
            db, registration.id,
            status="EXCUSED",
            reason="Medical emergency",
            recorded_by="admin01",
        )
        assert record.status == AttendanceStatus.EXCUSED.value

    def test_manual_creates_event(self, db, registration, ev_granted):
        mark_manual_attendance(
            db, registration.id,
            status="PRESENT",
            reason="Student arrived late",
            recorded_by="admin01",
        )
        events = (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.exam_registration_id == registration.id)
            .all()
        )
        assert len(events) == 1
        assert events[0].event_type == AttendanceEventType.ATTENDANCE_CORRECTED.value
        assert events[0].recorded_by == "admin01"
        assert events[0].reason == "Student arrived late"

    def test_manual_invalid_status_raises(self, db, registration, ev_granted):
        with pytest.raises(ValueError, match="Invalid status"):
            mark_manual_attendance(
                db, registration.id,
                status="ABSENT",
                reason="Some reason",
                recorded_by="admin01",
            )

    def test_manual_cancelled_registration_raises(self, db, student2, exam, ev_granted):
        reg = ExamRegistration(student_id=student2.id, exam_id=exam.id)
        reg.status = RegistrationStatus.CANCELLED.value
        db.add(reg)
        db.commit()
        db.refresh(reg)

        with pytest.raises(ValueError, match="cancelled"):
            mark_manual_attendance(
                db, reg.id,
                status="PRESENT",
                reason="Some reason",
                recorded_by="admin01",
            )

    def test_manual_empty_reason_raises(self, db, registration, ev_granted):
        with pytest.raises(ValueError, match="Reason is required"):
            mark_manual_attendance(
                db, registration.id,
                status="PRESENT",
                reason="",
                recorded_by="admin01",
            )

    def test_manual_empty_recorded_by_raises(self, db, registration, ev_granted):
        with pytest.raises(ValueError, match="recorded_by is required"):
            mark_manual_attendance(
                db, registration.id,
                status="PRESENT",
                reason="Some reason",
                recorded_by="",
            )

    def test_manual_no_ev_raises(self, db, student, exam):
        reg = ExamRegistration(student_id=student.id, exam_id=exam.id)
        db.add(reg)
        db.commit()
        db.refresh(reg)

        with pytest.raises(ValueError, match="No entry verification"):
            mark_manual_attendance(
                db, reg.id,
                status="PRESENT",
                reason="Some reason",
                recorded_by="admin01",
            )

    def test_manual_updates_existing_record(self, db, registration, ev_granted, seat_assignment):
        record_attendance(db, ev_granted.id)
        record = mark_manual_attendance(
            db, registration.id,
            status="EXCUSED",
            reason="Medical emergency",
            recorded_by="admin01",
        )
        assert record.status == AttendanceStatus.EXCUSED.value
        assert record.entry_method == EntryMethod.MANUAL_ENTRY.value


# ---------------------------------------------------------------------------
# get_exam_summary
# ---------------------------------------------------------------------------

class TestGetExamSummary:
    def test_empty_exam(self, db, exam):
        summary = get_exam_summary(db, exam.id)
        assert summary["total_registered"] == 0
        assert summary["total_present"] == 0
        assert summary["total_absent"] == 0
        assert summary["total_excused"] == 0
        assert summary["attendance_rate"] == 0.0

    def test_with_present(self, db, exam, registration, ev_granted, seat_assignment):
        record_attendance(db, ev_granted.id)
        summary = get_exam_summary(db, exam.id)
        assert summary["total_registered"] == 1
        assert summary["total_present"] == 1
        assert summary["total_absent"] == 0
        assert summary["attendance_rate"] == 100.0

    def test_absent_computed(self, db, exam, registration, ev_denied):
        record_attendance(db, ev_denied.id)
        summary = get_exam_summary(db, exam.id)
        assert summary["total_registered"] == 1
        assert summary["total_present"] == 0
        assert summary["total_absent"] == 1

    def test_by_hall(self, db, exam, registration, ev_granted, hall, seat_assignment):
        record_attendance(db, ev_granted.id)
        summary = get_exam_summary(db, exam.id)
        assert len(summary["by_hall"]) == 1
        assert summary["by_hall"][0]["hall_id"] == hall.id
        assert summary["by_hall"][0]["present"] == 1

    def test_missing_exam_raises(self, db):
        with pytest.raises(LookupError, match="not found"):
            get_exam_summary(db, 99999)


# ---------------------------------------------------------------------------
# list_student_attendance_history
# ---------------------------------------------------------------------------

class TestListStudentAttendanceHistory:
    def test_returns_history(self, db, student, ev_granted, seat_assignment):
        record_attendance(db, ev_granted.id)
        result = list_student_attendance_history(db, student.id)
        assert result["total"] == 1

    def test_empty_history(self, db, student):
        result = list_student_attendance_history(db, student.id)
        assert result["total"] == 0

    def test_missing_student_raises(self, db):
        with pytest.raises(LookupError, match="not found"):
            list_student_attendance_history(db, 99999)

    def test_pagination(self, db, student, ev_granted, seat_assignment):
        record_attendance(db, ev_granted.id)
        result = list_student_attendance_history(db, student.id, page=1, page_size=5)
        assert result["page"] == 1
        assert result["page_size"] == 5


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------

class TestConcurrency:
    def test_two_granted_evs_same_registration(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        ev1 = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.GRANTED.value,
            hall_ticket_check=HallTicketCheckStatus.PASSED.value,
            identity_check=IdentityCheckStatus.PASSED.value,
            seat_check=SeatCheckStatus.PASSED.value,
        )
        db.add(ev1)
        db.commit()
        db.refresh(ev1)

        ev2 = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.GRANTED.value,
            hall_ticket_check=HallTicketCheckStatus.PASSED.value,
            identity_check=IdentityCheckStatus.PASSED.value,
            seat_check=SeatCheckStatus.PASSED.value,
        )
        db.add(ev2)
        db.commit()
        db.refresh(ev2)

        record1 = record_attendance(db, ev1.id)
        record2 = record_attendance(db, ev2.id)

        # One record, updated
        assert record1.id == record2.id
        assert record2.entry_verification_id == ev2.id

        # Two events
        events = (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.exam_registration_id == registration.id)
            .all()
        )
        assert len(events) == 2


# ---------------------------------------------------------------------------
# Architectural Safety
# ---------------------------------------------------------------------------

class TestArchitecturalSafety:
    def test_record_attendance_does_not_modify_ev_status(self, db, ev_granted, seat_assignment):
        original_status = ev_granted.status
        record_attendance(db, ev_granted.id)
        db.refresh(ev_granted)
        assert ev_granted.status == original_status

    def test_manual_does_not_modify_ev_status(self, db, registration, ev_granted):
        original_status = ev_granted.status
        mark_manual_attendance(
            db, registration.id,
            status="PRESENT",
            reason="Late arrival",
            recorded_by="admin01",
        )
        db.refresh(ev_granted)
        assert ev_granted.status == original_status

    def test_no_biometric_data_in_record(self):
        columns = [c.name for c in AttendanceRecord.__table__.columns]
        forbidden = ["face_image", "embedding", "biometric", "face_data"]
        for f in forbidden:
            assert f not in columns

    def test_no_biometric_data_in_event(self):
        columns = [c.name for c in AttendanceEvent.__table__.columns]
        forbidden = ["face_image", "embedding", "biometric", "face_data"]
        for f in forbidden:
            assert f not in columns


# ---------------------------------------------------------------------------
# Privacy
# ---------------------------------------------------------------------------

class TestPrivacy:
    def test_no_credentials_in_record(self):
        columns = [c.name for c in AttendanceRecord.__table__.columns]
        forbidden = ["api_key", "secret", "password", "token"]
        for f in forbidden:
            assert f not in columns

    def test_no_credentials_in_event(self):
        columns = [c.name for c in AttendanceEvent.__table__.columns]
        forbidden = ["api_key", "secret", "password", "token"]
        for f in forbidden:
            assert f not in columns

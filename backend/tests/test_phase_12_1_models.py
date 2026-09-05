"""Phase 12.1 — Attendance Domain & Database Foundation.

Tests for AttendanceRecord and AttendanceEvent models and associated enums.
Covers: creation, defaults, FK relationships, nullable fields, timestamps,
enum persistence, unique constraints, idempotency, snapshot semantics,
model registration, and historical-record safety.
"""

import pytest
from datetime import date, datetime, time, timezone
from sqlalchemy import create_engine, inspect
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
from app.models.exam_registration import ExamRegistration
from app.models.seat_assignment import SeatAssignment
from app.models.student import Student
from app.models.subject import Subject


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
def entry_point(db, hall):
    ep = EntryPoint(name="Main Gate", code="MAIN_GATE", exam_hall_id=hall.id)
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


@pytest.fixture()
def entry_verification(db, student, registration, hall, entry_point):
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
def entry_verification_2(db, student, registration, hall, entry_point):
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
# Enum Tests
# ---------------------------------------------------------------------------

class TestAttendanceStatusEnum:
    def test_has_required_values(self):
        assert AttendanceStatus.PRESENT.value == "PRESENT"
        assert AttendanceStatus.ABSENT.value == "ABSENT"
        assert AttendanceStatus.EXCUSED.value == "EXCUSED"

    def test_string_enum(self):
        assert isinstance(AttendanceStatus.PRESENT, str)
        assert AttendanceStatus.PRESENT == "PRESENT"

    def test_all_values_unique(self):
        values = [s.value for s in AttendanceStatus]
        assert len(values) == len(set(values))


class TestEntryMethodEnum:
    def test_has_required_values(self):
        assert EntryMethod.VERIFIED_ENTRY.value == "VERIFIED_ENTRY"
        assert EntryMethod.MANUAL_ENTRY.value == "MANUAL_ENTRY"

    def test_string_enum(self):
        assert isinstance(EntryMethod.VERIFIED_ENTRY, str)
        assert EntryMethod.VERIFIED_ENTRY == "VERIFIED_ENTRY"

    def test_all_values_unique(self):
        values = [m.value for m in EntryMethod]
        assert len(values) == len(set(values))


class TestAttendanceEventTypeEnum:
    def test_has_required_values(self):
        assert AttendanceEventType.ENTRY_GRANTED.value == "ENTRY_GRANTED"
        assert AttendanceEventType.ENTRY_DENIED.value == "ENTRY_DENIED"
        assert AttendanceEventType.ENTRY_ESCALATED.value == "ENTRY_ESCALATED"
        assert AttendanceEventType.ATTENDANCE_RECORDED.value == "ATTENDANCE_RECORDED"
        assert AttendanceEventType.ATTENDANCE_CORRECTED.value == "ATTENDANCE_CORRECTED"
        assert AttendanceEventType.ATTENDANCE_EXCUSED.value == "ATTENDANCE_EXCUSED"

    def test_string_enum(self):
        assert isinstance(AttendanceEventType.ENTRY_GRANTED, str)
        assert AttendanceEventType.ENTRY_GRANTED == "ENTRY_GRANTED"

    def test_all_values_unique(self):
        values = [e.value for e in AttendanceEventType]
        assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# AttendanceRecord Tests
# ---------------------------------------------------------------------------

class TestAttendanceRecordCreation:
    def test_create_record(self, db, student, exam, registration, entry_verification, hall):
        record = AttendanceRecord(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            status=AttendanceStatus.PRESENT.value,
            entry_verification_id=entry_verification.id,
            entry_method=EntryMethod.VERIFIED_ENTRY.value,
            entry_time=entry_verification.created_at,
            hall_id=hall.id,
            seat_number="A1",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        assert record.id is not None
        assert record.student_id == student.id
        assert record.exam_id == exam.id
        assert record.exam_registration_id == registration.id
        assert record.status == AttendanceStatus.PRESENT.value
        assert record.entry_verification_id == entry_verification.id
        assert record.entry_method == EntryMethod.VERIFIED_ENTRY.value
        assert record.seat_number == "A1"

    def test_record_has_timestamps(self, db, student, exam, registration, entry_verification, hall):
        record = AttendanceRecord(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            status=AttendanceStatus.PRESENT.value,
            entry_verification_id=entry_verification.id,
            entry_method=EntryMethod.VERIFIED_ENTRY.value,
            entry_time=entry_verification.created_at,
            hall_id=hall.id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        assert record.recorded_at is not None
        assert record.updated_at is not None

    def test_record_repr(self, db, student, exam, registration, entry_verification, hall):
        record = AttendanceRecord(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            status=AttendanceStatus.PRESENT.value,
            entry_verification_id=entry_verification.id,
            entry_method=EntryMethod.VERIFIED_ENTRY.value,
            entry_time=entry_verification.created_at,
            hall_id=hall.id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        r = repr(record)
        assert "AttendanceRecord" in r
        assert f"student_id={student.id}" in r
        assert f"exam_id={exam.id}" in r
        assert "PRESENT" in r

    def test_seat_number_nullable(self, db, student, exam, registration, entry_verification, hall):
        record = AttendanceRecord(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            status=AttendanceStatus.PRESENT.value,
            entry_verification_id=entry_verification.id,
            entry_method=EntryMethod.VERIFIED_ENTRY.value,
            entry_time=entry_verification.created_at,
            hall_id=hall.id,
            seat_number=None,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        assert record.seat_number is None


class TestAttendanceRecordRelationships:
    def test_relationships_accessible(self, db, student, exam, registration, entry_verification, hall):
        record = AttendanceRecord(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            status=AttendanceStatus.PRESENT.value,
            entry_verification_id=entry_verification.id,
            entry_method=EntryMethod.VERIFIED_ENTRY.value,
            entry_time=entry_verification.created_at,
            hall_id=hall.id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        assert record.student.id == student.id
        assert record.exam.id == exam.id
        assert record.registration.id == registration.id
        assert record.entry_verification.id == entry_verification.id
        assert record.hall.id == hall.id


class TestAttendanceRecordUniqueness:
    def test_one_record_per_registration(self, db, student, exam, registration, entry_verification, hall):
        record1 = AttendanceRecord(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            status=AttendanceStatus.PRESENT.value,
            entry_verification_id=entry_verification.id,
            entry_method=EntryMethod.VERIFIED_ENTRY.value,
            entry_time=entry_verification.created_at,
            hall_id=hall.id,
        )
        db.add(record1)
        db.commit()

        record2 = AttendanceRecord(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            status=AttendanceStatus.PRESENT.value,
            entry_verification_id=entry_verification.id,
            entry_method=EntryMethod.VERIFIED_ENTRY.value,
            entry_time=entry_verification.created_at,
            hall_id=hall.id,
        )
        db.add(record2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_different_registrations_can_have_records(
        self, db, student, exam, hall, registration, entry_verification
    ):
        student2 = Student(usn="TEST002", name="Student Two")
        db.add(student2)
        db.commit()
        db.refresh(student2)

        reg2 = ExamRegistration(student_id=student2.id, exam_id=exam.id)
        db.add(reg2)
        db.commit()
        db.refresh(reg2)

        record1 = AttendanceRecord(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            status=AttendanceStatus.PRESENT.value,
            entry_verification_id=entry_verification.id,
            entry_method=EntryMethod.VERIFIED_ENTRY.value,
            entry_time=entry_verification.created_at,
            hall_id=hall.id,
        )
        db.add(record1)
        db.commit()

        record2 = AttendanceRecord(
            student_id=student2.id,
            exam_id=exam.id,
            exam_registration_id=reg2.id,
            status=AttendanceStatus.PRESENT.value,
            entry_verification_id=entry_verification.id,
            entry_method=EntryMethod.VERIFIED_ENTRY.value,
            entry_time=entry_verification.created_at,
            hall_id=hall.id,
        )
        db.add(record2)
        db.commit()
        assert record1.id != record2.id


class TestAttendanceRecordStatusValues:
    def test_status_persists(self, db, student, exam, registration, entry_verification, hall):
        for status in AttendanceStatus:
            record = AttendanceRecord(
                student_id=student.id,
                exam_id=exam.id,
                exam_registration_id=registration.id,
                status=status.value,
                entry_verification_id=entry_verification.id,
                entry_method=EntryMethod.VERIFIED_ENTRY.value,
                entry_time=entry_verification.created_at,
                hall_id=hall.id,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            assert record.status == status.value
            db.delete(record)
            db.commit()


class TestAttendanceRecordSnapshotSemantics:
    def test_hall_id_is_snapshot(self, db, student, exam, registration, entry_verification, hall, seat_assignment):
        record = AttendanceRecord(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            status=AttendanceStatus.PRESENT.value,
            entry_verification_id=entry_verification.id,
            entry_method=EntryMethod.VERIFIED_ENTRY.value,
            entry_time=entry_verification.created_at,
            hall_id=hall.id,
            seat_number=seat_assignment.seat_number,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        assert record.hall_id == hall.id
        assert record.seat_number == seat_assignment.seat_number


# ---------------------------------------------------------------------------
# AttendanceEvent Tests
# ---------------------------------------------------------------------------

class TestAttendanceEventCreation:
    def test_create_event(self, db, student, exam, registration, entry_verification):
        event = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification.id,
            event_type=AttendanceEventType.ENTRY_GRANTED.value,
            status_snapshot=AttendanceStatus.PRESENT.value,
            recorded_by="system",
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        assert event.id is not None
        assert event.student_id == student.id
        assert event.exam_id == exam.id
        assert event.exam_registration_id == registration.id
        assert event.entry_verification_id == entry_verification.id
        assert event.event_type == AttendanceEventType.ENTRY_GRANTED.value
        assert event.status_snapshot == AttendanceStatus.PRESENT.value
        assert event.recorded_by == "system"

    def test_event_has_timestamps(self, db, student, exam, registration, entry_verification):
        event = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification.id,
            event_type=AttendanceEventType.ENTRY_GRANTED.value,
            status_snapshot=AttendanceStatus.PRESENT.value,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        assert event.created_at is not None

    def test_event_repr(self, db, student, exam, registration, entry_verification):
        event = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification.id,
            event_type=AttendanceEventType.ENTRY_GRANTED.value,
            status_snapshot=AttendanceStatus.PRESENT.value,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        r = repr(event)
        assert "AttendanceEvent" in r
        assert f"student_id={student.id}" in r
        assert "ENTRY_GRANTED" in r

    def test_recorded_by_nullable(self, db, student, exam, registration, entry_verification):
        event = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification.id,
            event_type=AttendanceEventType.ENTRY_GRANTED.value,
            status_snapshot=AttendanceStatus.PRESENT.value,
            recorded_by=None,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        assert event.recorded_by is None

    def test_reason_nullable(self, db, student, exam, registration, entry_verification):
        event = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification.id,
            event_type=AttendanceEventType.ENTRY_GRANTED.value,
            status_snapshot=AttendanceStatus.PRESENT.value,
            reason=None,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        assert event.reason is None

    def test_event_with_reason(self, db, student, exam, registration, entry_verification):
        event = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification.id,
            event_type=AttendanceEventType.ATTENDANCE_CORRECTED.value,
            status_snapshot=AttendanceStatus.EXCUSED.value,
            recorded_by="admin01",
            reason="Student had medical emergency",
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        assert event.reason == "Student had medical emergency"
        assert event.recorded_by == "admin01"


class TestAttendanceEventRelationships:
    def test_relationships_accessible(self, db, student, exam, registration, entry_verification):
        event = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification.id,
            event_type=AttendanceEventType.ENTRY_GRANTED.value,
            status_snapshot=AttendanceStatus.PRESENT.value,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        assert event.student.id == student.id
        assert event.exam.id == exam.id
        assert event.registration.id == registration.id
        assert event.entry_verification.id == entry_verification.id


class TestAttendanceEventMultiEvent:
    def test_multiple_events_allowed_for_same_ev(self, db, student, exam, registration, entry_verification):
        """Multiple events per EV are now allowed for audit trail (corrections, etc.)."""
        event1 = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification.id,
            event_type=AttendanceEventType.ENTRY_GRANTED.value,
            status_snapshot=AttendanceStatus.PRESENT.value,
        )
        db.add(event1)
        db.commit()

        event2 = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification.id,
            event_type=AttendanceEventType.ATTENDANCE_CORRECTED.value,
            status_snapshot=AttendanceStatus.EXCUSED.value,
        )
        db.add(event2)
        db.commit()

        events = db.query(AttendanceEvent).filter(
            AttendanceEvent.entry_verification_id == entry_verification.id
        ).all()
        assert len(events) == 2

    def test_different_evs_can_have_events(
        self, db, student, exam, registration, entry_verification, entry_verification_2
    ):
        event1 = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification.id,
            event_type=AttendanceEventType.ENTRY_GRANTED.value,
            status_snapshot=AttendanceStatus.PRESENT.value,
        )
        db.add(event1)
        db.commit()

        event2 = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification_2.id,
            event_type=AttendanceEventType.ENTRY_GRANTED.value,
            status_snapshot=AttendanceStatus.PRESENT.value,
        )
        db.add(event2)
        db.commit()
        assert event1.id != event2.id


class TestAttendanceEventTypeValues:
    def test_all_event_types_persist(self, db, student, exam, registration, entry_verification):
        for event_type in AttendanceEventType:
            event = AttendanceEvent(
                student_id=student.id,
                exam_id=exam.id,
                exam_registration_id=registration.id,
                entry_verification_id=entry_verification.id,
                event_type=event_type.value,
                status_snapshot=AttendanceStatus.PRESENT.value,
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            assert event.event_type == event_type.value
            db.delete(event)
            db.commit()


# ---------------------------------------------------------------------------
# Multiple Events Across Registrations
# ---------------------------------------------------------------------------

class TestMultipleEventsAcrossRegistrations:
    def test_multiple_different_evs_same_registration(
        self, db, student, exam, registration, entry_verification, entry_verification_2
    ):
        event1 = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification.id,
            event_type=AttendanceEventType.ENTRY_GRANTED.value,
            status_snapshot=AttendanceStatus.PRESENT.value,
        )
        db.add(event1)
        db.commit()

        event2 = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification_2.id,
            event_type=AttendanceEventType.ENTRY_GRANTED.value,
            status_snapshot=AttendanceStatus.PRESENT.value,
        )
        db.add(event2)
        db.commit()

        events = (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.exam_registration_id == registration.id)
            .all()
        )
        assert len(events) == 2


# ---------------------------------------------------------------------------
# Privacy Tests
# ---------------------------------------------------------------------------

class TestAttendancePrivacy:
    def test_no_biometric_fields_in_record(self):
        import inspect
        columns = [c.name for c in AttendanceRecord.__table__.columns]
        forbidden = ["face_image", "embedding", "biometric", "face_data", "raw_image"]
        for f in forbidden:
            assert f not in columns, f"AttendanceRecord should not contain {f}"

    def test_no_biometric_fields_in_event(self):
        import inspect
        columns = [c.name for c in AttendanceEvent.__table__.columns]
        forbidden = ["face_image", "embedding", "biometric", "face_data", "raw_image"]
        for f in forbidden:
            assert f not in columns, f"AttendanceEvent should not contain {f}"

    def test_no_credentials_in_record(self):
        columns = [c.name for c in AttendanceRecord.__table__.columns]
        forbidden = ["api_key", "secret", "password", "token"]
        for f in forbidden:
            assert f not in columns, f"AttendanceRecord should not contain {f}"

    def test_no_credentials_in_event(self):
        columns = [c.name for c in AttendanceEvent.__table__.columns]
        forbidden = ["api_key", "secret", "password", "token"]
        for f in forbidden:
            assert f not in columns, f"AttendanceEvent should not contain {f}"


# ---------------------------------------------------------------------------
# Model Registration Tests
# ---------------------------------------------------------------------------

class TestModelRegistration:
    def test_attendance_record_in_metadata(self):
        assert "attendance_records" in Base.metadata.tables

    def test_attendance_event_in_metadata(self):
        assert "attendance_events" in Base.metadata.tables

    def test_attendance_record_columns(self):
        table = Base.metadata.tables["attendance_records"]
        expected = {
            "id", "student_id", "exam_id", "exam_registration_id",
            "status", "entry_verification_id", "entry_method", "entry_time",
            "hall_id", "session_id", "seat_number", "recorded_at", "updated_at",
        }
        actual = {c.name for c in table.columns}
        assert expected == actual

    def test_attendance_event_columns(self):
        table = Base.metadata.tables["attendance_events"]
        expected = {
            "id", "student_id", "exam_id", "exam_registration_id",
            "entry_verification_id", "event_type", "status_snapshot",
            "recorded_by", "reason", "created_at",
        }
        actual = {c.name for c in table.columns}
        assert expected == actual


# ---------------------------------------------------------------------------
# Index Tests
# ---------------------------------------------------------------------------

class TestIndexes:
    def test_record_indexes(self):
        table = Base.metadata.tables["attendance_records"]
        indexed_columns = {
            c.name for c in table.columns if c.index
        }
        assert "student_id" in indexed_columns
        assert "exam_id" in indexed_columns
        assert "exam_registration_id" in indexed_columns
        assert "status" in indexed_columns
        assert "entry_verification_id" in indexed_columns
        assert "hall_id" in indexed_columns

    def test_event_indexes(self):
        table = Base.metadata.tables["attendance_events"]
        indexed_columns = {
            c.name for c in table.columns if c.index
        }
        assert "student_id" in indexed_columns
        assert "exam_id" in indexed_columns
        assert "exam_registration_id" in indexed_columns
        assert "entry_verification_id" in indexed_columns
        assert "event_type" in indexed_columns
        assert "created_at" in indexed_columns


# ---------------------------------------------------------------------------
# Constraint Tests
# ---------------------------------------------------------------------------

class TestConstraints:
    def test_record_unique_constraint_exists(self):
        table = Base.metadata.tables["attendance_records"]
        constraint_names = [uc.name for uc in table.constraints if uc.name and "uq" in uc.name]
        assert "uq_attendance_record_per_registration" in constraint_names

    def test_event_no_unique_constraint_on_ev_id(self):
        """UNIQUE constraint on entry_verification_id was dropped in migration 023
        to allow multiple events per EV for audit trail."""
        table = Base.metadata.tables["attendance_events"]
        constraint_names = [uc.name for uc in table.constraints if uc.name and "uq" in uc.name]
        assert "uq_attendance_event_per_entry_verification" not in constraint_names


# ---------------------------------------------------------------------------
# History Preservation Tests
# ---------------------------------------------------------------------------

class TestHistoryPreservation:
    def test_multiple_events_for_different_evs_same_registration(
        self, db, student, exam, registration, entry_verification, entry_verification_2
    ):
        event1 = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification.id,
            event_type=AttendanceEventType.ENTRY_GRANTED.value,
            status_snapshot=AttendanceStatus.PRESENT.value,
        )
        db.add(event1)
        db.commit()

        event2 = AttendanceEvent(
            student_id=student.id,
            exam_id=exam.id,
            exam_registration_id=registration.id,
            entry_verification_id=entry_verification_2.id,
            event_type=AttendanceEventType.ENTRY_GRANTED.value,
            status_snapshot=AttendanceStatus.PRESENT.value,
        )
        db.add(event2)
        db.commit()

        all_events = (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.exam_registration_id == registration.id)
            .order_by(AttendanceEvent.id)
            .all()
        )
        assert len(all_events) == 2
        assert all_events[0].entry_verification_id == entry_verification.id
        assert all_events[1].entry_verification_id == entry_verification_2.id

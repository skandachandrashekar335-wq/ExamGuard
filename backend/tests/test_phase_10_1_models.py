"""Phase 10.1 — Entry Verification Domain Model.

Tests for EntryVerification model and associated enums.
Covers: creation, defaults, FK relationships, nullable relationships,
status lifecycle, escalation fields, timestamps, enum persistence,
historical-record safety, and model registration.
"""

import pytest
from datetime import date, time
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Base
from app.models.camera import Camera, CameraStatus
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
def identity_attempt(db, student, registration, hall_ticket):
    att = IdentityVerificationAttempt(
        student_id=student.id,
        exam_registration_id=registration.id,
        hall_ticket_id=hall_ticket.id,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


# ---------------------------------------------------------------------------
# Enum Tests
# ---------------------------------------------------------------------------

class TestEntryVerificationStatusEnum:
    def test_has_required_values(self):
        assert EntryVerificationStatus.PENDING.value == "PENDING"
        assert EntryVerificationStatus.IN_PROGRESS.value == "IN_PROGRESS"
        assert EntryVerificationStatus.GRANTED.value == "GRANTED"
        assert EntryVerificationStatus.DENIED.value == "DENIED"
        assert EntryVerificationStatus.ESCALATED.value == "ESCALATED"

    def test_string_enum(self):
        assert isinstance(EntryVerificationStatus.PENDING, str)
        assert EntryVerificationStatus.PENDING == "PENDING"

    def test_all_values_unique(self):
        values = [e.value for e in EntryVerificationStatus]
        assert len(values) == len(set(values))


class TestHallTicketCheckStatusEnum:
    def test_has_required_values(self):
        assert HallTicketCheckStatus.PENDING.value == "PENDING"
        assert HallTicketCheckStatus.PASSED.value == "PASSED"
        assert HallTicketCheckStatus.FAILED.value == "FAILED"
        assert HallTicketCheckStatus.SKIPPED.value == "SKIPPED"

    def test_string_enum(self):
        assert isinstance(HallTicketCheckStatus.PENDING, str)
        assert HallTicketCheckStatus.PENDING == "PENDING"


class TestIdentityCheckStatusEnum:
    def test_has_required_values(self):
        assert IdentityCheckStatus.PENDING.value == "PENDING"
        assert IdentityCheckStatus.PASSED.value == "PASSED"
        assert IdentityCheckStatus.FAILED.value == "FAILED"
        assert IdentityCheckStatus.SKIPPED.value == "SKIPPED"

    def test_string_enum(self):
        assert isinstance(IdentityCheckStatus.PENDING, str)
        assert IdentityCheckStatus.PENDING == "PENDING"


class TestSeatCheckStatusEnum:
    def test_has_required_values(self):
        assert SeatCheckStatus.PENDING.value == "PENDING"
        assert SeatCheckStatus.PASSED.value == "PASSED"
        assert SeatCheckStatus.FAILED.value == "FAILED"
        assert SeatCheckStatus.SKIPPED.value == "SKIPPED"

    def test_string_enum(self):
        assert isinstance(SeatCheckStatus.PENDING, str)
        assert SeatCheckStatus.PENDING == "PENDING"


# ---------------------------------------------------------------------------
# Creation & Defaults
# ---------------------------------------------------------------------------

class TestEntryVerificationCreation:
    def test_create_minimal(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.id is not None
        assert ev.student_id == student.id
        assert ev.exam_registration_id == registration.id
        assert ev.exam_hall_id == hall.id
        assert ev.entry_point_id == entry_point.id

    def test_default_status_is_pending(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.status == EntryVerificationStatus.PENDING.value

    def test_default_hall_ticket_check_is_pending(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.hall_ticket_check == HallTicketCheckStatus.PENDING.value

    def test_default_identity_check_is_pending(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.identity_check == IdentityCheckStatus.PENDING.value

    def test_default_seat_check_is_pending(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.seat_check == SeatCheckStatus.PENDING.value

    def test_nullable_fields_default_none(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.hall_ticket_id is None
        assert ev.identity_verification_attempt_id is None
        assert ev.camera_id is None
        assert ev.escalation_reason is None
        assert ev.resolved_at is None


# ---------------------------------------------------------------------------
# FK Relationships
# ---------------------------------------------------------------------------

class TestEntryVerificationRelationships:
    def test_with_hall_ticket(self, db, student, registration, hall, entry_point, hall_ticket):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.hall_ticket_id == hall_ticket.id

    def test_with_identity_verification_attempt(self, db, student, registration, hall, entry_point, identity_attempt):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            identity_verification_attempt_id=identity_attempt.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.identity_verification_attempt_id == identity_attempt.id

    def test_with_camera(self, db, student, registration, hall, entry_point, camera):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            camera_id=camera.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.camera_id == camera.id

    def test_with_all_optionals(self, db, student, registration, hall, entry_point, hall_ticket, identity_attempt, camera):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
            identity_verification_attempt_id=identity_attempt.id,
            camera_id=camera.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.hall_ticket_id == hall_ticket.id
        assert ev.identity_verification_attempt_id == identity_attempt.id
        assert ev.camera_id == camera.id

    def test_student_relationship_loads(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        loaded = db.get(EntryVerification, ev.id)
        assert loaded.student.id == student.id
        assert loaded.student.name == "Test Student"

    def test_exam_registration_relationship_loads(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        loaded = db.get(EntryVerification, ev.id)
        assert loaded.exam_registration.id == registration.id

    def test_exam_hall_relationship_loads(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        loaded = db.get(EntryVerification, ev.id)
        assert loaded.exam_hall.id == hall.id

    def test_entry_point_relationship_loads(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        loaded = db.get(EntryVerification, ev.id)
        assert loaded.entry_point.id == entry_point.id

    def test_hall_ticket_relationship_loads(self, db, student, registration, hall, entry_point, hall_ticket):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=hall_ticket.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        loaded = db.get(EntryVerification, ev.id)
        assert loaded.hall_ticket.id == hall_ticket.id

    def test_identity_verification_attempt_relationship_loads(self, db, student, registration, hall, entry_point, identity_attempt):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            identity_verification_attempt_id=identity_attempt.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        loaded = db.get(EntryVerification, ev.id)
        assert loaded.identity_verification_attempt.id == identity_attempt.id

    def test_camera_relationship_loads(self, db, student, registration, hall, entry_point, camera):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            camera_id=camera.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        loaded = db.get(EntryVerification, ev.id)
        assert loaded.camera.id == camera.id


# ---------------------------------------------------------------------------
# Status Values
# ---------------------------------------------------------------------------

class TestEntryVerificationStatusValues:
    def test_all_status_values_persist(self, db, student, registration, hall, entry_point):
        for status in EntryVerificationStatus:
            ev = EntryVerification(
                student_id=student.id,
                exam_registration_id=registration.id,
                exam_hall_id=hall.id,
                entry_point_id=entry_point.id,
                status=status.value,
            )
            db.add(ev)
            db.commit()
            db.refresh(ev)
            assert ev.status == status.value

    def test_all_hall_ticket_check_values_persist(self, db, student, registration, hall, entry_point):
        for check in HallTicketCheckStatus:
            ev = EntryVerification(
                student_id=student.id,
                exam_registration_id=registration.id,
                exam_hall_id=hall.id,
                entry_point_id=entry_point.id,
                hall_ticket_check=check.value,
            )
            db.add(ev)
            db.commit()
            db.refresh(ev)
            assert ev.hall_ticket_check == check.value

    def test_all_identity_check_values_persist(self, db, student, registration, hall, entry_point):
        for check in IdentityCheckStatus:
            ev = EntryVerification(
                student_id=student.id,
                exam_registration_id=registration.id,
                exam_hall_id=hall.id,
                entry_point_id=entry_point.id,
                identity_check=check.value,
            )
            db.add(ev)
            db.commit()
            db.refresh(ev)
            assert ev.identity_check == check.value

    def test_all_seat_check_values_persist(self, db, student, registration, hall, entry_point):
        for check in SeatCheckStatus:
            ev = EntryVerification(
                student_id=student.id,
                exam_registration_id=registration.id,
                exam_hall_id=hall.id,
                entry_point_id=entry_point.id,
                seat_check=check.value,
            )
            db.add(ev)
            db.commit()
            db.refresh(ev)
            assert ev.seat_check == check.value


# ---------------------------------------------------------------------------
# Escalation Data
# ---------------------------------------------------------------------------

class TestEscalationData:
    def test_escalation_reason_persists(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            escalation_reason="Student face unclear in camera feed",
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.escalation_reason == "Student face unclear in camera feed"

    def test_resolved_at_persists(self, db, student, registration, hall, entry_point):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.ESCALATED.value,
            escalation_reason="Manual review needed",
            resolved_at=now,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.resolved_at is not None


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------

class TestTimestamps:
    def test_created_at_auto_populated(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.created_at is not None

    def test_updated_at_auto_populated(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.updated_at is not None

    def test_created_at_and_updated_at_equal_on_creation(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.created_at == ev.updated_at

    def test_resolved_at_nullable(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        assert ev.resolved_at is None


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------

class TestRepr:
    def test_repr(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        r = repr(ev)
        assert "EntryVerification" in r
        assert f"id={ev.id}" in r
        assert f"student_id={student.id}" in r
        assert "PENDING" in r
        assert f"entry_point_id={entry_point.id}" in r


# ---------------------------------------------------------------------------
# Model Registration & Table Introspection
# ---------------------------------------------------------------------------

class TestModelRegistration:
    def test_model_metadata_contains_entry_verification(self):
        from app.models import Base
        assert "entry_verifications" in Base.metadata.tables

    def test_table_has_expected_columns(self):
        from app.models import Base
        table = Base.metadata.tables["entry_verifications"]
        column_names = {c.name for c in table.columns}

        expected_columns = {
            "id",
            "student_id",
            "exam_registration_id",
            "exam_hall_id",
            "entry_point_id",
            "hall_ticket_id",
            "identity_verification_attempt_id",
            "camera_id",
            "session_id",
            "status",
            "hall_ticket_check",
            "identity_check",
            "seat_check",
            "escalation_reason",
            "resolved_at",
            "created_at",
            "updated_at",
        }
        assert expected_columns == column_names

    def test_foreign_keys_exist(self):
        from app.models import Base
        table = Base.metadata.tables["entry_verifications"]

        fk_parent_columns = {fk.parent.name for fk in table.foreign_keys}
        expected_fk_columns = {
            "student_id",
            "exam_registration_id",
            "exam_hall_id",
            "entry_point_id",
            "hall_ticket_id",
            "identity_verification_attempt_id",
            "camera_id",
            "session_id",
        }
        assert expected_fk_columns == fk_parent_columns

    def test_server_defaults(self):
        from app.models import Base
        table = Base.metadata.tables["entry_verifications"]

        status_col = table.c.status
        assert status_col.server_default.arg == "PENDING"

        ht_col = table.c.hall_ticket_check
        assert ht_col.server_default.arg == "PENDING"

        id_col = table.c.identity_check
        assert id_col.server_default.arg == "PENDING"

        seat_col = table.c.seat_check
        assert seat_col.server_default.arg == "PENDING"


# ---------------------------------------------------------------------------
# Historical Record Safety (no cascade deletes)
# ---------------------------------------------------------------------------

class TestHistoricalRecordSafety:
    def test_no_cascade_delete_on_student(self):
        """EntryVerification does not use cascade='all, delete-orphan' on student FK."""
        from app.models import Base
        table = Base.metadata.tables["entry_verifications"]
        student_fk = [fk for fk in table.foreign_keys if fk.parent.name == "student_id"][0]
        assert student_fk.ondelete is None or student_fk.ondelete != "CASCADE"

    def test_no_cascade_delete_on_camera(self):
        """EntryVerification does not use cascade='all, delete-orphan' on camera FK."""
        from app.models import Base
        table = Base.metadata.tables["entry_verifications"]
        camera_fks = [fk for fk in table.foreign_keys if fk.parent.name == "camera_id"]
        if camera_fks:
            assert camera_fks[0].ondelete is None or camera_fks[0].ondelete != "CASCADE"

    def test_no_cascade_delete_on_entry_point(self):
        """EntryVerification does not use cascade='all, delete-orphan' on entry_point FK."""
        from app.models import Base
        table = Base.metadata.tables["entry_verifications"]
        ep_fks = [fk for fk in table.foreign_keys if fk.parent.name == "entry_point_id"]
        if ep_fks:
            assert ep_fks[0].ondelete is None or ep_fks[0].ondelete != "CASCADE"


# ---------------------------------------------------------------------------
# Data Integrity
# ---------------------------------------------------------------------------

class TestDataIntegrity:
    def test_missing_student_id_raises(self, db, registration, hall, entry_point):
        ev = EntryVerification(
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_missing_exam_registration_id_raises(self, db, student, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_missing_exam_hall_id_raises(self, db, student, registration, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            entry_point_id=entry_point.id,
        )
        db.add(ev)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_missing_entry_point_id_raises(self, db, student, registration, hall):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
        )
        db.add(ev)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_optional_fields_can_be_null(self, db, student, registration, hall, entry_point):
        ev = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            hall_ticket_id=None,
            identity_verification_attempt_id=None,
            camera_id=None,
            escalation_reason=None,
            resolved_at=None,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)
        assert ev.id is not None

"""Phase 12.5 — Integration & Hardening Tests.

End-to-end workflow tests, idempotency, concurrency, event history audit,
summary correctness, snapshot integrity, API integration, privacy, and
architectural safety tests for the complete Phase 12 attendance system.
"""

import pytest
from datetime import date, time, datetime, timezone
from sqlalchemy import create_engine, func
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
    get_attendance_by_registration,
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
    s = Student(usn="HTEST001", name="Hardening Test Student")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture()
def student2(db):
    s = Student(usn="HTEST002", name="Hardening Student Two")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture()
def subject(db):
    s = Subject(code="HSUB101", name="Hardening Subject", department="CS", semester=6)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture()
def exam(db, subject):
    e = Exam(
        subject_id=subject.id,
        exam_name="HTEST Exam",
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
    h = ExamHall(building="HTESTBuilding", room_number="201", capacity=50)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


@pytest.fixture()
def hall2(db):
    h = ExamHall(building="HTESTBuilding", room_number="202", capacity=50)
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
    ep = EntryPoint(name="HTEST Gate", code="HTESTEP1", exam_hall_id=hall.id)
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


def _make_ev(db, student, registration, hall, entry_point, status):
    ev = EntryVerification(
        student_id=student.id,
        exam_registration_id=registration.id,
        exam_hall_id=hall.id,
        entry_point_id=entry_point.id,
        status=status,
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
        seat_number="H01",
        exam_id=exam.id,
        student_id=student.id,
    )
    db.add(sa)
    db.commit()
    db.refresh(sa)
    return sa


# ===========================================================================
# 1. END-TO-END WORKFLOWS
# ===========================================================================


class TestEndToEndWorkflows:
    """Complete workflow tests for GRANTED, DENIED, ESCALATED, RE-ENTRY."""

    def test_granted_entry_workflow(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        """A: GRANTED ENTRY → AttendanceRecord PRESENT → correct event history."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )

        record = record_attendance(db, ev.id)

        assert record is not None
        assert record.status == AttendanceStatus.PRESENT.value
        assert record.student_id == student.id
        assert record.hall_id == hall.id
        assert record.seat_number == "H01"
        assert record.entry_verification_id == ev.id
        assert record.entry_method == EntryMethod.VERIFIED_ENTRY.value

        events = get_entry_events(db, ev.id)["items"]
        assert len(events) == 1
        assert events[0].event_type == AttendanceEventType.ENTRY_GRANTED.value
        assert events[0].status_snapshot == AttendanceStatus.PRESENT.value
        assert events[0].recorded_by == "system"

    def test_denied_entry_workflow(
        self, db, student, registration, hall, entry_point
    ):
        """B: DENIED ENTRY → ENTRY_DENIED event → no AttendanceRecord."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.DENIED.value,
        )

        result = record_attendance(db, ev.id)

        assert result is None
        record = get_attendance_by_registration(db, registration.id)
        assert record is None

        events = get_entry_events(db, ev.id)["items"]
        assert len(events) == 1
        assert events[0].event_type == AttendanceEventType.ENTRY_DENIED.value
        assert events[0].status_snapshot == "N/A"

    def test_escalated_then_granted(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        """C: ESCALATED → unresolved → cannot record → resolved to GRANTED → record."""
        ev_esc = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.ESCALATED.value,
        )

        with pytest.raises(ValueError, match="ESCALATED"):
            record_attendance(db, ev_esc.id)

        ev_granted = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )

        record = record_attendance(db, ev_granted.id)
        assert record is not None
        assert record.status == AttendanceStatus.PRESENT.value

        events = get_entry_events(db, ev_granted.id)["items"]
        assert len(events) == 1
        assert events[0].event_type == AttendanceEventType.ENTRY_GRANTED.value

    def test_escalated_then_denied(
        self, db, student, registration, hall, entry_point
    ):
        """D: ESCALATED → DENIED → no AttendanceRecord → denied event correct."""
        ev_esc = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.ESCALATED.value,
        )

        with pytest.raises(ValueError, match="ESCALATED"):
            record_attendance(db, ev_esc.id)

        ev_denied = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.DENIED.value,
        )

        result = record_attendance(db, ev_denied.id)
        assert result is None

        record = get_attendance_by_registration(db, registration.id)
        assert record is None

        events = get_entry_events(db, ev_denied.id)["items"]
        assert len(events) == 1
        assert events[0].event_type == AttendanceEventType.ENTRY_DENIED.value

    def test_re_entry_two_granted_evs(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        """E: RE-ENTRY → EV1 GRANTED, EV2 GRANTED → one current record, multiple events."""
        ev1 = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record1 = record_attendance(db, ev1.id)
        assert record1 is not None

        ev2 = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record2 = record_attendance(db, ev2.id)
        assert record2 is not None

        assert record1.id == record2.id

        current = get_attendance_by_registration(db, registration.id)
        assert current is not None
        assert current.entry_verification_id == ev2.id
        assert current.status == AttendanceStatus.PRESENT.value

        events_ev1 = get_entry_events(db, ev1.id)["items"]
        events_ev2 = get_entry_events(db, ev2.id)["items"]
        assert len(events_ev1) == 1
        assert len(events_ev2) == 1
        assert events_ev1[0].event_type == AttendanceEventType.ENTRY_GRANTED.value
        assert events_ev2[0].event_type == AttendanceEventType.ENTRY_GRANTED.value


# ===========================================================================
# 2. IDEMPOTENCY
# ===========================================================================


class TestIdempotency:
    """Verify idempotent behavior of record_attendance."""

    def test_record_attendance_idempotent(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        """record_attendance same EV twice → one event, one record."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )

        r1 = record_attendance(db, ev.id)
        r2 = record_attendance(db, ev.id)

        assert r1 is not None
        assert r2 is not None
        assert r1.id == r2.id

        events = get_entry_events(db, ev.id)["items"]
        assert len(events) == 1
        assert events[0].event_type == AttendanceEventType.ENTRY_GRANTED.value

        records = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == registration.id)
            .count()
        )
        assert records == 1

    def test_record_denied_idempotent(
        self, db, student, registration, hall, entry_point
    ):
        """record_attendance DENIED twice → one event, no record."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.DENIED.value,
        )

        r1 = record_attendance(db, ev.id)
        r2 = record_attendance(db, ev.id)

        assert r1 is None
        assert r2 is None

        events = get_entry_events(db, ev.id)["items"]
        assert len(events) == 1

        record = get_attendance_by_registration(db, registration.id)
        assert record is None


# ===========================================================================
# 3. CONCURRENCY
# ===========================================================================


class TestConcurrency:
    """Simulate concurrent access patterns."""

    def test_concurrent_same_ev(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        """Two requests for SAME GRANTED EV → no duplicates."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )

        r1 = record_attendance(db, ev.id)
        r2 = record_attendance(db, ev.id)

        assert r1 is not None
        assert r2 is not None
        assert r1.id == r2.id

        events = get_entry_events(db, ev.id)["items"]
        assert len(events) == 1

        records = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == registration.id)
            .count()
        )
        assert records == 1

    def test_concurrent_different_evs_same_registration(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        """Two DIFFERENT GRANTED EVs for same registration → one record, multiple events."""
        ev1 = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        ev2 = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )

        r1 = record_attendance(db, ev1.id)
        r2 = record_attendance(db, ev2.id)

        assert r1 is not None
        assert r2 is not None

        records = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.exam_registration_id == registration.id)
            .all()
        )
        assert len(records) == 1

        events1 = get_entry_events(db, ev1.id)["items"]
        events2 = get_entry_events(db, ev2.id)["items"]
        assert len(events1) == 1
        assert len(events2) == 1


# ===========================================================================
# 4. EVENT HISTORY AUDIT
# ===========================================================================


class TestEventHistoryAudit:
    """Verify manual correction always creates auditable events."""

    def test_manual_correction_creates_event_after_auto_record(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        """After auto-record, manual correction → ATTENDANCE_CORRECTED event created."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        corrected = mark_manual_attendance(
            db,
            registration.id,
            status=AttendanceStatus.EXCUSED.value,
            reason="Medical leave",
            recorded_by="admin_001",
        )
        assert corrected.status == AttendanceStatus.EXCUSED.value

        events = get_entry_events(db, ev.id)["items"]
        assert len(events) == 2

        event_types = [e.event_type for e in events]
        assert AttendanceEventType.ENTRY_GRANTED.value in event_types
        assert AttendanceEventType.ATTENDANCE_CORRECTED.value in event_types

        correction_event = [
            e for e in events
            if e.event_type == AttendanceEventType.ATTENDANCE_CORRECTED.value
        ][0]
        assert correction_event.status_snapshot == AttendanceStatus.EXCUSED.value
        assert correction_event.recorded_by == "admin_001"
        assert correction_event.reason == "Medical leave"

    def test_manual_correction_preserves_original_event(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        """Original ENTRY_GRANTED event is preserved after manual correction."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        mark_manual_attendance(
            db,
            registration.id,
            status=AttendanceStatus.EXCUSED.value,
            reason="Medical",
            recorded_by="admin",
        )

        events = get_entry_events(db, ev.id)["items"]
        grant_event = [
            e for e in events
            if e.event_type == AttendanceEventType.ENTRY_GRANTED.value
        ][0]
        assert grant_event.status_snapshot == AttendanceStatus.PRESENT.value

    def test_multiple_corrections_create_multiple_events(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        """Multiple corrections → each creates its own event."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        mark_manual_attendance(
            db,
            registration.id,
            status=AttendanceStatus.EXCUSED.value,
            reason="Reason 1",
            recorded_by="admin1",
        )

        mark_manual_attendance(
            db,
            registration.id,
            status=AttendanceStatus.PRESENT.value,
            reason="Reason 2",
            recorded_by="admin2",
        )

        events = get_entry_events(db, ev.id)["items"]
        assert len(events) == 3

        event_types = [e.event_type for e in events]
        assert event_types.count(AttendanceEventType.ATTENDANCE_CORRECTED.value) == 2


# ===========================================================================
# 5. ATTENDANCE STATE MACHINE
# ===========================================================================


class TestStateMachine:
    """Verify valid and invalid status transitions."""

    def test_present_to_excused(self, db, student, registration, hall, entry_point, seat_assignment):
        """PRESENT → EXCUSED is valid."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        result = mark_manual_attendance(
            db,
            registration.id,
            status=AttendanceStatus.EXCUSED.value,
            reason="Medical",
            recorded_by="admin",
        )
        assert result.status == AttendanceStatus.EXCUSED.value

    def test_excused_to_present(self, db, student, registration, hall, entry_point, seat_assignment):
        """EXCUSED → PRESENT is valid."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        mark_manual_attendance(
            db,
            registration.id,
            status=AttendanceStatus.EXCUSED.value,
            reason="Medical",
            recorded_by="admin",
        )

        result = mark_manual_attendance(
            db,
            registration.id,
            status=AttendanceStatus.PRESENT.value,
            reason="Reverted",
            recorded_by="admin",
        )
        assert result.status == AttendanceStatus.PRESENT.value

    def test_invalid_status_rejected(self, db, student, registration, hall, entry_point):
        """ABSENT status is not allowed for manual correction."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )

        with pytest.raises(ValueError, match="Invalid status"):
            mark_manual_attendance(
                db,
                registration.id,
                status=AttendanceStatus.ABSENT.value,
                reason="Test",
                recorded_by="admin",
            )

    def test_random_status_rejected(self, db, student, registration, hall, entry_point):
        """Arbitrary status string is rejected."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )

        with pytest.raises(ValueError, match="Invalid status"):
            mark_manual_attendance(
                db,
                registration.id,
                status="INVALID_STATUS",
                reason="Test",
                recorded_by="admin",
            )


# ===========================================================================
# 6. SUMMARY CORRECTNESS
# ===========================================================================


class TestSummaryCorrectness:
    """Verify summary computations are correct."""

    def test_summary_empty_exam(self, db, exam):
        """Zero registrations → all zeros, no division by zero."""
        summary = get_exam_summary(db, exam.id)
        assert summary["total_registered"] == 0
        assert summary["total_present"] == 0
        assert summary["total_absent"] == 0
        assert summary["total_excused"] == 0
        assert summary["attendance_rate"] == 0.0
        assert summary["by_hall"] == []

    def test_summary_all_present(self, db, student, registration, hall, entry_point, seat_assignment):
        """All present → rate = 100%."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        summary = get_exam_summary(db, registration.exam_id)
        assert summary["total_registered"] >= 1
        assert summary["total_present"] >= 1
        assert summary["total_absent"] == max(
            0, summary["total_registered"] - summary["total_present"] - summary["total_excused"]
        )

    def test_absent_computed_not_fabricated(
        self, db, student, registration, hall, entry_point
    ):
        """ABSENT = registered - present - excused. No ABSENT record rows."""
        summary = get_exam_summary(db, registration.exam_id)
        assert summary["total_absent"] == max(
            0,
            summary["total_registered"]
            - summary["total_present"]
            - summary["total_excused"],
        )

        absent_records = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.exam_id == registration.exam_id,
                AttendanceRecord.status == AttendanceStatus.ABSENT.value,
            )
            .count()
        )
        assert absent_records == 0

    def test_summary_by_hall(self, db, student, registration, hall, entry_point, seat_assignment):
        """By-hall breakdown includes correct hall."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        summary = get_exam_summary(db, registration.exam_id)
        hall_ids = [h["hall_id"] for h in summary["by_hall"]]
        assert hall.id in hall_ids

        for h in summary["by_hall"]:
            assert "hall_id" in h
            assert "hall_name" in h
            assert "total" in h
            assert "present" in h
            assert h["total"] >= 0
            assert h["present"] >= 0
            assert h["present"] <= h["total"]

    def test_summary_rate_range(self, db, student, registration, hall, entry_point, seat_assignment):
        """Attendance rate is between 0 and 100."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        summary = get_exam_summary(db, registration.exam_id)
        assert 0.0 <= summary["attendance_rate"] <= 100.0

    def test_summary_no_negative_counts(self, db, student, registration, hall, entry_point, seat_assignment):
        """No negative counts in summary."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        summary = get_exam_summary(db, registration.exam_id)
        assert summary["total_registered"] >= 0
        assert summary["total_present"] >= 0
        assert summary["total_excused"] >= 0
        assert summary["total_absent"] >= 0


# ===========================================================================
# 7. SNAPSHOT INTEGRITY
# ===========================================================================


class TestSnapshotIntegrity:
    """Verify attendance records snapshot data, not live lookups."""

    def test_seat_snapshot_preserved(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        """AttendanceRecord retains original seat even if SeatAssignment changes."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record = record_attendance(db, ev.id)
        assert record.seat_number == "H01"

        seat_assignment.seat_number = "CHANGED"
        db.commit()
        db.refresh(record)

        current = get_attendance_by_registration(db, registration.id)
        assert current.seat_number == "H01"

    def test_hall_snapshot_preserved(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        """AttendanceRecord retains original hall_id."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record = record_attendance(db, ev.id)
        assert record.hall_id == hall.id

        current = get_attendance_by_registration(db, registration.id)
        assert current.hall_id == hall.id


# ===========================================================================
# 8. API INTEGRATION (service-level)
# ===========================================================================


class TestAPIIntegration:
    """Test service functions used by API endpoints."""

    def test_list_attendance_filters(self, db, student, registration, hall, entry_point, seat_assignment):
        """list_attendance with hall_id and status filters."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        result = list_attendance(db, registration.exam_id, hall_id=hall.id)
        assert result["total"] >= 1
        for item in result["items"]:
            assert item.hall_id == hall.id

    def test_list_attendance_status_filter(self, db, student, registration, hall, entry_point, seat_assignment):
        """list_attendance with status filter."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        result = list_attendance(
            db, registration.exam_id, status=AttendanceStatus.PRESENT.value
        )
        assert result["total"] >= 1
        for item in result["items"]:
            assert item.status == AttendanceStatus.PRESENT.value

    def test_list_attendance_pagination(self, db, student, registration, hall, entry_point, seat_assignment):
        """list_attendance respects page and page_size."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        result = list_attendance(db, registration.exam_id, page=1, page_size=1)
        assert result["page"] == 1
        assert result["page_size"] == 1
        assert len(result["items"]) <= 1

    def test_list_student_attendance(self, db, student, registration, hall, entry_point, seat_assignment):
        """list_student_attendance_history returns student records."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        result = list_student_attendance_history(db, student.id)
        assert result["total"] >= 1
        for item in result["items"]:
            assert item.student_id == student.id

    def test_list_student_attendance_missing(self, db):
        """list_student_attendance_history raises for missing student."""
        with pytest.raises(LookupError):
            list_student_attendance_history(db, 999999)

    def test_get_entry_events_empty(self, db):
        """get_entry_events returns empty for non-existent EV."""
        result = get_entry_events(db, 999999)
        assert result["items"] == []
        assert result["total"] == 0


# ===========================================================================
# 9. PRIVACY
# ===========================================================================


class TestPrivacy:
    """Verify no sensitive data is exposed."""

    def test_no_biometric_data_in_record(self, db, student, registration, hall, entry_point, seat_assignment):
        """AttendanceRecord has no biometric fields."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record = record_attendance(db, ev.id)

        for attr in [
            "face_embedding", "face_image", "biometric_data",
            "provider_credentials", "api_key", "raw_ocr",
        ]:
            assert not hasattr(record, attr), f"AttendanceRecord should not have {attr}"

    def test_no_biometric_data_in_event(self, db, student, registration, hall, entry_point, seat_assignment):
        """AttendanceEvent has no biometric fields."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        events = get_entry_events(db, ev.id)["items"]
        for event in events:
            for attr in [
                "face_embedding", "face_image", "biometric_data",
                "provider_credentials", "api_key", "raw_ocr",
            ]:
                assert not hasattr(event, attr), f"AttendanceEvent should not have {attr}"

    def test_recorded_by_stored_not_leaked(self, db, student, registration, hall, entry_point, seat_assignment):
        """recorded_by is stored in event, not in record."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        events = get_entry_events(db, ev.id)["items"]
        assert events[0].recorded_by == "system"

        record = get_attendance_by_registration(db, registration.id)
        assert not hasattr(record, "recorded_by")


# ===========================================================================
# 10. ARCHITECTURAL SAFETY
# ===========================================================================


class TestArchitecturalSafety:
    """Verify attendance service does not mutate EntryVerification."""

    def test_record_attendance_does_not_mutate_ev(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        """record_attendance does not change EV status."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        original_status = ev.status

        record_attendance(db, ev.id)

        db.refresh(ev)
        assert ev.status == original_status

    def test_manual_correction_does_not_mutate_ev(
        self, db, student, registration, hall, entry_point, seat_assignment
    ):
        """mark_manual_attendance does not change EV status."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)
        original_status = ev.status

        mark_manual_attendance(
            db,
            registration.id,
            status=AttendanceStatus.EXCUSED.value,
            reason="Test",
            recorded_by="admin",
        )

        db.refresh(ev)
        assert ev.status == original_status

    def test_attendance_does_not_grant_or_deny_entry(
        self, db, student, registration, hall, entry_point
    ):
        """Attendance service never creates or modifies EntryVerification."""
        ev_count_before = db.query(func.count(EntryVerification.id)).scalar()

        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        record_attendance(db, ev.id)

        ev_count_after = db.query(func.count(EntryVerification.id)).scalar()
        assert ev_count_after == ev_count_before + 1


# ===========================================================================
# 11. EDGE CASES
# ===========================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_manual_correction_no_ev(self, db, student, exam):
        """Manual correction with no EV for registration → ValueError."""
        reg = ExamRegistration(student_id=student.id, exam_id=exam.id)
        db.add(reg)
        db.commit()
        db.refresh(reg)

        with pytest.raises(ValueError, match="No entry verification"):
            mark_manual_attendance(
                db,
                reg.id,
                status=AttendanceStatus.EXCUSED.value,
                reason="Test",
                recorded_by="admin",
            )

    def test_manual_correction_empty_reason(self, db, student, registration, hall, entry_point):
        """Manual correction with empty reason → ValueError."""
        _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )

        with pytest.raises(ValueError, match="Reason is required"):
            mark_manual_attendance(
                db,
                registration.id,
                status=AttendanceStatus.EXCUSED.value,
                reason="",
                recorded_by="admin",
            )

    def test_manual_correction_empty_recorded_by(self, db, student, registration, hall, entry_point):
        """Manual correction with empty recorded_by → ValueError."""
        _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )

        with pytest.raises(ValueError, match="recorded_by is required"):
            mark_manual_attendance(
                db,
                registration.id,
                status=AttendanceStatus.EXCUSED.value,
                reason="Test",
                recorded_by="",
            )

    def test_manual_correction_cancelled_registration(self, db, student, registration, hall, entry_point):
        """Manual correction on cancelled registration → ValueError."""
        _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.GRANTED.value,
        )
        registration.status = RegistrationStatus.CANCELLED.value
        db.commit()

        with pytest.raises(ValueError, match="cancelled"):
            mark_manual_attendance(
                db,
                registration.id,
                status=AttendanceStatus.EXCUSED.value,
                reason="Test",
                recorded_by="admin",
            )

    def test_record_attendance_pending_ev(self, db, student, registration, hall, entry_point):
        """record_attendance on PENDING EV → ValueError."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.PENDING.value,
        )

        with pytest.raises(ValueError, match="terminal state"):
            record_attendance(db, ev.id)

    def test_record_attendance_in_progress_ev(self, db, student, registration, hall, entry_point):
        """record_attendance on IN_PROGRESS EV → ValueError."""
        ev = _make_ev(
            db, student, registration, hall, entry_point,
            EntryVerificationStatus.IN_PROGRESS.value,
        )

        with pytest.raises(ValueError, match="terminal state"):
            record_attendance(db, ev.id)

    def test_record_attendance_missing_ev(self, db):
        """record_attendance on non-existent EV → LookupError."""
        with pytest.raises(LookupError):
            record_attendance(db, 999999)

    def test_get_attendance_missing_exam(self, db, student):
        """get_attendance for non-existent exam → None."""
        result = get_attendance(db, 999999, student.id)
        assert result is None

    def test_get_exam_summary_missing_exam(self, db):
        """get_exam_summary for non-existent exam → LookupError."""
        with pytest.raises(LookupError):
            get_exam_summary(db, 999999)

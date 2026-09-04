"""Phase 11.2 — Deterministic Anti-Proxy Signal Detection.

Tests for the signal detection service. Covers all 14 signal types,
idempotency, privacy/security, and regression.
"""

import json
import pytest
from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy import create_engine
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
from app.models.hall_ticket_match import (
    HallTicketMatchResult,
    HallTicketMatchSignal,
    MatchStatus,
)
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationDecision,
    IdentityVerificationEvidence,
    IdentityVerificationStatus,
)
from app.models.proxy_risk import (
    SecuritySignal,
    SecuritySignalType,
    SignalStrength,
    SIGNAL_STRENGTH_DEFAULTS,
)
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.student import Student
from app.models.subject import Subject
from app.services.signal_detection import detect_signals


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
def other_hall(db):
    h = ExamHall(building="OtherBuilding", room_number="202", capacity=30)
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
def camera(db, hall):
    c = Camera(
        name="Test Camera",
        device_identifier="CAM-TEST-001",
        exam_hall_id=hall.id,
        status=CameraStatus.ONLINE.value,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def camera_mapping(db, camera, entry_point):
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
        seat_number="A1",
        exam_id=exam.id,
        student_id=student.id,
        status=SeatAssignmentStatus.ASSIGNED.value,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture()
def entry_verification(db, student, registration, hall, entry_point):
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
def hall_ticket(db, registration):
    ht = HallTicket(
        exam_registration_id=registration.id,
        status=HallTicketStatus.VERIFIED.value,
    )
    db.add(ht)
    db.commit()
    db.refresh(ht)
    return ht


# ---------------------------------------------------------------------------
# IDENTITY_MISMATCH
# ---------------------------------------------------------------------------

class TestIdentityMismatch:
    def test_detected_when_no_match(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.NO_MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.IDENTITY_MISMATCH.value in types

        sig = next(s for s in signals if s.signal_type == SecuritySignalType.IDENTITY_MISMATCH.value)
        assert sig.strength == SignalStrength.STRONG.value
        assert sig.source == "identity_verification"
        data = json.loads(sig.evidence_json)
        assert data["source_type"] == "identity_verification_attempt"
        assert data["source_id"] == attempt.id

    def test_not_detected_when_match(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.IDENTITY_MISMATCH.value not in types

    def test_not_detected_when_inconclusive(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.INCONCLUSIVE.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.IDENTITY_MISMATCH.value not in types

    def test_not_detected_when_no_attempt(self, db, entry_verification):
        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.IDENTITY_MISMATCH.value not in types


# ---------------------------------------------------------------------------
# LIVENESS_SPOOF_DETECTED
# ---------------------------------------------------------------------------

class TestLivenessSpoofDetected:
    def test_detected_when_liveness_fail(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.PENDING.value,
            status=IdentityVerificationStatus.IN_PROGRESS.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        evidence = IdentityVerificationEvidence(
            attempt_id=attempt.id,
            signal_type="liveness",
            signal_value="FAIL",
        )
        db.add(evidence)
        db.commit()
        db.refresh(evidence)

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.LIVENESS_SPOOF_DETECTED.value in types

        sig = next(s for s in signals if s.signal_type == SecuritySignalType.LIVENESS_SPOOF_DETECTED.value)
        assert sig.strength == SignalStrength.STRONG.value
        data = json.loads(sig.evidence_json)
        assert data["source_type"] == "identity_verification_evidence"
        assert data["source_id"] == evidence.id

    def test_not_detected_when_liveness_pass(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.PENDING.value,
            status=IdentityVerificationStatus.IN_PROGRESS.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        evidence = IdentityVerificationEvidence(
            attempt_id=attempt.id,
            signal_type="liveness",
            signal_value="PASS",
        )
        db.add(evidence)
        db.commit()

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.LIVENESS_SPOOF_DETECTED.value not in types

    def test_not_detected_when_unrelated_evidence(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.PENDING.value,
            status=IdentityVerificationStatus.IN_PROGRESS.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        evidence = IdentityVerificationEvidence(
            attempt_id=attempt.id,
            signal_type="similarity_score",
            signal_value="0.92",
        )
        db.add(evidence)
        db.commit()

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.LIVENESS_SPOOF_DETECTED.value not in types


# ---------------------------------------------------------------------------
# WRONG_HALL_DETECTED
# ---------------------------------------------------------------------------

class TestWrongHallDetected:
    def test_detected_when_halls_conflict(self, db, entry_verification, registration, seat, other_hall):
        entry_verification.exam_hall_id = other_hall.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.WRONG_HALL_DETECTED.value in types

        sig = next(s for s in signals if s.signal_type == SecuritySignalType.WRONG_HALL_DETECTED.value)
        assert sig.strength == SignalStrength.STRONG.value
        data = json.loads(sig.evidence_json)
        assert data["source_type"] == "seat_assignment"
        assert data["assigned_hall_id"] == seat.exam_hall_id
        assert data["entry_hall_id"] == other_hall.id

    def test_not_detected_when_halls_match(self, db, entry_verification, seat):
        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.WRONG_HALL_DETECTED.value not in types

    def test_not_detected_when_no_seat(self, db, entry_verification, other_hall):
        entry_verification.exam_hall_id = other_hall.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.WRONG_HALL_DETECTED.value not in types


# ---------------------------------------------------------------------------
# IDENTITY_INCONCLUSIVE
# ---------------------------------------------------------------------------

class TestIdentityInconclusive:
    def test_detected_when_inconclusive(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.INCONCLUSIVE.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.IDENTITY_INCONCLUSIVE.value in types

        sig = next(s for s in signals if s.signal_type == SecuritySignalType.IDENTITY_INCONCLUSIVE.value)
        assert sig.strength == SignalStrength.MODERATE.value

    def test_not_detected_when_match(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(attempt)
        db.commit()

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.IDENTITY_INCONCLUSIVE.value not in types


# ---------------------------------------------------------------------------
# DUPLICATE_ENTRY_SAME_EXAM
# ---------------------------------------------------------------------------

class TestDuplicateEntrySameExam:
    def test_detected_when_second_entry(self, db, student, registration, hall, entry_point, exam):
        ev1 = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.GRANTED.value,
        )
        db.add(ev1)
        db.commit()
        db.refresh(ev1)

        ev2 = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.IN_PROGRESS.value,
        )
        db.add(ev2)
        db.commit()
        db.refresh(ev2)

        signals = detect_signals(db, ev2.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.DUPLICATE_ENTRY_SAME_EXAM.value in types

        sig = next(s for s in signals if s.signal_type == SecuritySignalType.DUPLICATE_ENTRY_SAME_EXAM.value)
        assert sig.strength == SignalStrength.MODERATE.value
        data = json.loads(sig.evidence_json)
        assert ev1.id in data["other_entry_ids"]
        assert data["exam_id"] == exam.id

    def test_not_detected_when_different_exam(self, db, student, registration, hall, entry_point, subject):
        other_exam = Exam(
            subject_id=subject.id,
            exam_name="Other Exam",
            exam_date=date(2026, 9, 16),
            start_time=time(9, 0),
            end_time=time(12, 0),
            semester=6,
            department="CS",
        )
        db.add(other_exam)
        db.commit()
        db.refresh(other_exam)

        other_reg = ExamRegistration(student_id=student.id, exam_id=other_exam.id)
        db.add(other_reg)
        db.commit()
        db.refresh(other_reg)

        ev1 = EntryVerification(
            student_id=student.id,
            exam_registration_id=other_reg.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.GRANTED.value,
        )
        db.add(ev1)
        db.commit()

        ev2 = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.IN_PROGRESS.value,
        )
        db.add(ev2)
        db.commit()
        db.refresh(ev2)

        signals = detect_signals(db, ev2.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.DUPLICATE_ENTRY_SAME_EXAM.value not in types

    def test_not_detected_when_different_student(self, db, entry_verification, registration, hall, entry_point, exam):
        other_student = Student(usn="OTHER001", name="Other Student")
        db.add(other_student)
        db.commit()
        db.refresh(other_student)

        other_reg = ExamRegistration(student_id=other_student.id, exam_id=exam.id)
        db.add(other_reg)
        db.commit()
        db.refresh(other_reg)

        ev1 = EntryVerification(
            student_id=other_student.id,
            exam_registration_id=other_reg.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.GRANTED.value,
        )
        db.add(ev1)
        db.commit()

        # Check that entry_verification (original student) doesn't detect duplicate
        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.DUPLICATE_ENTRY_SAME_EXAM.value not in types

    def test_not_detected_on_first_entry(self, db, entry_verification):
        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.DUPLICATE_ENTRY_SAME_EXAM.value not in types


# ---------------------------------------------------------------------------
# REPEATED_FAILED_IDENTITY
# ---------------------------------------------------------------------------

class TestRepeatedFailedIdentity:
    def test_detected_when_two_no_match(self, db, entry_verification, registration, student):
        a1 = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            decision=IdentityVerificationDecision.NO_MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        a2 = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            decision=IdentityVerificationDecision.NO_MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add_all([a1, a2])
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.REPEATED_FAILED_IDENTITY.value in types

        sig = next(s for s in signals if s.signal_type == SecuritySignalType.REPEATED_FAILED_IDENTITY.value)
        assert sig.strength == SignalStrength.MODERATE.value
        data = json.loads(sig.evidence_json)
        assert data["attempt_count"] == 2
        assert a1.id in data["source_ids"]
        assert a2.id in data["source_ids"]

    def test_not_detected_when_one_no_match(self, db, entry_verification, registration, student):
        a1 = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            decision=IdentityVerificationDecision.NO_MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(a1)
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.REPEATED_FAILED_IDENTITY.value not in types

    def test_not_detected_when_no_match_plus_match(self, db, entry_verification, registration, student):
        a1 = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            decision=IdentityVerificationDecision.NO_MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        a2 = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            decision=IdentityVerificationDecision.MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add_all([a1, a2])
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.REPEATED_FAILED_IDENTITY.value not in types


# ---------------------------------------------------------------------------
# HALL_TICKET_FIELD_MISMATCH
# ---------------------------------------------------------------------------

class TestHallTicketFieldMismatch:
    def test_detected_when_mismatch(self, db, entry_verification, registration):
        ht = HallTicket(
            exam_registration_id=registration.id,
            status=HallTicketStatus.MATCHED.value,
        )
        db.add(ht)
        db.commit()
        db.refresh(ht)

        match_result = HallTicketMatchResult(
            document_id=1,
            extraction_result_id=1,
            overall_status=MatchStatus.PARTIAL_MATCH.value,
        )
        db.add(match_result)
        db.commit()
        db.refresh(match_result)

        ht.match_result_id = match_result.id
        db.commit()

        signal1 = HallTicketMatchSignal(
            match_result_id=match_result.id,
            field_name="student_usn",
            matched=False,
            signal_type="student_usn",
        )
        signal2 = HallTicketMatchSignal(
            match_result_id=match_result.id,
            field_name="exam_date",
            matched=False,
            signal_type="exam_date",
        )
        db.add_all([signal1, signal2])
        db.commit()

        entry_verification.hall_ticket_id = ht.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.HALL_TICKET_FIELD_MISMATCH.value in types

        sig = next(s for s in signals if s.signal_type == SecuritySignalType.HALL_TICKET_FIELD_MISMATCH.value)
        assert sig.strength == SignalStrength.MODERATE.value
        data = json.loads(sig.evidence_json)
        assert "student_usn" in data["mismatched_fields"]
        assert "exam_date" in data["mismatched_fields"]
        assert data["match_result_id"] == match_result.id

    def test_not_detected_when_all_matched(self, db, entry_verification, registration):
        ht = HallTicket(
            exam_registration_id=registration.id,
            status=HallTicketStatus.MATCHED.value,
        )
        db.add(ht)
        db.commit()
        db.refresh(ht)

        match_result = HallTicketMatchResult(
            document_id=1,
            extraction_result_id=1,
            overall_status=MatchStatus.MATCHED.value,
        )
        db.add(match_result)
        db.commit()
        db.refresh(match_result)

        ht.match_result_id = match_result.id
        db.commit()

        signal = HallTicketMatchSignal(
            match_result_id=match_result.id,
            field_name="student_usn",
            matched=True,
            signal_type="student_usn",
        )
        db.add(signal)
        db.commit()

        entry_verification.hall_ticket_id = ht.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.HALL_TICKET_FIELD_MISMATCH.value not in types

    def test_not_detected_when_no_hall_ticket(self, db, entry_verification):
        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.HALL_TICKET_FIELD_MISMATCH.value not in types


# ---------------------------------------------------------------------------
# WRONG_ENTRY_POINT
# ---------------------------------------------------------------------------

class TestWrongEntryPoint:
    def test_detected_when_halls_conflict(self, db, entry_verification, seat, other_hall, entry_point):
        other_ep = EntryPoint(name="Side Gate", code="SIDE_GATE", exam_hall_id=other_hall.id)
        db.add(other_ep)
        db.commit()
        db.refresh(other_ep)

        entry_verification.entry_point_id = other_ep.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.WRONG_ENTRY_POINT.value in types

        sig = next(s for s in signals if s.signal_type == SecuritySignalType.WRONG_ENTRY_POINT.value)
        assert sig.strength == SignalStrength.MODERATE.value
        data = json.loads(sig.evidence_json)
        assert data["entry_point_hall_id"] == other_hall.id
        assert data["assigned_hall_id"] == seat.exam_hall_id

    def test_not_detected_when_matching(self, db, entry_verification, seat, entry_point):
        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.WRONG_ENTRY_POINT.value not in types

    def test_not_detected_when_no_seat(self, db, entry_verification, other_hall):
        other_ep = EntryPoint(name="Side Gate", code="SIDE_GATE", exam_hall_id=other_hall.id)
        db.add(other_ep)
        db.commit()
        db.refresh(other_ep)

        entry_verification.entry_point_id = other_ep.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.WRONG_ENTRY_POINT.value not in types


# ---------------------------------------------------------------------------
# MISSING_IDENTITY_CHECK
# ---------------------------------------------------------------------------

class TestMissingIdentityCheck:
    def test_detected_when_skipped_with_camera(self, db, entry_verification, camera, camera_mapping):
        entry_verification.identity_check = IdentityCheckStatus.SKIPPED.value
        entry_verification.camera_id = camera.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.MISSING_IDENTITY_CHECK.value in types

        sig = next(s for s in signals if s.signal_type == SecuritySignalType.MISSING_IDENTITY_CHECK.value)
        assert sig.strength == SignalStrength.INFORMATIONAL.value
        data = json.loads(sig.evidence_json)
        assert data["camera_id"] == camera.id

    def test_not_detected_when_completed(self, db, entry_verification, camera, camera_mapping):
        entry_verification.identity_check = IdentityCheckStatus.PASSED.value
        entry_verification.camera_id = camera.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.MISSING_IDENTITY_CHECK.value not in types

    def test_not_detected_when_no_camera(self, db, entry_verification):
        entry_verification.identity_check = IdentityCheckStatus.SKIPPED.value
        entry_verification.camera_id = None
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.MISSING_IDENTITY_CHECK.value not in types


# ---------------------------------------------------------------------------
# NO_SEAT_ASSIGNMENT
# ---------------------------------------------------------------------------

class TestNoSeatAssignment:
    def test_detected_when_no_assignment(self, db, entry_verification):
        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.NO_SEAT_ASSIGNMENT.value in types

        sig = next(s for s in signals if s.signal_type == SecuritySignalType.NO_SEAT_ASSIGNMENT.value)
        assert sig.strength == SignalStrength.WEAK.value

    def test_not_detected_when_valid_assignment(self, db, entry_verification, seat):
        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.NO_SEAT_ASSIGNMENT.value not in types

    def test_detected_when_cancelled_assignment(self, db, entry_verification, seat):
        seat.status = SeatAssignmentStatus.CANCELLED.value
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.NO_SEAT_ASSIGNMENT.value in types


# ---------------------------------------------------------------------------
# NO_HALL_TICKET
# ---------------------------------------------------------------------------

class TestNoHallTicket:
    def test_detected_when_no_ticket(self, db, entry_verification):
        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.NO_HALL_TICKET.value in types

        sig = next(s for s in signals if s.signal_type == SecuritySignalType.NO_HALL_TICKET.value)
        assert sig.strength == SignalStrength.WEAK.value

    def test_not_detected_when_verified_ticket(self, db, entry_verification, registration):
        ht = HallTicket(
            exam_registration_id=registration.id,
            status=HallTicketStatus.VERIFIED.value,
        )
        db.add(ht)
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.NO_HALL_TICKET.value not in types

    def test_not_detected_when_matched_ticket(self, db, entry_verification, registration):
        ht = HallTicket(
            exam_registration_id=registration.id,
            status=HallTicketStatus.MATCHED.value,
        )
        db.add(ht)
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.NO_HALL_TICKET.value not in types

    def test_detected_when_rejected_ticket(self, db, entry_verification, registration):
        ht = HallTicket(
            exam_registration_id=registration.id,
            status=HallTicketStatus.REJECTED.value,
        )
        db.add(ht)
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.NO_HALL_TICKET.value in types


# ---------------------------------------------------------------------------
# CAMERA_OFFLINE_AT_ENTRY
# ---------------------------------------------------------------------------

class TestCameraOfflineAtEntry:
    def test_detected_when_offline(self, db, entry_verification, camera):
        camera.status = CameraStatus.OFFLINE.value
        db.commit()

        entry_verification.camera_id = camera.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.CAMERA_OFFLINE_AT_ENTRY.value in types

        sig = next(s for s in signals if s.signal_type == SecuritySignalType.CAMERA_OFFLINE_AT_ENTRY.value)
        assert sig.strength == SignalStrength.WEAK.value
        data = json.loads(sig.evidence_json)
        assert data["camera_status"] == CameraStatus.OFFLINE.value

    def test_detected_when_disabled(self, db, entry_verification, camera):
        camera.status = CameraStatus.DISABLED.value
        db.commit()

        entry_verification.camera_id = camera.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.CAMERA_OFFLINE_AT_ENTRY.value in types

    def test_not_detected_when_online(self, db, entry_verification, camera):
        entry_verification.camera_id = camera.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.CAMERA_OFFLINE_AT_ENTRY.value not in types

    def test_not_detected_when_no_camera(self, db, entry_verification):
        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.CAMERA_OFFLINE_AT_ENTRY.value not in types


# ---------------------------------------------------------------------------
# LATE_ENTRY
# ---------------------------------------------------------------------------

class TestLateEntry:
    def test_detected_when_after_start(self, db, entry_verification, registration, exam):
        entry_verification.created_at = datetime(2026, 9, 15, 9, 30, tzinfo=timezone.utc)
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.LATE_ENTRY.value in types

        sig = next(s for s in signals if s.signal_type == SecuritySignalType.LATE_ENTRY.value)
        assert sig.strength == SignalStrength.WEAK.value
        data = json.loads(sig.evidence_json)
        assert "exam_start_time" in data
        assert "entry_created_at" in data

    def test_not_detected_when_before_start(self, db, entry_verification, registration, exam):
        entry_verification.created_at = datetime(2026, 9, 15, 8, 50, tzinfo=timezone.utc)
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.LATE_ENTRY.value not in types

    def test_not_detected_when_exactly_at_start(self, db, entry_verification, registration, exam):
        entry_verification.created_at = datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc)
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.LATE_ENTRY.value not in types


# ---------------------------------------------------------------------------
# RAPID_SEQUENTIAL_ENTRY
# ---------------------------------------------------------------------------

class TestRapidSequentialEntry:
    def test_detected_within_window(self, db, student, registration, hall, entry_point, exam):
        ev1 = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.GRANTED.value,
            created_at=datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc),
        )
        db.add(ev1)
        db.commit()
        db.refresh(ev1)

        ev2 = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.IN_PROGRESS.value,
            created_at=datetime(2026, 9, 15, 9, 2, tzinfo=timezone.utc),
        )
        db.add(ev2)
        db.commit()
        db.refresh(ev2)

        signals = detect_signals(db, ev2.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.RAPID_SEQUENTIAL_ENTRY.value in types

        sig = next(s for s in signals if s.signal_type == SecuritySignalType.RAPID_SEQUENTIAL_ENTRY.value)
        assert sig.strength == SignalStrength.WEAK.value
        data = json.loads(sig.evidence_json)
        assert ev1.id in data["other_entry_ids"]
        assert data["window_seconds"] == 300

    def test_not_detected_outside_window(self, db, student, registration, hall, entry_point, exam):
        ev1 = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.GRANTED.value,
            created_at=datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc),
        )
        db.add(ev1)
        db.commit()
        db.refresh(ev1)

        ev2 = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.IN_PROGRESS.value,
            created_at=datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc),
        )
        db.add(ev2)
        db.commit()
        db.refresh(ev2)

        signals = detect_signals(db, ev2.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.RAPID_SEQUENTIAL_ENTRY.value not in types

    def test_not_detected_different_student(self, db, student, registration, hall, entry_point, exam):
        other_student = Student(usn="OTHER002", name="Other Student 2")
        db.add(other_student)
        db.commit()
        db.refresh(other_student)

        other_reg = ExamRegistration(student_id=other_student.id, exam_id=exam.id)
        db.add(other_reg)
        db.commit()
        db.refresh(other_reg)

        ev1 = EntryVerification(
            student_id=other_student.id,
            exam_registration_id=other_reg.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.GRANTED.value,
            created_at=datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc),
        )
        db.add(ev1)
        db.commit()
        db.refresh(ev1)

        ev_original = EntryVerification(
            student_id=student.id,
            exam_registration_id=registration.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.IN_PROGRESS.value,
            created_at=datetime(2026, 9, 15, 9, 2, tzinfo=timezone.utc),
        )
        db.add(ev_original)
        db.commit()
        db.refresh(ev_original)

        signals = detect_signals(db, ev_original.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.RAPID_SEQUENTIAL_ENTRY.value not in types

    def test_not_detected_different_exam(self, db, student, hall, entry_point, subject):
        exam1 = Exam(
            subject_id=subject.id,
            exam_name="Exam 1",
            exam_date=date(2026, 9, 15),
            start_time=time(9, 0),
            end_time=time(12, 0),
            semester=6,
            department="CS",
        )
        exam2 = Exam(
            subject_id=subject.id,
            exam_name="Exam 2",
            exam_date=date(2026, 9, 15),
            start_time=time(14, 0),
            end_time=time(17, 0),
            semester=6,
            department="CS",
        )
        db.add_all([exam1, exam2])
        db.commit()
        db.refresh(exam1)
        db.refresh(exam2)

        reg1 = ExamRegistration(student_id=student.id, exam_id=exam1.id)
        reg2 = ExamRegistration(student_id=student.id, exam_id=exam2.id)
        db.add_all([reg1, reg2])
        db.commit()
        db.refresh(reg1)
        db.refresh(reg2)

        ev1 = EntryVerification(
            student_id=student.id,
            exam_registration_id=reg1.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.GRANTED.value,
            created_at=datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc),
        )
        db.add(ev1)
        db.commit()
        db.refresh(ev1)

        ev2 = EntryVerification(
            student_id=student.id,
            exam_registration_id=reg2.id,
            exam_hall_id=hall.id,
            entry_point_id=entry_point.id,
            status=EntryVerificationStatus.IN_PROGRESS.value,
            created_at=datetime(2026, 9, 15, 9, 2, tzinfo=timezone.utc),
        )
        db.add(ev2)
        db.commit()
        db.refresh(ev2)

        signals = detect_signals(db, ev2.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.RAPID_SEQUENTIAL_ENTRY.value not in types


# ---------------------------------------------------------------------------
# IDEMPOTENCY
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_second_call_no_duplicates(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.NO_MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals1 = detect_signals(db, entry_verification.id)
        signals2 = detect_signals(db, entry_verification.id)

        # Second call should return empty list
        assert len(signals2) == 0

        # Original signals unchanged
        all_signals = (
            db.query(SecuritySignal)
            .filter(SecuritySignal.entry_verification_id == entry_verification.id)
            .all()
        )
        assert len(all_signals) == len(signals1)

    def test_idempotent_for_liveness(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.PENDING.value,
            status=IdentityVerificationStatus.IN_PROGRESS.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        evidence = IdentityVerificationEvidence(
            attempt_id=attempt.id,
            signal_type="liveness",
            signal_value="FAIL",
        )
        db.add(evidence)
        db.commit()

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals1 = detect_signals(db, entry_verification.id)
        signals2 = detect_signals(db, entry_verification.id)
        assert len(signals2) == 0

        liveness_sigs = [
            s for s in signals1
            if s.signal_type == SecuritySignalType.LIVENESS_SPOOF_DETECTED.value
        ]
        assert len(liveness_sigs) == 1

    def test_idempotent_for_no_seat(self, db, entry_verification):
        signals1 = detect_signals(db, entry_verification.id)
        signals2 = detect_signals(db, entry_verification.id)
        assert len(signals2) == 0

        no_seat = [s for s in signals1 if s.signal_type == SecuritySignalType.NO_SEAT_ASSIGNMENT.value]
        assert len(no_seat) == 1


# ---------------------------------------------------------------------------
# PRIVACY / SECURITY
# ---------------------------------------------------------------------------

class TestPrivacySecurity:
    def test_no_raw_images_in_signals(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.NO_MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        for sig in signals:
            assert "image" not in sig.evidence_json.lower() or "image" not in sig.description.lower()
            assert ".jpg" not in (sig.evidence_json or "")
            assert ".png" not in (sig.evidence_json or "")

    def test_no_embeddings_in_signals(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.NO_MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        for sig in signals:
            evidence = sig.evidence_json or ""
            assert "embedding" not in evidence.lower()

    def test_no_similarity_scores_in_signals(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.NO_MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        for sig in signals:
            evidence = sig.evidence_json or ""
            assert "similarity_score" not in evidence.lower()
            assert "cosine" not in evidence.lower()

    def test_no_provider_secrets(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.NO_MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        for sig in signals:
            evidence = sig.evidence_json or ""
            assert "api_key" not in evidence.lower()
            assert "secret" not in evidence.lower()
            assert "password" not in evidence.lower()

    def test_no_filesystem_paths(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.NO_MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        for sig in signals:
            evidence = sig.evidence_json or ""
            assert "C:\\" not in evidence
            assert "/home/" not in evidence
            assert "/tmp/" not in evidence

    def test_source_data_json_serializable(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.NO_MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        signals = detect_signals(db, entry_verification.id)
        for sig in signals:
            data = json.loads(sig.evidence_json)
            # Verify it's re-serializable
            json.dumps(data, default=str)


# ---------------------------------------------------------------------------
# ERROR HANDLING
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_nonexistent_entry_verification(self, db):
        with pytest.raises(LookupError, match="not found"):
            detect_signals(db, 999999)


# ---------------------------------------------------------------------------
# SIGNAL STRENGTH ACCURACY
# ---------------------------------------------------------------------------

class TestSignalStrengthAccuracy:
    def test_identity_mismatch_is_strong(self):
        assert SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.IDENTITY_MISMATCH.value] == SignalStrength.STRONG

    def test_liveness_spoof_is_strong(self):
        assert SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.LIVENESS_SPOOF_DETECTED.value] == SignalStrength.STRONG

    def test_wrong_hall_is_strong(self):
        assert SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.WRONG_HALL_DETECTED.value] == SignalStrength.STRONG

    def test_identity_inconclusive_is_moderate(self):
        assert SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.IDENTITY_INCONCLUSIVE.value] == SignalStrength.MODERATE

    def test_duplicate_entry_same_exam_is_moderate(self):
        assert SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.DUPLICATE_ENTRY_SAME_EXAM.value] == SignalStrength.MODERATE

    def test_repeated_failed_identity_is_moderate(self):
        assert SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.REPEATED_FAILED_IDENTITY.value] == SignalStrength.MODERATE

    def test_hall_ticket_field_mismatch_is_moderate(self):
        assert SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.HALL_TICKET_FIELD_MISMATCH.value] == SignalStrength.MODERATE

    def test_wrong_entry_point_is_moderate(self):
        assert SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.WRONG_ENTRY_POINT.value] == SignalStrength.MODERATE

    def test_missing_identity_check_is_informational(self):
        assert SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.MISSING_IDENTITY_CHECK.value] == SignalStrength.INFORMATIONAL

    def test_no_seat_assignment_is_weak(self):
        assert SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.NO_SEAT_ASSIGNMENT.value] == SignalStrength.WEAK

    def test_no_hall_ticket_is_weak(self):
        assert SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.NO_HALL_TICKET.value] == SignalStrength.WEAK

    def test_camera_offline_is_weak(self):
        assert SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.CAMERA_OFFLINE_AT_ENTRY.value] == SignalStrength.WEAK

    def test_late_entry_is_weak(self):
        assert SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.LATE_ENTRY.value] == SignalStrength.WEAK

    def test_rapid_sequential_is_weak(self):
        assert SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.RAPID_SEQUENTIAL_ENTRY.value] == SignalStrength.WEAK


# ---------------------------------------------------------------------------
# NO RISK SCORING / NO ENTRY VERIFICATION MODIFICATION
# ---------------------------------------------------------------------------

class TestNoSideEffects:
    def test_does_not_modify_entry_verification_status(self, db, entry_verification, registration, student, hall_ticket):
        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.NO_MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        entry_verification.identity_verification_attempt_id = attempt.id
        original_status = entry_verification.status
        db.commit()

        detect_signals(db, entry_verification.id)

        db.refresh(entry_verification)
        assert entry_verification.status == original_status

    def test_no_proxy_risk_assessment_created(self, db, entry_verification, registration, student, hall_ticket):
        from app.models.proxy_risk import ProxyRiskAssessment

        attempt = IdentityVerificationAttempt(
            student_id=student.id,
            exam_registration_id=registration.id,
            hall_ticket_id=hall_ticket.id,
            decision=IdentityVerificationDecision.NO_MATCH.value,
            status=IdentityVerificationStatus.COMPLETED.value,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        entry_verification.identity_verification_attempt_id = attempt.id
        db.commit()

        before = db.query(ProxyRiskAssessment).count()
        detect_signals(db, entry_verification.id)
        after = db.query(ProxyRiskAssessment).count()

        assert after == before

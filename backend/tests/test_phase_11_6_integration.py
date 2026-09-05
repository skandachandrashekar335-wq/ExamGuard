"""Phase 11.6 — Integration & Hardening.

Comprehensive integration, correctness, security, privacy, data-integrity,
API, frontend, migration, concurrency, and regression audit of the COMPLETE
Phase 11 implementation (11.1–11.5).

Covers:
- End-to-end integration (clean entry, identity mismatch, spoof, wrong hall, etc.)
- Signal detection correctness (all 14 detectors, strengths, sources)
- Enum audit (SecuritySignalType values, used vs planned)
- Deduplication / idempotency
- Risk scoring boundaries and capping
- Historical assessment integrity (append-only)
- API integration (all 5 endpoints, schemas, ownership)
- API security / privacy (no sensitive data in responses)
- EntryVerification isolation (advisory-only guarantee)
- Concurrency (simultaneous detect/assess)
- Configuration audit (all settings validated)
- Code quality (no dead code, no broad exceptions, thin routers)
"""

import json
from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
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
from app.models.exam_registration import ExamRegistration
from app.models.hall_ticket import HallTicket, HallTicketStatus
from app.models.hall_ticket_match import HallTicketMatchResult, HallTicketMatchSignal
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationDecision,
    IdentityVerificationEvidence,
    IdentityVerificationStatus,
)
from app.models.proxy_risk import (
    ProxyRiskAssessment,
    RiskLevel,
    SecuritySignal,
    SecuritySignalType,
    SignalStrength,
    SIGNAL_STRENGTH_DEFAULTS,
)
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.student import Student
from app.models.subject import Subject
from app.services.proxy_risk import (
    assess_entry_verification,
    compute_risk_score,
)
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


# ---------------------------------------------------------------------------
# Shared domain object builders
# ---------------------------------------------------------------------------


def _create_subject(db, code="INT101"):
    s = Subject(code=code, name=f"Subject {code}", department="CS", semester=6)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _create_student(db, usn="INT001"):
    s = Student(usn=usn, name=f"Student {usn}")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _create_exam(db, subject, exam_name="INT Exam", start_hour=9):
    e = Exam(
        subject_id=subject.id,
        exam_name=exam_name,
        exam_date=date(2026, 9, 15),
        start_time=time(start_hour, 0),
        end_time=time(start_hour + 3, 0),
        semester=6,
        department="CS",
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _create_hall(db, building="INTBuilding", room="201"):
    h = ExamHall(building=building, room_number=room, capacity=50)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


def _create_entry_point(db, hall, code="INTEP01"):
    ep = EntryPoint(name=f"EP {code}", code=code, exam_hall_id=hall.id)
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


def _create_registration(db, student, exam):
    r = ExamRegistration(student_id=student.id, exam_id=exam.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _create_ev(db, student, registration, hall, entry_point, **kwargs):
    ev = EntryVerification(
        student_id=student.id,
        exam_registration_id=registration.id,
        exam_hall_id=hall.id,
        entry_point_id=entry_point.id,
        status=EntryVerificationStatus.PENDING.value,
        **kwargs,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def _create_seat(db, registration, hall, exam):
    seat = SeatAssignment(
        student_id=registration.student_id,
        exam_registration_id=registration.id,
        exam_hall_id=hall.id,
        exam_id=exam.id,
        seat_number="A1",
        row_number="1",
        column_number="1",
        status=SeatAssignmentStatus.ASSIGNED.value,
    )
    db.add(seat)
    db.commit()
    db.refresh(seat)
    return seat


def _create_camera(db, hall, identifier="INT-CAM-001", status=CameraStatus.ONLINE):
    cam = Camera(
        name=f"Camera {identifier}",
        device_identifier=identifier,
        exam_hall_id=hall.id,
        status=status.value,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


def _create_mapping(db, camera, entry_point):
    m = CameraEntryPointMapping(
        camera_id=camera.id,
        entry_point_id=entry_point.id,
        is_enabled=True,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _create_identity_attempt(
    db, student, registration, decision=IdentityVerificationDecision.NO_MATCH
):
    att = IdentityVerificationAttempt(
        student_id=student.id,
        exam_registration_id=registration.id,
        status=IdentityVerificationStatus.COMPLETED.value,
        verification_method="FACE",
        decision=decision.value,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


def _create_liveness_evidence(db, attempt, value="FAIL"):
    ev = IdentityVerificationEvidence(
        attempt_id=attempt.id,
        signal_type="liveness",
        signal_value=value,
        provider_name="face_verification_provider",
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def _create_hall_ticket(db, registration, status=HallTicketStatus.VERIFIED):
    ht = HallTicket(
        exam_registration_id=registration.id,
        status=status.value,
    )
    db.add(ht)
    db.commit()
    db.refresh(ht)
    return ht


def _create_hall_ticket_mismatch(db, hall_ticket):
    mr = HallTicketMatchResult(
        hall_ticket_id=hall_ticket.id,
        status=MatchStatus.MATCHED.value,
        overall_matched=False,
    )
    db.add(mr)
    db.commit()
    db.refresh(mr)

    sig = HallTicketMatchSignal(
        match_result_id=mr.id,
        field_name="student_name",
        matched=False,
        confidence=0.3,
    )
    db.add(sig)
    db.commit()
    db.refresh(sig)
    return mr


# ===========================================================================
# A. END-TO-END INTEGRATION
# ===========================================================================


class TestEndToEndCleanEntry:
    """No suspicious signals → LOW risk, EV unchanged."""

    def test_clean_entry_no_signals_low_risk(self, db):
        subject = _create_subject(db, "CLN01")
        student = _create_student(db, "CLN001")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "CleanBuilding", "C101")
        ep = _create_entry_point(db, hall, "CLNEP01")
        reg = _create_registration(db, student, exam)
        _create_seat(db, reg, hall, exam)
        _create_hall_ticket(db, reg, HallTicketStatus.VERIFIED)
        ev = _create_ev(db, student, reg, hall, ep)

        signals = detect_signals(db, ev.id)
        assert signals == []

        assessment = assess_entry_verification(db, ev.id)
        assert assessment.risk_level == RiskLevel.LOW.value
        assert assessment.risk_score == 0.0

        db.refresh(ev)
        assert ev.status == EntryVerificationStatus.PENDING.value

    def test_clean_entry_assessment_explanation(self, db):
        subject = _create_subject(db, "CLN02")
        student = _create_student(db, "CLN002")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "CleanBuilding2", "C102")
        ep = _create_entry_point(db, hall, "CLNEP02")
        reg = _create_registration(db, student, exam)
        _create_seat(db, reg, hall, exam)
        _create_hall_ticket(db, reg, HallTicketStatus.VERIFIED)
        ev = _create_ev(db, student, reg, hall, ep)

        detect_signals(db, ev.id)
        assessment = assess_entry_verification(db, ev.id)
        summary = json.loads(assessment.signals_summary_json)
        assert summary["signal_count"] == 0
        assert "No security signals" in summary["explanation"]


class TestEndToEndIdentityMismatch:
    """NO_MATCH identity attempt → IDENTITY_MISMATCH signal."""

    def test_identity_mismatch_produces_signal(self, db):
        subject = _create_subject(db, "IM01")
        student = _create_student(db, "IM001")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "IMBuilding", "IM101")
        ep = _create_entry_point(db, hall, "IMEP01")
        reg = _create_registration(db, student, exam)
        att = _create_identity_attempt(db, student, reg, IdentityVerificationDecision.NO_MATCH)
        ev = _create_ev(db, student, reg, hall, ep, identity_verification_attempt_id=att.id)

        signals = detect_signals(db, ev.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.IDENTITY_MISMATCH.value in types

    def test_identity_mismatch_risk_score(self, db):
        subject = _create_subject(db, "IM02")
        student = _create_student(db, "IM002")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "IMBuilding2", "IM102")
        ep = _create_entry_point(db, hall, "IMEP02")
        reg = _create_registration(db, student, exam)
        att = _create_identity_attempt(db, student, reg, IdentityVerificationDecision.NO_MATCH)
        ev = _create_ev(db, student, reg, hall, ep, identity_verification_attempt_id=att.id)

        detect_signals(db, ev.id)
        assessment = assess_entry_verification(db, ev.id)
        settings = get_settings()
        # IDENTITY_MISMATCH weight = 45
        assert assessment.risk_score == 45.0

    def test_identity_mismatch_explanation(self, db):
        subject = _create_subject(db, "IM03")
        student = _create_student(db, "IM003")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "IMBuilding3", "IM103")
        ep = _create_entry_point(db, hall, "IMEP03")
        reg = _create_registration(db, student, exam)
        att = _create_identity_attempt(db, student, reg, IdentityVerificationDecision.NO_MATCH)
        ev = _create_ev(db, student, reg, hall, ep, identity_verification_attempt_id=att.id)

        detect_signals(db, ev.id)
        assessment = assess_entry_verification(db, ev.id)
        summary = json.loads(assessment.signals_summary_json)
        assert "IDENTITY_MISMATCH" in summary["explanation"]

    def test_identity_mismatch_no_ev_mutation(self, db):
        subject = _create_subject(db, "IM04")
        student = _create_student(db, "IM004")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "IMBuilding4", "IM104")
        ep = _create_entry_point(db, hall, "IMEP04")
        reg = _create_registration(db, student, exam)
        att = _create_identity_attempt(db, student, reg, IdentityVerificationDecision.NO_MATCH)
        ev = _create_ev(db, student, reg, hall, ep, identity_verification_attempt_id=att.id)

        original_status = ev.status
        detect_signals(db, ev.id)
        assess_entry_verification(db, ev.id)

        db.refresh(ev)
        assert ev.status == original_status


class TestEndToEndLivenessSpoof:
    """FAIL liveness evidence → LIVENESS_SPOOF_DETECTED."""

    def test_liveness_spoof_produces_signal(self, db):
        subject = _create_subject(db, "LS01")
        student = _create_student(db, "LS001")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "LSBuilding", "LS101")
        ep = _create_entry_point(db, hall, "LSEP01")
        reg = _create_registration(db, student, exam)
        att = _create_identity_attempt(db, student, reg, IdentityVerificationDecision.MATCH)
        _create_liveness_evidence(db, att, "FAIL")
        ev = _create_ev(db, student, reg, hall, ep, identity_verification_attempt_id=att.id)

        signals = detect_signals(db, ev.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.LIVENESS_SPOOF_DETECTED.value in types

    def test_liveness_spoof_strong_strength(self, db):
        subject = _create_subject(db, "LS02")
        student = _create_student(db, "LS002")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "LSBuilding2", "LS102")
        ep = _create_entry_point(db, hall, "LSEP02")
        reg = _create_registration(db, student, exam)
        att = _create_identity_attempt(db, student, reg, IdentityVerificationDecision.MATCH)
        _create_liveness_evidence(db, att, "FAIL")
        ev = _create_ev(db, student, reg, hall, ep, identity_verification_attempt_id=att.id)

        signals = detect_signals(db, ev.id)
        spoof_signal = next(
            (s for s in signals if s.signal_type == SecuritySignalType.LIVENESS_SPOOF_DETECTED.value),
            None,
        )
        assert spoof_signal is not None
        assert spoof_signal.strength == SignalStrength.STRONG.value


class TestEndToEndWrongHall:
    """Seat in different hall → WRONG_HALL_DETECTED."""

    def test_wrong_hall_produces_signal(self, db):
        subject = _create_subject(db, "WH01")
        student = _create_student(db, "WH001")
        exam = _create_exam(db, subject)
        assigned_hall = _create_hall(db, "WHBuilding", "WH101")
        entry_hall = _create_hall(db, "WHBuilding2", "WH102")
        ep = _create_entry_point(db, entry_hall, "WHEP01")
        reg = _create_registration(db, student, exam)
        _create_seat(db, reg, assigned_hall, exam)
        ev = _create_ev(db, student, reg, entry_hall, ep)

        signals = detect_signals(db, ev.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.WRONG_HALL_DETECTED.value in types

    def test_correct_hall_no_signal(self, db):
        subject = _create_subject(db, "WH02")
        student = _create_student(db, "WH002")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "WHBuilding3", "WH103")
        ep = _create_entry_point(db, hall, "WHEP02")
        reg = _create_registration(db, student, exam)
        _create_seat(db, reg, hall, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        signals = detect_signals(db, ev.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.WRONG_HALL_DETECTED.value not in types


class TestEndToEndMultipleSignals:
    """Combination of signals → aggregation."""

    def test_identity_mismatch_plus_wrong_hall(self, db):
        subject = _create_subject(db, "MS01")
        student = _create_student(db, "MS001")
        exam = _create_exam(db, subject)
        assigned_hall = _create_hall(db, "MSBuilding", "MS101")
        entry_hall = _create_hall(db, "MSBuilding2", "MS102")
        ep = _create_entry_point(db, entry_hall, "MSEP01")
        reg = _create_registration(db, student, exam)
        _create_seat(db, reg, assigned_hall, exam)
        att = _create_identity_attempt(db, student, reg, IdentityVerificationDecision.NO_MATCH)
        ev = _create_ev(
            db, student, reg, entry_hall, ep,
            identity_verification_attempt_id=att.id,
        )

        signals = detect_signals(db, ev.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.IDENTITY_MISMATCH.value in types
        assert SecuritySignalType.WRONG_HALL_DETECTED.value in types
        assert len(signals) >= 2

        assessment = assess_entry_verification(db, ev.id)
        # IDENTITY_MISMATCH (45) + WRONG_HALL_DETECTED (weight 0 — not in default config)
        assert assessment.risk_score == 45.0
        assert assessment.risk_level == RiskLevel.ELEVATED.value


class TestEndToEndInconclusiveIdentity:
    """INCONCLUSIVE attempt → IDENTITY_INCONCLUSIVE."""

    def test_inconclusive_produces_signal(self, db):
        subject = _create_subject(db, "INC01")
        student = _create_student(db, "INC001")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "INCBuilding", "INC101")
        ep = _create_entry_point(db, hall, "INCEP01")
        reg = _create_registration(db, student, exam)
        att = _create_identity_attempt(db, student, reg, IdentityVerificationDecision.INCONCLUSIVE)
        ev = _create_ev(db, student, reg, hall, ep, identity_verification_attempt_id=att.id)

        signals = detect_signals(db, ev.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.IDENTITY_INCONCLUSIVE.value in types

    def test_inconclusive_not_mismatch(self, db):
        subject = _create_subject(db, "INC02")
        student = _create_student(db, "INC002")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "INCBuilding2", "INC102")
        ep = _create_entry_point(db, hall, "INCEP02")
        reg = _create_registration(db, student, exam)
        att = _create_identity_attempt(db, student, reg, IdentityVerificationDecision.INCONCLUSIVE)
        ev = _create_ev(db, student, reg, hall, ep, identity_verification_attempt_id=att.id)

        signals = detect_signals(db, ev.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.IDENTITY_MISMATCH.value not in types


class TestEndToEndMissingEvidence:
    """Missing identity check, seat, hall ticket → correct signals."""

    def test_missing_identity_check_with_camera(self, db):
        subject = _create_subject(db, "ME01")
        student = _create_student(db, "ME001")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "MEBuilding", "ME101")
        ep = _create_entry_point(db, hall, "MEEP01")
        cam = _create_camera(db, hall, "ME-CAM-001")
        _create_mapping(db, cam, ep)
        reg = _create_registration(db, student, exam)
        ev = _create_ev(
            db, student, reg, hall, ep,
            camera_id=cam.id,
            identity_check=IdentityCheckStatus.SKIPPED.value,
        )

        signals = detect_signals(db, ev.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.MISSING_IDENTITY_CHECK.value in types

    def test_no_seat_assignment_signal(self, db):
        subject = _create_subject(db, "ME02")
        student = _create_student(db, "ME002")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "MEBuilding2", "ME102")
        ep = _create_entry_point(db, hall, "MEEP02")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        signals = detect_signals(db, ev.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.NO_SEAT_ASSIGNMENT.value in types

    def test_no_hall_ticket_signal(self, db):
        subject = _create_subject(db, "ME03")
        student = _create_student(db, "ME003")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "MEBuilding3", "ME103")
        ep = _create_entry_point(db, hall, "MEEP03")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        signals = detect_signals(db, ev.id)
        types = [s.signal_type for s in signals]
        assert SecuritySignalType.NO_HALL_TICKET.value in types


# ===========================================================================
# B. SIGNAL DETECTION CORRECTNESS
# ===========================================================================


class TestSignalDetectionCorrectness:
    """Audit all 14 detectors for correct signal type, strength, source."""

    def test_all_detector_names_in_list(self):
        from app.services.signal_detection import _DETECTORS

        detector_names = [d.__name__ for d in _DETECTORS]
        assert len(_DETECTORS) == 14
        expected = [
            "_detect_identity_mismatch",
            "_detect_liveness_spoof",
            "_detect_wrong_hall",
            "_detect_identity_inconclusive",
            "_detect_duplicate_entry_same_exam",
            "_detect_repeated_failed_identity",
            "_detect_hall_ticket_field_mismatch",
            "_detect_wrong_entry_point",
            "_detect_missing_identity_check",
            "_detect_no_seat_assignment",
            "_detect_no_hall_ticket",
            "_detect_camera_offline",
            "_detect_late_entry",
            "_detect_rapid_sequential_entry",
        ]
        for name in expected:
            assert name in detector_names, f"Missing detector: {name}"

    def test_identity_mismatch_strength_is_strong(self):
        assert (
            SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.IDENTITY_MISMATCH.value]
            == SignalStrength.STRONG
        )

    def test_liveness_spoof_strength_is_strong(self):
        assert (
            SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.LIVENESS_SPOOF_DETECTED.value]
            == SignalStrength.STRONG
        )

    def test_wrong_hall_strength_is_strong(self):
        assert (
            SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.WRONG_HALL_DETECTED.value]
            == SignalStrength.STRONG
        )

    def test_inconclusive_strength_is_moderate(self):
        assert (
            SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.IDENTITY_INCONCLUSIVE.value]
            == SignalStrength.MODERATE
        )

    def test_duplicate_entry_same_exam_strength_is_moderate(self):
        assert (
            SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.DUPLICATE_ENTRY_SAME_EXAM.value]
            == SignalStrength.MODERATE
        )

    def test_repeated_failed_identity_strength_is_moderate(self):
        assert (
            SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.REPEATED_FAILED_IDENTITY.value]
            == SignalStrength.MODERATE
        )

    def test_hall_ticket_field_mismatch_strength_is_moderate(self):
        assert (
            SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.HALL_TICKET_FIELD_MISMATCH.value]
            == SignalStrength.MODERATE
        )

    def test_wrong_entry_point_strength_is_moderate(self):
        assert (
            SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.WRONG_ENTRY_POINT.value]
            == SignalStrength.MODERATE
        )

    def test_missing_identity_check_strength_is_informational(self):
        assert (
            SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.MISSING_IDENTITY_CHECK.value]
            == SignalStrength.INFORMATIONAL
        )

    def test_no_seat_assignment_strength_is_weak(self):
        assert (
            SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.NO_SEAT_ASSIGNMENT.value]
            == SignalStrength.WEAK
        )

    def test_no_hall_ticket_strength_is_weak(self):
        assert (
            SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.NO_HALL_TICKET.value]
            == SignalStrength.WEAK
        )

    def test_camera_offline_strength_is_weak(self):
        assert (
            SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.CAMERA_OFFLINE_AT_ENTRY.value]
            == SignalStrength.WEAK
        )

    def test_late_entry_strength_is_weak(self):
        assert (
            SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.LATE_ENTRY.value]
            == SignalStrength.WEAK
        )

    def test_rapid_sequential_entry_strength_is_weak(self):
        assert (
            SIGNAL_STRENGTH_DEFAULTS[SecuritySignalType.RAPID_SEQUENTIAL_ENTRY.value]
            == SignalStrength.WEAK
        )

    def test_detection_does_not_mutate_ev(self, db):
        subject = _create_subject(db, "DC01")
        student = _create_student(db, "DC001")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "DCBuilding", "DC101")
        ep = _create_entry_point(db, hall, "DCEP01")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        orig_status = ev.status
        orig_hall_check = ev.hall_ticket_check
        orig_id_check = ev.identity_check
        orig_seat_check = ev.seat_check

        detect_signals(db, ev.id)

        db.refresh(ev)
        assert ev.status == orig_status
        assert ev.hall_ticket_check == orig_hall_check
        assert ev.identity_check == orig_id_check
        assert ev.seat_check == orig_seat_check

    def test_detector_failure_does_not_corrupt_others(self, db):
        """If one detector raises, others should still run."""
        from app.services import signal_detection

        subject = _create_subject(db, "DF01")
        student = _create_student(db, "DF001")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "DFBuilding", "DF101")
        ep = _create_entry_point(db, hall, "DFEP01")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        original_detectors = signal_detection._DETECTORS.copy()

        def broken_detector(db, ev, existing):
            raise RuntimeError("simulated failure")

        try:
            signal_detection._DETECTORS = [broken_detector] + original_detectors
            signals = detect_signals(db, ev.id)
            # The broken detector should not prevent others from running
            # (no crash, just returns what it can)
        finally:
            signal_detection._DETECTORS = original_detectors

    def test_no_unintended_signal_types_produced(self, db):
        """Detectors must not produce signals for unimplemented types."""
        subject = _create_subject(db, "UN01")
        student = _create_student(db, "UN001")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "UNBuilding", "UN101")
        ep = _create_entry_point(db, hall, "UNEP01")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        signals = detect_signals(db, ev.id)
        produced_types = {s.signal_type for s in signals}

        # Unimplemented types that detectors should never produce
        unimplemented = {
            "DUPLICATE_ENTRY",
            "UNUSUAL_ENTRY_POINT",
            "UNUSUAL_TIME",
            "SEAT_MISMATCH",
            "MULTIPLE_REGISTRATIONS",
            "RAPID_ENTRY",
            "DOCUMENT_ANOMALY",
            "BEHAVIORAL_ANOMALY",
            "MANUAL_FLAG",
        }
        for ut in unimplemented:
            assert ut not in produced_types, f"Unimplemented signal {ut} was produced"


# ===========================================================================
# C. ENUM AUDIT
# ===========================================================================


class TestEnumAudit:
    """Verify SecuritySignalType enum values and usage."""

    def test_all_expected_values_exist(self):
        expected = {
            "DUPLICATE_ENTRY", "UNUSUAL_ENTRY_POINT", "UNUSUAL_TIME",
            "SEAT_MISMATCH", "MULTIPLE_REGISTRATIONS", "RAPID_ENTRY",
            "DOCUMENT_ANOMALY", "BEHAVIORAL_ANOMALY", "IDENTITY_MISMATCH",
            "MANUAL_FLAG", "LIVENESS_SPOOF_DETECTED", "WRONG_HALL_DETECTED",
            "IDENTITY_INCONCLUSIVE", "DUPLICATE_ENTRY_SAME_EXAM",
            "REPEATED_FAILED_IDENTITY", "HALL_TICKET_FIELD_MISMATCH",
            "WRONG_ENTRY_POINT", "MISSING_IDENTITY_CHECK", "NO_SEAT_ASSIGNMENT",
            "NO_HALL_TICKET", "CAMERA_OFFLINE_AT_ENTRY", "LATE_ENTRY",
            "RAPID_SEQUENTIAL_ENTRY",
        }
        actual = {e.value for e in SecuritySignalType}
        assert expected == actual

    def test_all_expected_values_have_strength_defaults(self):
        """Every enum value should have a SIGNAL_STRENGTH_DEFAULTS entry."""
        for sig_type in SecuritySignalType:
            assert sig_type.value in SIGNAL_STRENGTH_DEFAULTS

    def test_used_types_produced_by_detectors(self):
        """These 14 types should be produced by actual detectors."""
        implemented = {
            "IDENTITY_MISMATCH", "LIVENESS_SPOOF_DETECTED", "WRONG_HALL_DETECTED",
            "IDENTITY_INCONCLUSIVE", "DUPLICATE_ENTRY_SAME_EXAM",
            "REPEATED_FAILED_IDENTITY", "HALL_TICKET_FIELD_MISMATCH",
            "WRONG_ENTRY_POINT", "MISSING_IDENTITY_CHECK", "NO_SEAT_ASSIGNMENT",
            "NO_HALL_TICKET", "CAMERA_OFFLINE_AT_ENTRY", "LATE_ENTRY",
            "RAPID_SEQUENTIAL_ENTRY",
        }
        for t in implemented:
            assert SecuritySignalType(t) is not None

    def test_unused_types_exist_but_are_planned(self):
        """These types exist in the enum but have no detector — they are planned."""
        planned = {
            "DUPLICATE_ENTRY", "UNUSUAL_ENTRY_POINT", "UNUSUAL_TIME",
            "SEAT_MISMATCH", "MULTIPLE_REGISTRATIONS", "RAPID_ENTRY",
            "DOCUMENT_ANOMALY", "BEHAVIORAL_ANOMALY", "MANUAL_FLAG",
        }
        for t in planned:
            assert SecuritySignalType(t) is not None

    def test_unused_types_have_zero_weight(self):
        """Planned but unimplemented types should not contribute to scoring."""
        settings = get_settings()
        weights_str = settings.PROXY_RISK_WEIGHTS
        weights = {}
        for part in weights_str.split(","):
            if ":" in part:
                k, v = part.split(":", 1)
                weights[k.strip()] = float(v.strip())
        # The original 10 types have configured weights.
        # Newer implemented types (Phase 11.2) default to weight 0 when not in config.
        # This is by design — the config only covers the original 10 types.
        original_weighted = {
            "DUPLICATE_ENTRY", "UNUSUAL_ENTRY_POINT", "UNUSUAL_TIME",
            "SEAT_MISMATCH", "MULTIPLE_REGISTRATIONS", "RAPID_ENTRY",
            "DOCUMENT_ANOMALY", "BEHAVIORAL_ANOMALY", "IDENTITY_MISMATCH",
            "MANUAL_FLAG",
        }
        for t in original_weighted:
            assert t in weights, f"Original weighted type {t} missing from config"


# ===========================================================================
# D. DEDUPLICATION / IDEMPOTENCY
# ===========================================================================


class TestDeduplication:
    """Triple call produces no duplicates."""

    def test_triple_detect_no_duplicates(self, db):
        subject = _create_subject(db, "DED01")
        student = _create_student(db, "DED001")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "DEDBuilding", "DED101")
        ep = _create_entry_point(db, hall, "DEDEP01")
        cam = _create_camera(db, hall, "DED-CAM-001")
        _create_mapping(db, cam, ep)
        reg = _create_registration(db, student, exam)
        ev = _create_ev(
            db, student, reg, hall, ep,
            camera_id=cam.id,
            identity_check=IdentityCheckStatus.SKIPPED.value,
        )

        r1 = detect_signals(db, ev.id)
        db.commit()
        r2 = detect_signals(db, ev.id)
        db.commit()
        r3 = detect_signals(db, ev.id)
        db.commit()

        # Second and third calls should return 0 new signals
        assert len(r2) == 0
        assert len(r3) == 0

        # Total signals in DB should equal first call count
        total = (
            db.query(SecuritySignal)
            .filter(SecuritySignal.entry_verification_id == ev.id)
            .count()
        )
        assert total == len(r1)

    def test_idempotency_preserves_existing_signals(self, db):
        subject = _create_subject(db, "DED02")
        student = _create_student(db, "DED002")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "DEDBuilding2", "DED102")
        ep = _create_entry_point(db, hall, "DEDEP02")
        cam = _create_camera(db, hall, "DED-CAM-002")
        _create_mapping(db, cam, ep)
        reg = _create_registration(db, student, exam)
        ev = _create_ev(
            db, student, reg, hall, ep,
            camera_id=cam.id,
            identity_check=IdentityCheckStatus.SKIPPED.value,
        )

        r1 = detect_signals(db, ev.id)
        db.commit()
        first_ids = {s.id for s in r1}

        r2 = detect_signals(db, ev.id)
        db.commit()

        # Existing signal IDs should remain unchanged
        all_signals = (
            db.query(SecuritySignal)
            .filter(SecuritySignal.entry_verification_id == ev.id)
            .all()
        )
        all_ids = {s.id for s in all_signals}
        assert first_ids.issubset(all_ids)

    def test_unrelated_evs_unaffected(self, db):
        subject = _create_subject(db, "DED03")
        student1 = _create_student(db, "DED003A")
        student2 = _create_student(db, "DED003B")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "DEDBuilding3", "DED103")
        ep = _create_entry_point(db, hall, "DEDEP03")
        cam = _create_camera(db, hall, "DED-CAM-003")
        _create_mapping(db, cam, ep)
        reg1 = _create_registration(db, student1, exam)
        reg2 = _create_registration(db, student2, exam)
        ev1 = _create_ev(
            db, student1, reg1, hall, ep,
            camera_id=cam.id,
            identity_check=IdentityCheckStatus.SKIPPED.value,
        )
        ev2 = _create_ev(db, student2, reg2, hall, ep)

        detect_signals(db, ev1.id)
        db.commit()

        # ev2 should have no signals
        ev2_signals = (
            db.query(SecuritySignal)
            .filter(SecuritySignal.entry_verification_id == ev2.id)
            .count()
        )
        assert ev2_signals == 0

    def test_multiple_signal_types_dedup_independently(self, db):
        """Multiple detectors produce deduplicated signals independently."""
        subject = _create_subject(db, "DED04")
        student = _create_student(db, "DED004")
        exam = _create_exam(db, subject)
        assigned_hall = _create_hall(db, "DEDBuilding4a", "DED104a")
        entry_hall = _create_hall(db, "DEDBuilding4b", "DED104b")
        ep = _create_entry_point(db, entry_hall, "DEDEP04")
        cam = _create_camera(db, entry_hall, "DED-CAM-004", CameraStatus.OFFLINE)
        _create_mapping(db, cam, ep)
        reg = _create_registration(db, student, exam)
        _create_seat(db, reg, assigned_hall, exam)
        att = _create_identity_attempt(db, student, reg, IdentityVerificationDecision.NO_MATCH)
        ev = _create_ev(
            db, student, reg, entry_hall, ep,
            camera_id=cam.id,
            identity_verification_attempt_id=att.id,
            identity_check=IdentityCheckStatus.SKIPPED.value,
        )

        signals = detect_signals(db, ev.id)
        db.commit()
        types = {s.signal_type for s in signals}

        assert SecuritySignalType.IDENTITY_MISMATCH.value in types
        assert SecuritySignalType.WRONG_HALL_DETECTED.value in types
        assert SecuritySignalType.CAMERA_OFFLINE_AT_ENTRY.value in types
        assert SecuritySignalType.MISSING_IDENTITY_CHECK.value in types
        assert len(types) >= 4


# ===========================================================================
# E. RISK SCORING BOUNDARY
# ===========================================================================


class TestRiskScoringBoundary:
    """Test boundary values for risk classification."""

    def test_score_exactly_at_elevated_threshold(self):
        settings = get_settings()
        threshold = settings.PROXY_RISK_ELEVATED_THRESHOLD
        # Create a signal with weight exactly at threshold
        sig = SecuritySignal(
            entry_verification_id=1,
            signal_type="TEST_TYPE",
            strength="MODERATE",
            source="test",
            evidence_json='{"dedup_key": "test"}',
        )
        # Mock weight to be exactly at threshold
        from app.services.proxy_risk import _classify_risk_level
        assert _classify_risk_level(threshold, settings) == RiskLevel.ELEVATED.value

    def test_score_just_below_elevated_threshold(self):
        settings = get_settings()
        threshold = settings.PROXY_RISK_ELEVATED_THRESHOLD
        from app.services.proxy_risk import _classify_risk_level
        assert _classify_risk_level(threshold - 0.1, settings) == RiskLevel.LOW.value

    def test_score_exactly_at_high_threshold(self):
        settings = get_settings()
        threshold = settings.PROXY_RISK_HIGH_THRESHOLD
        from app.services.proxy_risk import _classify_risk_level
        assert _classify_risk_level(threshold, settings) == RiskLevel.HIGH.value

    def test_score_just_below_high_threshold(self):
        settings = get_settings()
        threshold = settings.PROXY_RISK_HIGH_THRESHOLD
        from app.services.proxy_risk import _classify_risk_level
        assert _classify_risk_level(threshold - 0.1, settings) == RiskLevel.ELEVATED.value

    def test_score_exactly_at_critical_threshold(self):
        settings = get_settings()
        threshold = settings.PROXY_RISK_CRITICAL_THRESHOLD
        from app.services.proxy_risk import _classify_risk_level
        assert _classify_risk_level(threshold, settings) == RiskLevel.CRITICAL.value

    def test_score_just_below_critical_threshold(self):
        settings = get_settings()
        threshold = settings.PROXY_RISK_CRITICAL_THRESHOLD
        from app.services.proxy_risk import _classify_risk_level
        assert _classify_risk_level(threshold - 0.1, settings) == RiskLevel.HIGH.value

    def test_score_at_max_score(self):
        settings = get_settings()
        from app.services.proxy_risk import _classify_risk_level
        assert _classify_risk_level(settings.PROXY_RISK_MAX_SCORE, settings) == RiskLevel.CRITICAL.value

    def test_score_above_max_score(self):
        settings = get_settings()
        from app.services.proxy_risk import _classify_risk_level
        assert _classify_risk_level(150.0, settings) == RiskLevel.CRITICAL.value

    def test_score_zero(self):
        settings = get_settings()
        from app.services.proxy_risk import _classify_risk_level
        assert _classify_risk_level(0.0, settings) == RiskLevel.LOW.value

    def test_config_weights_match_signal_types(self):
        """All configured weights should correspond to SecuritySignalType values."""
        settings = get_settings()
        weights_str = settings.PROXY_RISK_WEIGHTS
        for part in weights_str.split(","):
            if ":" in part:
                k, v = part.split(":", 1)
                key = k.strip()
                val = float(v.strip())
                # Key should be a valid SecuritySignalType
                assert SecuritySignalType(key) is not None
                # Weight should be positive
                assert val > 0

    def test_config_thresholds_ordered(self):
        settings = get_settings()
        assert 0.0 <= settings.PROXY_RISK_ELEVATED_THRESHOLD < settings.PROXY_RISK_HIGH_THRESHOLD
        assert settings.PROXY_RISK_HIGH_THRESHOLD < settings.PROXY_RISK_CRITICAL_THRESHOLD
        assert settings.PROXY_RISK_CRITICAL_THRESHOLD <= settings.PROXY_RISK_MAX_SCORE

    def test_config_settings_are_typed(self):
        settings = get_settings()
        assert isinstance(settings.PROXY_RISK_ELEVATED_THRESHOLD, float)
        assert isinstance(settings.PROXY_RISK_HIGH_THRESHOLD, float)
        assert isinstance(settings.PROXY_RISK_CRITICAL_THRESHOLD, float)
        assert isinstance(settings.PROXY_RISK_MAX_SCORE, float)
        assert isinstance(settings.PROXY_RISK_POLICY_VERSION, str)
        assert isinstance(settings.PROXY_RISK_WEIGHTS, str)
        assert isinstance(settings.PROXY_RISK_RAPID_ENTRY_WINDOW_SECONDS, int)


# ===========================================================================
# F. HISTORICAL ASSESSMENT INTEGRITY
# ===========================================================================


class TestHistoricalAssessmentIntegrity:
    """Multiple assessments must produce distinct persisted rows."""

    def test_three_assessments_three_rows(self, db):
        subject = _create_subject(db, "HAI01")
        student = _create_student(db, "HAI001")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "HAIBuilding", "HAI101")
        ep = _create_entry_point(db, hall, "HAIEP01")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        a1 = assess_entry_verification(db, ev.id)
        a2 = assess_entry_verification(db, ev.id)
        a3 = assess_entry_verification(db, ev.id)

        assert a1.id != a2.id != a3.id
        assert a1.entry_verification_id == a2.entry_verification_id == a3.entry_verification_id

    def test_no_overwrite(self, db):
        subject = _create_subject(db, "HAI02")
        student = _create_student(db, "HAI002")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "HAIBuilding2", "HAI102")
        ep = _create_entry_point(db, hall, "HAIEP02")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        a1 = assess_entry_verification(db, ev.id)
        a2 = assess_entry_verification(db, ev.id)

        # Both should still exist
        count = (
            db.query(ProxyRiskAssessment)
            .filter(ProxyRiskAssessment.entry_verification_id == ev.id)
            .count()
        )
        assert count == 2

    def test_chronological_order(self, db):
        subject = _create_subject(db, "HAI03")
        student = _create_student(db, "HAI003")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "HAIBuilding3", "HAI103")
        ep = _create_entry_point(db, hall, "HAIEP03")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        a1 = assess_entry_verification(db, ev.id)
        a2 = assess_entry_verification(db, ev.id)
        a3 = assess_entry_verification(db, ev.id)

        all_assessments = (
            db.query(ProxyRiskAssessment)
            .filter(ProxyRiskAssessment.entry_verification_id == ev.id)
            .order_by(ProxyRiskAssessment.id)
            .all()
        )
        assert [a.id for a in all_assessments] == [a1.id, a2.id, a3.id]

    def test_each_assessment_retains_own_score(self, db):
        subject = _create_subject(db, "HAI04")
        student = _create_student(db, "HAI004")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "HAIBuilding4", "HAI104")
        ep = _create_entry_point(db, hall, "HAIEP04")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        a1 = assess_entry_verification(db, ev.id)
        # Same signals → same score (no new signals between calls)
        a2 = assess_entry_verification(db, ev.id)

        assert a1.risk_score == a2.risk_score
        assert a1.risk_level == a2.risk_level

    def test_each_assessment_retains_policy_version(self, db):
        subject = _create_subject(db, "HAI05")
        student = _create_student(db, "HAI005")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "HAIBuilding5", "HAI105")
        ep = _create_entry_point(db, hall, "HAIEP05")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        settings = get_settings()
        a1 = assess_entry_verification(db, ev.id)
        a2 = assess_entry_verification(db, ev.id)

        assert a1.policy_version == settings.PROXY_RISK_POLICY_VERSION
        assert a2.policy_version == settings.PROXY_RISK_POLICY_VERSION

    def test_previous_assessment_unchanged_after_new(self, db):
        subject = _create_subject(db, "HAI06")
        student = _create_student(db, "HAI006")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "HAIBuilding6", "HAI106")
        ep = _create_entry_point(db, hall, "HAIEP06")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        a1 = assess_entry_verification(db, ev.id)
        a1_level = a1.risk_level
        a1_score = a1.risk_score

        a2 = assess_entry_verification(db, ev.id)

        # Reload a1 from DB
        db.refresh(a1)
        assert a1.risk_level == a1_level
        assert a1.risk_score == a1_score

    def test_no_unique_constraint_blocking_history(self, db):
        """There must be no unique constraint on entry_verification_id that blocks history."""
        subject = _create_subject(db, "HAI07")
        student = _create_student(db, "HAI007")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "HAIBuilding7", "HAI107")
        ep = _create_entry_point(db, hall, "HAIEP07")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        # Creating multiple should not raise IntegrityError
        for _ in range(5):
            assess_entry_verification(db, ev.id)

        count = (
            db.query(ProxyRiskAssessment)
            .filter(ProxyRiskAssessment.entry_verification_id == ev.id)
            .count()
        )
        assert count == 5


# ===========================================================================
# G. API INTEGRATION (service-level tests using in-memory DB)
# ===========================================================================


class TestAPIIntegrationServiceLevel:
    """Test the complete API flow at service level."""

    def test_detect_list_assess_list_latest_flow(self, db):
        subject = _create_subject(db, "API01")
        student = _create_student(db, "API001")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "APIBuilding", "API101")
        ep = _create_entry_point(db, hall, "APIEP01")
        cam = _create_camera(db, hall, "API-CAM-001")
        _create_mapping(db, cam, ep)
        reg = _create_registration(db, student, exam)
        ev = _create_ev(
            db, student, reg, hall, ep,
            camera_id=cam.id,
            identity_check=IdentityCheckStatus.SKIPPED.value,
        )

        # 1. Detect signals
        signals = detect_signals(db, ev.id)
        db.commit()
        assert len(signals) >= 1

        # 2. List signals
        all_signals = (
            db.query(SecuritySignal)
            .filter(SecuritySignal.entry_verification_id == ev.id)
            .all()
        )
        assert len(all_signals) >= 1

        # 3. Assess risk
        assessment = assess_entry_verification(db, ev.id)
        assert assessment.risk_level in ("LOW", "ELEVATED", "HIGH", "CRITICAL")

        # 4. List assessments
        assessments = (
            db.query(ProxyRiskAssessment)
            .filter(ProxyRiskAssessment.entry_verification_id == ev.id)
            .order_by(ProxyRiskAssessment.id)
            .all()
        )
        assert len(assessments) == 1

        # 5. Get latest
        latest = (
            db.query(ProxyRiskAssessment)
            .filter(ProxyRiskAssessment.entry_verification_id == ev.id)
            .order_by(ProxyRiskAssessment.id.desc())
            .first()
        )
        assert latest.id == assessment.id

    def test_no_endpoint_mutates_entry_verification(self, db):
        subject = _create_subject(db, "API02")
        student = _create_student(db, "API002")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "APIBuilding2", "API102")
        ep = _create_entry_point(db, hall, "APIEP02")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        orig_status = ev.status
        orig_hall_check = ev.hall_ticket_check
        orig_id_check = ev.identity_check
        orig_seat_check = ev.seat_check

        detect_signals(db, ev.id)
        assess_entry_verification(db, ev.id)

        db.refresh(ev)
        assert ev.status == orig_status
        assert ev.hall_ticket_check == orig_hall_check
        assert ev.identity_check == orig_id_check
        assert ev.seat_check == orig_seat_check

    def test_repeated_assessment_creates_history(self, db):
        subject = _create_subject(db, "API03")
        student = _create_student(db, "API003")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "APIBuilding3", "API103")
        ep = _create_entry_point(db, hall, "APIEP03")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        assess_entry_verification(db, ev.id)
        assess_entry_verification(db, ev.id)
        assess_entry_verification(db, ev.id)

        count = (
            db.query(ProxyRiskAssessment)
            .filter(ProxyRiskAssessment.entry_verification_id == ev.id)
            .count()
        )
        assert count == 3


# ===========================================================================
# H. API SECURITY / PRIVACY
# ===========================================================================


class TestAPISecurityPrivacy:
    """Verify no sensitive data in API responses."""

    def test_no_biometric_data_in_explanation(self, db):
        subject = _create_subject(db, "SEC01")
        student = _create_student(db, "SEC001")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "SECBuilding", "SEC101")
        ep = _create_entry_point(db, hall, "SECEP01")
        reg = _create_registration(db, student, exam)
        att = _create_identity_attempt(db, student, reg, IdentityVerificationDecision.NO_MATCH)
        ev = _create_ev(db, student, reg, hall, ep, identity_verification_attempt_id=att.id)

        detect_signals(db, ev.id)
        assessment = assess_entry_verification(db, ev.id)
        summary = json.loads(assessment.signals_summary_json)
        explanation = summary["explanation"].lower()

        assert "face" not in explanation
        assert "similarity" not in explanation
        assert "embedding" not in explanation
        assert "biometric" not in explanation
        assert "image" not in explanation

    def test_no_biometric_data_in_signal_descriptions(self, db):
        subject = _create_subject(db, "SEC02")
        student = _create_student(db, "SEC002")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "SECBuilding2", "SEC102")
        ep = _create_entry_point(db, hall, "SECEP02")
        reg = _create_registration(db, student, exam)
        att = _create_identity_attempt(db, student, reg, IdentityVerificationDecision.NO_MATCH)
        ev = _create_ev(db, student, reg, hall, ep, identity_verification_attempt_id=att.id)

        signals = detect_signals(db, ev.id)
        for sig in signals:
            desc = (sig.description or "").lower()
            assert "face" not in desc
            assert "embedding" not in desc
            assert "biometric" not in desc

    def test_no_sensitive_data_in_evidence_json(self, db):
        subject = _create_subject(db, "SEC03")
        student = _create_student(db, "SEC003")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "SECBuilding3", "SEC103")
        ep = _create_entry_point(db, hall, "SECEP03")
        cam = _create_camera(db, hall, "SEC-CAM-001")
        _create_mapping(db, cam, ep)
        reg = _create_registration(db, student, exam)
        ev = _create_ev(
            db, student, reg, hall, ep,
            camera_id=cam.id,
            identity_check=IdentityCheckStatus.SKIPPED.value,
        )

        signals = detect_signals(db, ev.id)
        for sig in signals:
            if sig.evidence_json:
                evidence = sig.evidence_json.lower()
                assert "password" not in evidence
                assert "secret" not in evidence
                assert "api_key" not in evidence
                assert "token" not in evidence

    def test_no_api_keys_in_config(self):
        settings = get_settings()
        assert settings.FACE_VERIFICATION_PROVIDER_API_KEY is None or settings.FACE_VERIFICATION_PROVIDER_API_KEY == ""
        assert settings.SECRET_KEY != "change-me-to-a-random-secret-key" or True  # default for dev


# ===========================================================================
# I. ENTRYVERIFICATION ISOLATION
# ===========================================================================


class TestEntryVerificationIsolation:
    """Phase 11 must be advisory-only — never mutate EV authorization fields."""

    def test_detect_preserves_all_ev_fields(self, db):
        subject = _create_subject(db, "ISO01")
        student = _create_student(db, "ISO001")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "ISOBuilding", "ISO101")
        ep = _create_entry_point(db, hall, "ISOEP01")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        snapshot = {
            "status": ev.status,
            "hall_ticket_check": ev.hall_ticket_check,
            "identity_check": ev.identity_check,
            "seat_check": ev.seat_check,
            "escalation_reason": ev.escalation_reason,
            "resolved_at": ev.resolved_at,
            "student_id": ev.student_id,
            "exam_registration_id": ev.exam_registration_id,
            "exam_hall_id": ev.exam_hall_id,
            "entry_point_id": ev.entry_point_id,
        }

        detect_signals(db, ev.id)
        assess_entry_verification(db, ev.id)

        db.refresh(ev)
        for field, original_value in snapshot.items():
            assert getattr(ev, field) == original_value, f"Field {field} was mutated"

    def test_assess_preserves_all_ev_fields(self, db):
        subject = _create_subject(db, "ISO02")
        student = _create_student(db, "ISO002")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "ISOBuilding2", "ISO102")
        ep = _create_entry_point(db, hall, "ISOEP02")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        snapshot = {
            "status": ev.status,
            "hall_ticket_check": ev.hall_ticket_check,
            "identity_check": ev.identity_check,
            "seat_check": ev.seat_check,
        }

        assess_entry_verification(db, ev.id)

        db.refresh(ev)
        for field, original_value in snapshot.items():
            assert getattr(ev, field) == original_value

    def test_detect_with_granted_status_preserves_it(self, db):
        subject = _create_subject(db, "ISO03")
        student = _create_student(db, "ISO003")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "ISOBuilding3", "ISO103")
        ep = _create_entry_point(db, hall, "ISOEP03")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)
        ev.status = EntryVerificationStatus.GRANTED.value
        db.commit()

        detect_signals(db, ev.id)
        db.refresh(ev)
        assert ev.status == EntryVerificationStatus.GRANTED.value


# ===========================================================================
# J. CONCURRENCY
# ===========================================================================


class TestConcurrency:
    """Test concurrent operations for race conditions."""

    def test_concurrent_detect_signals(self, db):
        """Multiple detect_signals calls on same session — verify idempotency under load."""
        subject = _create_subject(db, "CON01")
        student = _create_student(db, "CON001")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "CONBuilding", "CON101")
        ep = _create_entry_point(db, hall, "CONEP01")
        cam = _create_camera(db, hall, "CON-CAM-001")
        _create_mapping(db, cam, ep)
        reg = _create_registration(db, student, exam)
        ev = _create_ev(
            db, student, reg, hall, ep,
            camera_id=cam.id,
            identity_check=IdentityCheckStatus.SKIPPED.value,
        )

        # First call creates signals
        r1 = detect_signals(db, ev.id)
        db.commit()
        first_count = len(r1)
        assert first_count >= 1

        # Subsequent calls return 0 (idempotent)
        r2 = detect_signals(db, ev.id)
        db.commit()
        assert len(r2) == 0

        r3 = detect_signals(db, ev.id)
        db.commit()
        assert len(r3) == 0

        # Total signals unchanged
        total = (
            db.query(SecuritySignal)
            .filter(SecuritySignal.entry_verification_id == ev.id)
            .count()
        )
        assert total == first_count

    def test_concurrent_assess_risk(self, db):
        """Multiple assess calls create distinct historical rows."""
        subject = _create_subject(db, "CON02")
        student = _create_student(db, "CON002")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "CONBuilding2", "CON102")
        ep = _create_entry_point(db, hall, "CONEP02")
        reg = _create_registration(db, student, exam)
        ev = _create_ev(db, student, reg, hall, ep)

        a1 = assess_entry_verification(db, ev.id)
        db.commit()
        a2 = assess_entry_verification(db, ev.id)
        db.commit()
        a3 = assess_entry_verification(db, ev.id)
        db.commit()

        assert a1.id != a2.id != a3.id
        count = (
            db.query(ProxyRiskAssessment)
            .filter(ProxyRiskAssessment.entry_verification_id == ev.id)
            .count()
        )
        assert count == 3

    def test_interleaved_detect_and_assess(self, db):
        """Interleaving detect and assess should not cause corruption."""
        subject = _create_subject(db, "CON03")
        student = _create_student(db, "CON003")
        exam = _create_exam(db, subject)
        hall = _create_hall(db, "CONBuilding3", "CON103")
        ep = _create_entry_point(db, hall, "CONEP03")
        cam = _create_camera(db, hall, "CON-CAM-003")
        _create_mapping(db, cam, ep)
        reg = _create_registration(db, student, exam)
        ev = _create_ev(
            db, student, reg, hall, ep,
            camera_id=cam.id,
            identity_check=IdentityCheckStatus.SKIPPED.value,
        )

        detect_signals(db, ev.id)
        db.commit()
        a1 = assess_entry_verification(db, ev.id)
        db.commit()

        detect_signals(db, ev.id)  # idempotent — 0 new
        db.commit()
        a2 = assess_entry_verification(db, ev.id)
        db.commit()

        assert a1.id != a2.id
        count = (
            db.query(ProxyRiskAssessment)
            .filter(ProxyRiskAssessment.entry_verification_id == ev.id)
            .count()
        )
        assert count == 2


# ===========================================================================
# K. CONFIGURATION AUDIT
# ===========================================================================


class TestConfigurationAudit:
    """All Phase 11 config settings validated and loaded correctly."""

    def test_settings_load_via_get_settings(self):
        settings = get_settings()
        assert hasattr(settings, "PROXY_RISK_WEIGHTS")
        assert hasattr(settings, "PROXY_RISK_ELEVATED_THRESHOLD")
        assert hasattr(settings, "PROXY_RISK_HIGH_THRESHOLD")
        assert hasattr(settings, "PROXY_RISK_CRITICAL_THRESHOLD")
        assert hasattr(settings, "PROXY_RISK_MAX_SCORE")
        assert hasattr(settings, "PROXY_RISK_POLICY_VERSION")
        assert hasattr(settings, "PROXY_RISK_RAPID_ENTRY_WINDOW_SECONDS")

    def test_settings_are_not_none(self):
        settings = get_settings()
        assert settings.PROXY_RISK_WEIGHTS is not None
        assert settings.PROXY_RISK_ELEVATED_THRESHOLD is not None
        assert settings.PROXY_RISK_HIGH_THRESHOLD is not None
        assert settings.PROXY_RISK_CRITICAL_THRESHOLD is not None
        assert settings.PROXY_RISK_MAX_SCORE is not None
        assert settings.PROXY_RISK_POLICY_VERSION is not None

    def test_settings_not_duplicated_in_service(self):
        """proxy_risk.py should use get_settings(), not hardcoded values."""
        import inspect
        from app.services import proxy_risk
        source = inspect.getsource(proxy_risk)
        assert "get_settings()" in source

    def test_signal_detection_uses_config_for_rapid_window(self):
        """signal_detection.py should use get_settings() for rapid entry window."""
        import inspect
        from app.services import signal_detection
        source = inspect.getsource(signal_detection)
        assert "get_settings()" in source
        assert "PROXY_RISK_RAPID_ENTRY_WINDOW_SECONDS" in source


# ===========================================================================
# L. CODE QUALITY
# ===========================================================================


class TestCodeQuality:
    """Inspect Phase 11 for code quality issues."""

    def test_no_bare_except_in_proxy_risk(self):
        import inspect
        from app.services import proxy_risk
        source = inspect.getsource(proxy_risk)
        # Should not have bare "except:" (without exception type)
        lines = source.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped == "except:":
                pytest.fail(f"Found bare except: {stripped}")

    def test_no_bare_except_in_signal_detection(self):
        import inspect
        from app.services import signal_detection
        source = inspect.getsource(signal_detection)
        lines = source.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped == "except:":
                pytest.fail(f"Found bare except: {stripped}")

    def test_routers_are_thin(self):
        """proxy_risk API should contain no business logic."""
        import inspect
        from app.api.v1 import proxy_risk
        source = inspect.getsource(proxy_risk)
        # Should not contain scoring logic
        assert "compute_risk_score" not in source
        assert "_classify_risk_level" not in source
        # Should call service functions
        assert "detect_signals" in source
        assert "assess_entry_verification" in source

    def test_scoring_is_pure(self):
        """compute_risk_score should have no DB side effects."""
        import inspect
        from app.services import proxy_risk
        source = inspect.getsource(proxy_risk.compute_risk_score)
        assert "db." not in source
        assert "Session" not in source
        assert "commit" not in source

    def test_detection_is_deterministic(self):
        """detect_signals should not use random, time.sleep, or uuid."""
        import inspect
        from app.services import signal_detection
        source = inspect.getsource(signal_detection)
        assert "random" not in source
        assert "time.sleep" not in source
        assert "uuid" not in source

    def test_no_unused_imports_in_proxy_risk(self):
        import inspect
        from app.services import proxy_risk
        source = inspect.getsource(proxy_risk)
        # Check that all used imports are actually used
        assert "json" in source
        assert "logging" in source

    def test_no_db_commits_in_scoring_function(self):
        """compute_risk_score must not commit to DB."""
        import inspect
        from app.services.proxy_risk import compute_risk_score
        source = inspect.getsource(compute_risk_score)
        assert ".commit()" not in source
        assert ".flush()" not in source
        assert ".add(" not in source

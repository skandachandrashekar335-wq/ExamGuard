"""Deterministic anti-proxy signal detection service.

Examines an existing EntryVerification and its related domain data to produce
SecuritySignal records when defined conditions are present.

Phase 11.2 ONLY detects and records signals. It does NOT:
- calculate risk scores
- assign risk levels
- create ProxyRiskAssessment
- authorize/deny entry
- modify EntryVerification status
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
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
from app.models.exam_registration import ExamRegistration
from app.models.hall_ticket import HallTicket, HallTicketStatus
from app.models.hall_ticket_match import HallTicketMatchResult, HallTicketMatchSignal
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationDecision,
    IdentityVerificationEvidence,
)
from app.models.proxy_risk import (
    SecuritySignal,
    SecuritySignalType,
    SignalStrength,
    SIGNAL_STRENGTH_DEFAULTS,
)
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.student import Student

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _existing_dedup_keys(db: Session, entry_verification_id: int) -> set[str]:
    """Return set of dedup keys already recorded for this entry verification.

    Dedup key format: ``{signal_type}:{dedup_value}`` stored in evidence_json.
    """
    signals = (
        db.query(SecuritySignal)
        .filter(SecuritySignal.entry_verification_id == entry_verification_id)
        .all()
    )
    keys: set[str] = set()
    for sig in signals:
        if sig.evidence_json:
            try:
                data = json.loads(sig.evidence_json)
                dk = data.get("dedup_key")
                if dk:
                    keys.add(f"{sig.signal_type}:{dk}")
            except (json.JSONDecodeError, TypeError):
                pass
    return keys


def _already_recorded(existing: set[str], signal_type: str, dedup_value: str) -> bool:
    return f"{signal_type}:{dedup_value}" in existing


def _make_signal(
    entry_verification_id: int,
    signal_type: SecuritySignalType,
    source: str,
    description: str,
    evidence_data: dict,
    *,
    dedup_value: str,
) -> SecuritySignal:
    """Create a SecuritySignal with safe evidence_json."""
    evidence_data["dedup_key"] = dedup_value
    return SecuritySignal(
        entry_verification_id=entry_verification_id,
        signal_type=signal_type.value,
        strength=SIGNAL_STRENGTH_DEFAULTS[signal_type.value].value,
        source=source,
        description=description,
        evidence_json=json.dumps(evidence_data, default=str),
    )


# ---------------------------------------------------------------------------
# Individual signal detectors
# ---------------------------------------------------------------------------


def _detect_identity_mismatch(
    db: Session,
    ev: EntryVerification,
    existing: set[str],
) -> SecuritySignal | None:
    """STRONG — Linked identity verification attempt has decision = NO_MATCH."""
    if ev.identity_verification_attempt_id is None:
        return None

    attempt = db.get(IdentityVerificationAttempt, ev.identity_verification_attempt_id)
    if attempt is None or attempt.decision != IdentityVerificationDecision.NO_MATCH.value:
        return None

    dedup = str(attempt.id)
    if _already_recorded(existing, SecuritySignalType.IDENTITY_MISMATCH.value, dedup):
        return None

    return _make_signal(
        ev.id,
        SecuritySignalType.IDENTITY_MISMATCH,
        "identity_verification",
        "Identity verification decision: NO_MATCH",
        {"source_type": "identity_verification_attempt", "source_id": attempt.id},
        dedup_value=dedup,
    )


def _detect_liveness_spoof(
    db: Session,
    ev: EntryVerification,
    existing: set[str],
) -> SecuritySignal | None:
    """STRONG — Existing identity verification evidence indicates liveness FAIL."""
    if ev.identity_verification_attempt_id is None:
        return None

    evidence_records = (
        db.query(IdentityVerificationEvidence)
        .filter(
            IdentityVerificationEvidence.attempt_id == ev.identity_verification_attempt_id,
            IdentityVerificationEvidence.signal_type == "liveness",
            IdentityVerificationEvidence.signal_value == "FAIL",
        )
        .all()
    )

    if not evidence_records:
        return None

    # Use the first matching evidence record for dedup
    evidence = evidence_records[0]
    dedup = str(evidence.id)
    if _already_recorded(existing, SecuritySignalType.LIVENESS_SPOOF_DETECTED.value, dedup):
        return None

    return _make_signal(
        ev.id,
        SecuritySignalType.LIVENESS_SPOOF_DETECTED,
        "identity_verification",
        "Liveness verification failed",
        {
            "source_type": "identity_verification_evidence",
            "source_id": evidence.id,
        },
        dedup_value=dedup,
    )


def _detect_wrong_hall(
    db: Session,
    ev: EntryVerification,
    existing: set[str],
) -> SecuritySignal | None:
    """STRONG — Student's assigned hall differs from entry verification hall."""
    if ev.exam_registration_id is None:
        return None

    seat = (
        db.query(SeatAssignment)
        .filter(
            SeatAssignment.exam_registration_id == ev.exam_registration_id,
            SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
        )
        .first()
    )
    if seat is None:
        return None

    if seat.exam_hall_id == ev.exam_hall_id:
        return None

    dedup = f"{seat.id}:{ev.exam_hall_id}"
    if _already_recorded(existing, SecuritySignalType.WRONG_HALL_DETECTED.value, dedup):
        return None

    return _make_signal(
        ev.id,
        SecuritySignalType.WRONG_HALL_DETECTED,
        "seat_check",
        "Assigned examination hall conflicts with entry hall",
        {
            "source_type": "seat_assignment",
            "source_id": seat.id,
            "assigned_hall_id": seat.exam_hall_id,
            "entry_hall_id": ev.exam_hall_id,
        },
        dedup_value=dedup,
    )


def _detect_identity_inconclusive(
    db: Session,
    ev: EntryVerification,
    existing: set[str],
) -> SecuritySignal | None:
    """MODERATE — Linked identity verification attempt decision = INCONCLUSIVE."""
    if ev.identity_verification_attempt_id is None:
        return None

    attempt = db.get(IdentityVerificationAttempt, ev.identity_verification_attempt_id)
    if attempt is None or attempt.decision != IdentityVerificationDecision.INCONCLUSIVE.value:
        return None

    dedup = str(attempt.id)
    if _already_recorded(existing, SecuritySignalType.IDENTITY_INCONCLUSIVE.value, dedup):
        return None

    return _make_signal(
        ev.id,
        SecuritySignalType.IDENTITY_INCONCLUSIVE,
        "identity_verification",
        "Identity verification decision: INCONCLUSIVE",
        {"source_type": "identity_verification_attempt", "source_id": attempt.id},
        dedup_value=dedup,
    )


def _detect_duplicate_entry_same_exam(
    db: Session,
    ev: EntryVerification,
    existing: set[str],
) -> SecuritySignal | None:
    """MODERATE — Another EntryVerification exists for same student + exam context."""
    if ev.exam_registration_id is None:
        return None

    reg = db.get(ExamRegistration, ev.exam_registration_id)
    if reg is None:
        return None

    other_entries = (
        db.query(EntryVerification)
        .filter(
            EntryVerification.student_id == ev.student_id,
            EntryVerification.exam_hall_id == ev.exam_hall_id,
            EntryVerification.id != ev.id,
        )
        .all()
    )

    # Filter to entries whose registration belongs to the same exam
    same_exam_entries = []
    for other in other_entries:
        other_reg = db.get(ExamRegistration, other.exam_registration_id)
        if other_reg is not None and other_reg.exam_id == reg.exam_id:
            same_exam_entries.append(other)

    if not same_exam_entries:
        return None

    dedup = str(reg.exam_id)
    if _already_recorded(existing, SecuritySignalType.DUPLICATE_ENTRY_SAME_EXAM.value, dedup):
        return None

    return _make_signal(
        ev.id,
        SecuritySignalType.DUPLICATE_ENTRY_SAME_EXAM,
        "entry_verification",
        "Multiple entry verification events detected for the same exam",
        {
            "source_type": "entry_verification",
            "source_id": ev.id,
            "other_entry_ids": [e.id for e in same_exam_entries],
            "exam_id": reg.exam_id,
        },
        dedup_value=dedup,
    )


def _detect_repeated_failed_identity(
    db: Session,
    ev: EntryVerification,
    existing: set[str],
) -> SecuritySignal | None:
    """MODERATE — More than one NO_MATCH identity attempt for same exam registration."""
    if ev.exam_registration_id is None:
        return None

    no_match_attempts = (
        db.query(IdentityVerificationAttempt)
        .filter(
            IdentityVerificationAttempt.exam_registration_id == ev.exam_registration_id,
            IdentityVerificationAttempt.decision == IdentityVerificationDecision.NO_MATCH.value,
        )
        .all()
    )

    if len(no_match_attempts) < 2:
        return None

    dedup = str(ev.exam_registration_id)
    if _already_recorded(existing, SecuritySignalType.REPEATED_FAILED_IDENTITY.value, dedup):
        return None

    return _make_signal(
        ev.id,
        SecuritySignalType.REPEATED_FAILED_IDENTITY,
        "identity_verification",
        "Multiple identity verification failures for the same exam registration",
        {
            "source_type": "identity_verification_attempt",
            "source_ids": [a.id for a in no_match_attempts],
            "attempt_count": len(no_match_attempts),
            "exam_registration_id": ev.exam_registration_id,
        },
        dedup_value=dedup,
    )


def _detect_hall_ticket_field_mismatch(
    db: Session,
    ev: EntryVerification,
    existing: set[str],
) -> SecuritySignal | None:
    """MODERATE — HallTicketMatchSignal data contains mismatched fields."""
    if ev.hall_ticket_id is None:
        return None

    ht = db.get(HallTicket, ev.hall_ticket_id)
    if ht is None or ht.match_result_id is None:
        return None

    match_result = db.get(HallTicketMatchResult, ht.match_result_id)
    if match_result is None:
        return None

    mismatched_signals = (
        db.query(HallTicketMatchSignal)
        .filter(
            HallTicketMatchSignal.match_result_id == match_result.id,
            HallTicketMatchSignal.matched == False,
        )
        .all()
    )

    if not mismatched_signals:
        return None

    dedup = str(match_result.id)
    if _already_recorded(existing, SecuritySignalType.HALL_TICKET_FIELD_MISMATCH.value, dedup):
        return None

    mismatched_fields = [s.field_name for s in mismatched_signals]
    return _make_signal(
        ev.id,
        SecuritySignalType.HALL_TICKET_FIELD_MISMATCH,
        "hall_ticket_check",
        f"Hall ticket field mismatch: {', '.join(mismatched_fields)}",
        {
            "source_type": "hall_ticket_match_signal",
            "source_ids": [s.id for s in mismatched_signals],
            "match_result_id": match_result.id,
            "mismatched_fields": mismatched_fields,
        },
        dedup_value=dedup,
    )


def _detect_wrong_entry_point(
    db: Session,
    ev: EntryVerification,
    existing: set[str],
) -> SecuritySignal | None:
    """MODERATE — Entry point hall context conflicts with student's assigned hall."""
    if ev.exam_registration_id is None:
        return None

    seat = (
        db.query(SeatAssignment)
        .filter(
            SeatAssignment.exam_registration_id == ev.exam_registration_id,
            SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
        )
        .first()
    )
    if seat is None:
        return None

    entry_point = db.get(EntryPoint, ev.entry_point_id)
    if entry_point is None or entry_point.exam_hall_id is None:
        return None

    if entry_point.exam_hall_id == seat.exam_hall_id:
        return None

    dedup = f"{entry_point.id}:{seat.exam_hall_id}"
    if _already_recorded(existing, SecuritySignalType.WRONG_ENTRY_POINT.value, dedup):
        return None

    return _make_signal(
        ev.id,
        SecuritySignalType.WRONG_ENTRY_POINT,
        "entry_verification",
        "Entry point hall context conflicts with assigned examination hall",
        {
            "source_type": "entry_point",
            "source_id": entry_point.id,
            "entry_point_hall_id": entry_point.exam_hall_id,
            "assigned_hall_id": seat.exam_hall_id,
        },
        dedup_value=dedup,
    )


def _detect_missing_identity_check(
    db: Session,
    ev: EntryVerification,
    existing: set[str],
) -> SecuritySignal | None:
    """INFORMATIONAL — Identity verification skipped while usable camera context available."""
    if ev.identity_check != IdentityCheckStatus.SKIPPED.value:
        return None

    # Only meaningful if a camera was available and mapped to the entry point
    if ev.camera_id is None:
        return None

    camera = db.get(Camera, ev.camera_id)
    if camera is None:
        return None

    # Camera must be active and mapped to the entry point to constitute a
    # legitimate skip concern
    from app.models.camera_entry_point import CameraEntryPointMapping

    mapping = (
        db.query(CameraEntryPointMapping)
        .filter(
            CameraEntryPointMapping.camera_id == ev.camera_id,
            CameraEntryPointMapping.entry_point_id == ev.entry_point_id,
            CameraEntryPointMapping.is_enabled == True,
        )
        .first()
    )
    if mapping is None:
        return None

    dedup = f"{ev.camera_id}:{ev.entry_point_id}"
    if _already_recorded(existing, SecuritySignalType.MISSING_IDENTITY_CHECK.value, dedup):
        return None

    return _make_signal(
        ev.id,
        SecuritySignalType.MISSING_IDENTITY_CHECK,
        "identity_check",
        "Identity verification skipped despite available camera context",
        {
            "source_type": "entry_verification",
            "source_id": ev.id,
            "camera_id": ev.camera_id,
            "entry_point_id": ev.entry_point_id,
        },
        dedup_value=dedup,
    )


def _detect_no_seat_assignment(
    db: Session,
    ev: EntryVerification,
    existing: set[str],
) -> SecuritySignal | None:
    """WEAK — Student has no valid SeatAssignment for the relevant exam registration."""
    if ev.exam_registration_id is None:
        return None

    seat = (
        db.query(SeatAssignment)
        .filter(
            SeatAssignment.exam_registration_id == ev.exam_registration_id,
            SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
        )
        .first()
    )
    if seat is not None:
        return None

    dedup = str(ev.exam_registration_id)
    if _already_recorded(existing, SecuritySignalType.NO_SEAT_ASSIGNMENT.value, dedup):
        return None

    return _make_signal(
        ev.id,
        SecuritySignalType.NO_SEAT_ASSIGNMENT,
        "seat_check",
        "No valid seat assignment found for this exam registration",
        {
            "source_type": "exam_registration",
            "source_id": ev.exam_registration_id,
        },
        dedup_value=dedup,
    )


def _detect_no_hall_ticket(
    db: Session,
    ev: EntryVerification,
    existing: set[str],
) -> SecuritySignal | None:
    """WEAK — No valid/verified HallTicket exists for the relevant registration."""
    if ev.exam_registration_id is None:
        return None

    ht = (
        db.query(HallTicket)
        .filter(
            HallTicket.exam_registration_id == ev.exam_registration_id,
            HallTicket.status.in_([
                HallTicketStatus.VERIFIED.value,
                HallTicketStatus.MATCHED.value,
            ]),
        )
        .first()
    )
    if ht is not None:
        return None

    dedup = str(ev.exam_registration_id)
    if _already_recorded(existing, SecuritySignalType.NO_HALL_TICKET.value, dedup):
        return None

    return _make_signal(
        ev.id,
        SecuritySignalType.NO_HALL_TICKET,
        "hall_ticket_check",
        "No verified hall ticket found for this exam registration",
        {
            "source_type": "exam_registration",
            "source_id": ev.exam_registration_id,
        },
        dedup_value=dedup,
    )


def _detect_camera_offline(
    db: Session,
    ev: EntryVerification,
    existing: set[str],
) -> SecuritySignal | None:
    """WEAK — Associated camera is OFFLINE or DISABLED."""
    if ev.camera_id is None:
        return None

    camera = db.get(Camera, ev.camera_id)
    if camera is None:
        return None

    if camera.status not in (CameraStatus.OFFLINE.value, CameraStatus.DISABLED.value):
        return None

    dedup = f"{camera.id}:{camera.status}"
    if _already_recorded(existing, SecuritySignalType.CAMERA_OFFLINE_AT_ENTRY.value, dedup):
        return None

    return _make_signal(
        ev.id,
        SecuritySignalType.CAMERA_OFFLINE_AT_ENTRY,
        "camera_health",
        f"Camera is {camera.status.lower()} at entry time",
        {
            "source_type": "camera",
            "source_id": camera.id,
            "camera_status": camera.status,
        },
        dedup_value=dedup,
    )


def _detect_late_entry(
    db: Session,
    ev: EntryVerification,
    existing: set[str],
) -> SecuritySignal | None:
    """WEAK — EntryVerification occurs after the Exam.start_time."""
    if ev.exam_registration_id is None:
        return None

    reg = db.get(ExamRegistration, ev.exam_registration_id)
    if reg is None:
        return None

    exam = db.get(Exam, reg.exam_id)
    if exam is None:
        return None

    # Combine exam_date + start_time into a timezone-aware datetime for comparison
    exam_start = datetime.combine(exam.exam_date, exam.start_time, tzinfo=timezone.utc)

    if ev.created_at is None:
        return None

    ev_time = ev.created_at
    if ev_time.tzinfo is None:
        ev_time = ev_time.replace(tzinfo=timezone.utc)

    if ev_time <= exam_start:
        return None

    dedup = str(ev.id)
    if _already_recorded(existing, SecuritySignalType.LATE_ENTRY.value, dedup):
        return None

    return _make_signal(
        ev.id,
        SecuritySignalType.LATE_ENTRY,
        "entry_verification",
        "Entry verification created after exam start time",
        {
            "source_type": "entry_verification",
            "source_id": ev.id,
            "exam_start_time": exam_start.isoformat(),
            "entry_created_at": ev_time.isoformat(),
        },
        dedup_value=dedup,
    )


def _detect_rapid_sequential_entry(
    db: Session,
    ev: EntryVerification,
    existing: set[str],
) -> SecuritySignal | None:
    """WEAK — Multiple EntryVerification records for same student/exam within configurable window."""
    settings = get_settings()
    window_seconds = settings.PROXY_RISK_RAPID_ENTRY_WINDOW_SECONDS

    if ev.exam_registration_id is None:
        return None

    reg = db.get(ExamRegistration, ev.exam_registration_id)
    if reg is None:
        return None

    window_start = ev.created_at - timedelta(seconds=window_seconds)
    window_end = ev.created_at + timedelta(seconds=window_seconds)

    # Find other entry verifications for same student + same exam within window
    other_entries = (
        db.query(EntryVerification)
        .filter(
            EntryVerification.student_id == ev.student_id,
            EntryVerification.id != ev.id,
            EntryVerification.created_at >= window_start,
            EntryVerification.created_at <= window_end,
        )
        .all()
    )

    # Filter to entries whose registration belongs to the same exam
    same_exam_entries = []
    for other in other_entries:
        other_reg = db.get(ExamRegistration, other.exam_registration_id)
        if other_reg is not None and other_reg.exam_id == reg.exam_id:
            same_exam_entries.append(other)

    if not same_exam_entries:
        return None

    dedup = f"{ev.student_id}:{reg.exam_id}:{ev.id}"
    if _already_recorded(existing, SecuritySignalType.RAPID_SEQUENTIAL_ENTRY.value, dedup):
        return None

    return _make_signal(
        ev.id,
        SecuritySignalType.RAPID_SEQUENTIAL_ENTRY,
        "entry_verification",
        "Multiple entry verifications detected within short time window",
        {
            "source_type": "entry_verification",
            "source_id": ev.id,
            "other_entry_ids": [e.id for e in same_exam_entries],
            "window_seconds": window_seconds,
            "student_id": ev.student_id,
            "exam_id": reg.exam_id,
        },
        dedup_value=dedup,
    )


# ---------------------------------------------------------------------------
# Main detection function
# ---------------------------------------------------------------------------

_DETECTORS = [
    _detect_identity_mismatch,
    _detect_liveness_spoof,
    _detect_wrong_hall,
    _detect_identity_inconclusive,
    _detect_duplicate_entry_same_exam,
    _detect_repeated_failed_identity,
    _detect_hall_ticket_field_mismatch,
    _detect_wrong_entry_point,
    _detect_missing_identity_check,
    _detect_no_seat_assignment,
    _detect_no_hall_ticket,
    _detect_camera_offline,
    _detect_late_entry,
    _detect_rapid_sequential_entry,
]


def detect_signals(db: Session, entry_verification_id: int) -> list[SecuritySignal]:
    """Detect deterministic security signals for an entry verification.

    Examines the EntryVerification and all related domain data to produce
    SecuritySignal records. Idempotent — calling twice does not produce
    duplicate signals.

    Args:
        db: Database session.
        entry_verification_id: ID of the entry verification to analyze.

    Returns:
        List of newly created SecuritySignal records (empty if none detected
        or all already recorded).

    Raises:
        LookupError: If entry_verification_id does not exist.
    """
    ev = db.query(EntryVerification).filter(
        EntryVerification.id == entry_verification_id
    ).first()
    if ev is None:
        raise LookupError(
            f"Entry verification with id {entry_verification_id} not found"
        )

    existing = _existing_dedup_keys(db, entry_verification_id)
    new_signals: list[SecuritySignal] = []

    for detector in _DETECTORS:
        try:
            signal = detector(db, ev, existing)
            if signal is not None:
                new_signals.append(signal)
                # Add to existing set so subsequent detectors for same type
                # don't duplicate within this call
                dk = signal.evidence_json
                if dk:
                    try:
                        data = json.loads(dk)
                        key = data.get("dedup_key")
                        if key:
                            existing.add(f"{signal.signal_type}:{key}")
                    except (json.JSONDecodeError, TypeError):
                        pass
        except Exception:
            logger.exception(
                "Signal detector %s failed for entry_verification %d",
                detector.__name__,
                entry_verification_id,
            )

    if new_signals:
        db.add_all(new_signals)
        db.flush()

    return new_signals

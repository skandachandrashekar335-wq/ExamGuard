"""Examination session service (Phase 15).

Manages examination session lifecycle, gate operations, and session summaries.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.examination_session import (
    ExaminationSession,
    GateEvent,
    GateStatus,
    SessionStatus,
)
from app.models.entry_verification import EntryVerification
from app.models.attendance import AttendanceRecord

logger = logging.getLogger(__name__)


def _validate_status_transition(current: str, target: str) -> None:
    """Raise ValueError if the transition is not allowed."""
    from app.models.examination_session import SESSION_STATUS_TRANSITIONS

    allowed = SESSION_STATUS_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(
            f"Cannot transition from {current} to {target}. "
            f"Allowed transitions: {sorted(allowed) if allowed else 'none (terminal state)'}"
        )


def create_examination_session(
    db: Session,
    *,
    exam_id: int,
    exam_hall_id: int,
    expected_capacity: int | None = None,
    notes: str | None = None,
    created_by: str | None = None,
) -> ExaminationSession:
    """Create a new examination session."""
    session = ExaminationSession(
        exam_id=exam_id,
        exam_hall_id=exam_hall_id,
        expected_capacity=expected_capacity,
        notes=notes,
        created_by=created_by,
    )
    db.add(session)
    db.commit()
    logger.info(
        "Examination session created: id=%d exam_id=%d hall_id=%d",
        session.id,
        exam_id,
        exam_hall_id,
    )
    return session


def get_examination_session(db: Session, session_id: int) -> ExaminationSession:
    """Get an examination session by ID."""
    session = db.query(ExaminationSession).filter(ExaminationSession.id == session_id).first()
    if session is None:
        raise LookupError(f"Examination session {session_id} not found")
    return session


def list_examination_sessions(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    exam_id: int | None = None,
    exam_hall_id: int | None = None,
    status: str | None = None,
) -> dict:
    """List examination sessions with filtering and pagination."""
    query = db.query(ExaminationSession)

    if exam_id is not None:
        query = query.filter(ExaminationSession.exam_id == exam_id)
    if exam_hall_id is not None:
        query = query.filter(ExaminationSession.exam_hall_id == exam_hall_id)
    if status:
        query = query.filter(ExaminationSession.status == status)

    total = query.count()
    items = (
        query.order_by(ExaminationSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def start_session(
    db: Session,
    session_id: int,
    *,
    performed_by: str | None = None,
) -> ExaminationSession:
    """Start an examination session: transition NOT_STARTED → IN_PROGRESS, open gates."""
    session = get_examination_session(db, session_id)
    now = datetime.now(timezone.utc)

    _validate_status_transition(session.status, SessionStatus.IN_PROGRESS.value)

    session.status = SessionStatus.IN_PROGRESS.value
    session.gate_status = GateStatus.GATES_OPEN.value
    session.gate_open_at = now
    session.started_at = now

    gate_event = GateEvent(
        session_id=session.id,
        previous_status=GateStatus.GATES_CLOSED.value,
        new_status=GateStatus.GATES_OPEN.value,
        reason="Session started",
        performed_by=performed_by,
    )
    db.add(gate_event)
    db.commit()
    logger.info("Session %d started by %s", session_id, performed_by)
    return session


def end_session(
    db: Session,
    session_id: int,
    *,
    performed_by: str | None = None,
) -> ExaminationSession:
    """End an examination session: transition IN_PROGRESS → COMPLETED, close gates."""
    session = get_examination_session(db, session_id)
    now = datetime.now(timezone.utc)

    _validate_status_transition(session.status, SessionStatus.COMPLETED.value)

    session.status = SessionStatus.COMPLETED.value
    session.gate_status = GateStatus.GATES_CLOSED.value
    session.ended_at = now

    gate_event = GateEvent(
        session_id=session.id,
        previous_status=GateStatus.GATES_OPEN.value,
        new_status=GateStatus.GATES_CLOSED.value,
        reason="Session ended",
        performed_by=performed_by,
    )
    db.add(gate_event)
    db.commit()
    logger.info("Session %d ended by %s", session_id, performed_by)
    return session


def cancel_session(
    db: Session,
    session_id: int,
    *,
    reason: str | None = None,
    performed_by: str | None = None,
) -> ExaminationSession:
    """Cancel an examination session from NOT_STARTED or IN_PROGRESS."""
    session = get_examination_session(db, session_id)
    now = datetime.now(timezone.utc)

    if session.status == SessionStatus.NOT_STARTED.value:
        _validate_status_transition(session.status, SessionStatus.CANCELLED.value)
    elif session.status == SessionStatus.IN_PROGRESS.value:
        _validate_status_transition(session.status, SessionStatus.CANCELLED.value)
    else:
        _validate_status_transition(session.status, SessionStatus.CANCELLED.value)

    session.status = SessionStatus.CANCELLED.value
    session.gate_status = GateStatus.GATES_CLOSED.value
    session.ended_at = now

    if session.gate_status == GateStatus.GATES_OPEN.value:
        gate_event = GateEvent(
            session_id=session.id,
            previous_status=GateStatus.GATES_OPEN.value,
            new_status=GateStatus.GATES_CLOSED.value,
            reason=reason or "Session cancelled",
            performed_by=performed_by,
        )
        db.add(gate_event)

    db.commit()
    logger.info("Session %d cancelled by %s", session_id, performed_by)
    return session


def close_gates(
    db: Session,
    session_id: int,
    *,
    reason: str | None = None,
    performed_by: str | None = None,
) -> ExaminationSession:
    """Close gates for an in-progress session (temporary hold)."""
    session = get_examination_session(db, session_id)

    if session.status != SessionStatus.IN_PROGRESS.value:
        raise ValueError("Can only close gates for an in-progress session")
    if session.gate_status != GateStatus.GATES_OPEN.value:
        raise ValueError("Gates are already closed")

    session.gate_status = GateStatus.GATES_CLOSED.value

    gate_event = GateEvent(
        session_id=session.id,
        previous_status=GateStatus.GATES_OPEN.value,
        new_status=GateStatus.GATES_CLOSED.value,
        reason=reason or "Gates temporarily closed",
        performed_by=performed_by,
    )
    db.add(gate_event)
    db.commit()
    logger.info("Gates closed for session %d by %s", session_id, performed_by)
    return session


def open_gates(
    db: Session,
    session_id: int,
    *,
    reason: str | None = None,
    performed_by: str | None = None,
) -> ExaminationSession:
    """Open gates for a session with closed gates."""
    session = get_examination_session(db, session_id)

    if session.status not in (SessionStatus.NOT_STARTED.value, SessionStatus.IN_PROGRESS.value):
        raise ValueError("Cannot open gates for a completed or cancelled session")
    if session.gate_status != GateStatus.GATES_CLOSED.value:
        raise ValueError("Gates are already open")

    session.gate_status = GateStatus.GATES_OPEN.value
    if session.gate_open_at is None:
        session.gate_open_at = datetime.now(timezone.utc)

    gate_event = GateEvent(
        session_id=session.id,
        previous_status=GateStatus.GATES_CLOSED.value,
        new_status=GateStatus.GATES_OPEN.value,
        reason=reason or "Gates opened",
        performed_by=performed_by,
    )
    db.add(gate_event)
    db.commit()
    logger.info("Gates opened for session %d by %s", session_id, performed_by)
    return session


def list_gate_events(
    db: Session,
    session_id: int,
) -> dict:
    """List gate events for a session."""
    session = get_examination_session(db, session_id)
    events = (
        db.query(GateEvent)
        .filter(GateEvent.session_id == session_id)
        .order_by(GateEvent.created_at)
        .all()
    )
    return {
        "items": events,
        "total": len(events),
    }


def get_session_summary(db: Session) -> dict:
    """Get aggregate counts of examination sessions."""
    total = db.query(func.count(ExaminationSession.id)).scalar() or 0
    not_started = (
        db.query(func.count(ExaminationSession.id))
        .filter(ExaminationSession.status == SessionStatus.NOT_STARTED.value)
        .scalar()
        or 0
    )
    in_progress = (
        db.query(func.count(ExaminationSession.id))
        .filter(ExaminationSession.status == SessionStatus.IN_PROGRESS.value)
        .scalar()
        or 0
    )
    completed = (
        db.query(func.count(ExaminationSession.id))
        .filter(ExaminationSession.status == SessionStatus.COMPLETED.value)
        .scalar()
        or 0
    )
    cancelled = (
        db.query(func.count(ExaminationSession.id))
        .filter(ExaminationSession.status == SessionStatus.CANCELLED.value)
        .scalar()
        or 0
    )
    total_evs = db.query(func.count(EntryVerification.id)).scalar() or 0
    total_att = db.query(func.count(AttendanceRecord.id)).scalar() or 0

    return {
        "total_sessions": total,
        "not_started": not_started,
        "in_progress": in_progress,
        "completed": completed,
        "cancelled": cancelled,
        "total_entry_verifications": total_evs,
        "total_attendance_records": total_att,
    }

"""Invigilator control center API.

Provides the authenticated invigilator with their assigned exam/hall/entry-point/camera,
exam session status, and operational controls (start/end exam, view verifications).

This is the backend for the INVIGILATOR role's primary interface.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Role, get_current_user, require_role
from app.core.database import get_db
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.entry_point import EntryPoint
from app.models.camera import Camera
from app.models.examination_session import ExaminationSession, SessionStatus, GateStatus
from app.models.invigilator_assignment import InvigilatorAssignment
from app.models.entry_verification import EntryVerification
from app.models.attendance import AttendanceRecord
from app.models.security_event import SecurityEvent
from app.services import examination_session as session_svc
from app.services import invigilator_assignment as assign_svc

router = APIRouter(
    prefix="/invigilator",
    tags=["Invigilator Control Center"],
)


class InvigilatorProfileResponse(BaseModel):
    user_id: int
    email: str | None
    full_name: str | None
    role: str
    assignment_id: int
    exam_id: int
    exam_name: str
    exam_date: str
    exam_start_time: str
    exam_end_time: str
    subject_code: str | None
    subject_name: str | None
    hall_id: int
    hall_name: str
    hall_building: str
    hall_room: str
    entry_point_id: int | None
    entry_point_name: str | None
    entry_point_code: str | None
    camera_id: int | None
    camera_name: str | None
    camera_status: str | None
    session_id: int | None
    session_status: str | None
    gate_status: str | None


class InvigilatorDashboardResponse(BaseModel):
    profile: InvigilatorProfileResponse
    session_active: bool
    can_start: bool
    can_end: bool
    verification_count: int
    granted_count: int
    denied_count: int
    escalated_count: int
    attendance_count: int
    security_event_count: int
    recent_verifications: list[dict]


class StartExamRequest(BaseModel):
    performed_by: str | None = None


class EndExamRequest(BaseModel):
    performed_by: str | None = None


def _get_profile(db: Session, user_claims: dict) -> InvigilatorProfileResponse:
    """Build the invigilator profile from their assignment."""
    user_id = int(user_claims["sub"])

    # Get all active assignments for this user
    assignments = assign_svc.get_all_assignments_for_user(db, user_id)
    if not assignments:
        raise HTTPException(
            status_code=404,
            detail="No active invigilator assignment found for this user",
        )

    # Use the first active assignment (future: support multiple)
    assignment = assignments[0]

    # Load related entities
    exam = db.query(Exam).filter(Exam.id == assignment.exam_id).first()
    hall = db.query(ExamHall).filter(ExamHall.id == assignment.exam_hall_id).first()
    ep = db.query(EntryPoint).filter(EntryPoint.id == assignment.entry_point_id).first() if assignment.entry_point_id else None
    camera = db.query(Camera).filter(Camera.id == assignment.camera_id).first() if assignment.camera_id else None

    if not exam or not hall:
        raise HTTPException(status_code=500, detail="Assigned exam or hall not found")

    # Find existing session for this exam+hall
    session = (
        db.query(ExaminationSession)
        .filter(
            ExaminationSession.exam_id == exam.id,
            ExaminationSession.exam_hall_id == hall.id,
        )
        .order_by(ExaminationSession.created_at.desc())
        .first()
    )

    # Load subject
    subject_code = None
    subject_name = None
    if exam.subject:
        subject_code = exam.subject.code
        subject_name = exam.subject.name

    return InvigilatorProfileResponse(
        user_id=user_id,
        email=user_claims.get("email"),
        full_name=user_claims.get("full_name"),
        role=user_claims.get("role", "INVIGILATOR"),
        assignment_id=assignment.id,
        exam_id=exam.id,
        exam_name=exam.exam_name,
        exam_date=str(exam.exam_date),
        exam_start_time=str(exam.start_time),
        exam_end_time=str(exam.end_time),
        subject_code=subject_code,
        subject_name=subject_name,
        hall_id=hall.id,
        hall_name=hall.name or f"{hall.building} {hall.room_number}",
        hall_building=hall.building,
        hall_room=hall.room_number,
        entry_point_id=ep.id if ep else None,
        entry_point_name=ep.name if ep else None,
        entry_point_code=ep.code if ep else None,
        camera_id=camera.id if camera else None,
        camera_name=camera.name if camera else None,
        camera_status=camera.status if camera else None,
        session_id=session.id if session else None,
        session_status=session.status if session else None,
        gate_status=session.gate_status if session else None,
    )


@router.get(
    "/profile",
    response_model=InvigilatorProfileResponse,
    summary="Get invigilator's assigned exam/hall/entry-point/camera",
)
def get_profile(
    user: dict = Depends(require_role([Role.INVIGILATOR])),
    db: Session = Depends(get_db),
):
    return _get_profile(db, user)


@router.get(
    "/dashboard",
    response_model=InvigilatorDashboardResponse,
    summary="Get invigilator dashboard with live stats",
)
def get_dashboard(
    user: dict = Depends(require_role([Role.INVIGILATOR])),
    db: Session = Depends(get_db),
):
    profile = _get_profile(db, user)
    user_id = int(user["sub"])

    # Find session
    session = None
    if profile.session_id:
        session = db.query(ExaminationSession).filter(
            ExaminationSession.id == profile.session_id
        ).first()

    # Check time window
    exam = db.query(Exam).filter(Exam.id == profile.exam_id).first()
    now = datetime.now(timezone.utc)
    can_start = False
    can_end = False

    if session:
        if session.status == SessionStatus.NOT_STARTED.value:
            # Check if we're within the exam window
            exam_date = exam.exam_date
            start_time = exam.start_time
            end_time = exam.end_time

            # Build timezone-aware datetimes
            from datetime import time as dt_time
            exam_start = datetime.combine(exam_date, start_time, tzinfo=timezone.utc)
            exam_end = datetime.combine(exam_date, end_time, tzinfo=timezone.utc)

            # Allow starting up to 15 minutes before scheduled start
            from datetime import timedelta
            early_start = exam_start - timedelta(minutes=15)

            if now >= early_start and now <= exam_end:
                can_start = True
        elif session.status == SessionStatus.IN_PROGRESS.value:
            can_end = True

    # Count verifications for this session
    verification_count = 0
    granted_count = 0
    denied_count = 0
    escalated_count = 0
    recent_verifications = []

    if session:
        from sqlalchemy import func
        evs = (
            db.query(EntryVerification)
            .filter(EntryVerification.session_id == session.id)
            .order_by(EntryVerification.created_at.desc())
            .all()
        )
        verification_count = len(evs)
        granted_count = sum(1 for e in evs if e.status == "GRANTED")
        denied_count = sum(1 for e in evs if e.status == "DENIED")
        escalated_count = sum(1 for e in evs if e.status == "ESCALATED")

        # Recent 10 verifications
        for ev in evs[:10]:
            student = db.query(EntryVerification.student_id).filter(
                EntryVerification.id == ev.id
            ).first()
            recent_verifications.append({
                "id": ev.id,
                "student_id": ev.student_id,
                "status": ev.status,
                "hall_ticket_check": ev.hall_ticket_check,
                "identity_check": ev.identity_check,
                "seat_check": ev.seat_check,
                "created_at": str(ev.created_at),
            })

    # Count attendance
    attendance_count = 0
    if session:
        attendance_count = (
            db.query(func.count(AttendanceRecord.id))
            .filter(AttendanceRecord.session_id == session.id)
            .scalar() or 0
        )

    # Count security events
    security_event_count = 0
    if session:
        security_event_count = (
            db.query(func.count(SecurityEvent.id))
            .filter(SecurityEvent.exam_id == profile.exam_id)
            .filter(SecurityEvent.hall_id == profile.hall_id)
            .scalar() or 0
        )

    return InvigilatorDashboardResponse(
        profile=profile,
        session_active=session is not None and session.status == SessionStatus.IN_PROGRESS.value,
        can_start=can_start,
        can_end=can_end,
        verification_count=verification_count,
        granted_count=granted_count,
        denied_count=denied_count,
        escalated_count=escalated_count,
        attendance_count=attendance_count,
        security_event_count=security_event_count,
        recent_verifications=recent_verifications,
    )


@router.post(
    "/start-exam",
    summary="Start the examination session",
)
def start_exam(
    body: StartExamRequest = StartExamRequest(),
    user: dict = Depends(require_role([Role.INVIGILATOR])),
    db: Session = Depends(get_db),
):
    profile = _get_profile(db, user)

    if not profile.session_id:
        raise HTTPException(
            status_code=404,
            detail="No examination session found. Create a session first.",
        )

    # Time check (server-side)
    exam = db.query(Exam).filter(Exam.id == profile.exam_id).first()
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    exam_start = datetime.combine(exam.exam_date, exam.start_time, tzinfo=timezone.utc)
    exam_end = datetime.combine(exam.exam_date, exam.end_time, tzinfo=timezone.utc)
    early_start = exam_start - timedelta(minutes=15)

    if now > exam_end:
        raise HTTPException(
            status_code=422,
            detail=f"Exam ended at {exam_end.isoformat()}. Cannot start.",
        )
    if now < early_start:
        raise HTTPException(
            status_code=422,
            detail=f"Exam starts at {exam_start.isoformat()}. Too early to start.",
        )

    try:
        session = session_svc.start_session(
            db, profile.session_id,
            performed_by=body.performed_by or user.get("email", "invigilator"),
        )
        return {"status": "started", "session_id": session.id, "gate_status": session.gate_status}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/end-exam",
    summary="End the examination session",
)
def end_exam(
    body: EndExamRequest = EndExamRequest(),
    user: dict = Depends(require_role([Role.INVIGILATOR])),
    db: Session = Depends(get_db),
):
    profile = _get_profile(db, user)

    if not profile.session_id:
        raise HTTPException(status_code=404, detail="No examination session found.")

    try:
        session = session_svc.end_session(
            db, profile.session_id,
            performed_by=body.performed_by or user.get("email", "invigilator"),
        )
        return {"status": "ended", "session_id": session.id}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

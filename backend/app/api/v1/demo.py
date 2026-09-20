"""Demo / Test Data Loader endpoint for ExamGuard presentations.

Creates a deterministic, idempotent demo scenario with:
- 1 Subject, 1 Exam, 1 Student, 1 Registration, 1 Hall,
  1 Seat Assignment, 1 Examination Session, 1 Entry Point,
  1 Identity Verification Attempt, 1 Invigilator Assignment

All records are tagged with deterministic codes so they can be
found/reused on repeated calls (idempotent).

This feature requires ADMIN or OPERATOR authentication.
It does NOT bypass face verification or any security checks.
"""

from datetime import date, time, timedelta, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Role, require_role, get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models import (
    Subject,
    Exam,
    Student,
    ExamRegistration,
    ExamHall,
    SeatAssignment,
    ExaminationSession,
    EntryPoint,
    IdentityVerificationAttempt,
    InvigilatorAssignment,
    User,
)

router = APIRouter(prefix="/demo", tags=["Demo Data"])
settings = get_settings()

# ── Deterministic demo identifiers ────────────────────────────────
DEMO_SUBJECT_CODE = "DEMO-CA"
DEMO_EXAM_DEPT = "Demo"
DEMO_EXAM_SEMESTER = 1
DEMO_STUDENT_USN = "DEMO001"
DEMO_HALL_BUILDING = "Demo Building"
DEMO_HALL_ROOM = "A1"
DEMO_ENTRY_CODE = "DEMO_MAIN"


class DemoLoadResponse(BaseModel):
    status: str
    message: str
    demo_exam_id: int
    demo_hall_id: int
    demo_student_id: int
    demo_session_id: int
    demo_attempt_id: int
    demo_invigilator_assignment_id: int | None = None


class DemoStatusResponse(BaseModel):
    loaded: bool
    demo_exam_id: int | None = None
    demo_hall_id: int | None = None
    demo_student_id: int | None = None
    demo_session_id: int | None = None
    demo_attempt_id: int | None = None


# ── Helpers ───────────────────────────────────────────────────────

def _find_or_create(db: Session, model, unique_filters: dict, defaults: dict):
    """Find existing record or create new one. Returns (obj, is_new)."""
    stmt = select(model).filter_by(**unique_filters)
    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        return existing, False
    obj = model(**unique_filters, **defaults)
    db.add(obj)
    db.flush()
    return obj, True


def _get_demo_user(db: Session, claims: dict) -> User:
    """Get the current user as a User model instance."""
    firebase_uid = claims.get("sub")
    if firebase_uid:
        user = db.execute(
            select(User).filter_by(firebase_uid=firebase_uid)
        ).scalar_one_or_none()
        if user:
            return user
    email = claims.get("email", "")
    user = db.execute(
        select(User).filter_by(email=email)
    ).scalar_one_or_none()
    return user


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/status", response_model=DemoStatusResponse)
def demo_status(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    """Check whether demo data has been loaded."""
    subject = db.execute(
        select(Subject).filter_by(code=DEMO_SUBJECT_CODE)
    ).scalar_one_or_none()

    if not subject:
        return DemoStatusResponse(loaded=False)

    exam = db.execute(
        select(Exam).filter_by(subject_id=subject.id)
    ).scalar_one_or_none()
    student = db.execute(
        select(Student).filter_by(usn=DEMO_STUDENT_USN)
    ).scalar_one_or_none()

    session = None
    attempt = None
    if exam:
        session = db.execute(
            select(ExaminationSession).filter_by(exam_id=exam.id)
        ).scalar_one_or_none()
    if student and exam:
        reg = db.execute(
            select(ExamRegistration).filter_by(
                student_id=student.id, exam_id=exam.id
            )
        ).scalar_one_or_none()
        if reg:
            attempt = db.execute(
                select(IdentityVerificationAttempt).filter_by(
                    exam_registration_id=reg.id
                )
            ).scalar_one_or_none()

    return DemoStatusResponse(
        loaded=True,
        demo_exam_id=exam.id if exam else None,
        demo_hall_id=session.exam_hall_id if session else None,
        demo_student_id=student.id if student else None,
        demo_session_id=session.id if session else None,
        demo_attempt_id=attempt.id if attempt else None,
    )


@router.get("/reference-image")
def demo_reference_image(
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    """Serve the deterministic demo candidate reference face image.

    Returns a synthetic face PNG that can be used as the reference
    (enrollment) image for the demo candidate's identity verification.
    The image is deterministic — same bytes every call.
    """
    from app.services.demo_face_image import generate_demo_face_png

    png_bytes = generate_demo_face_png()
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Demo-Image": "synthetic-face",
        },
    )


@router.post("/load", response_model=DemoLoadResponse)
def demo_load(
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    """Load (or reload) the deterministic demo scenario.

    Idempotent: calling multiple times produces the same records.
    Creates subject → exam → student → registration → hall → seat
    assignment → examination session → identity verification attempt.

    The identity verification attempt is created in CREATED status
    with method=FACE, ready for the real face verification pipeline.
    """
    # ── Subject ──
    subject, _ = _find_or_create(
        db, Subject,
        unique_filters={"code": DEMO_SUBJECT_CODE, "department": DEMO_EXAM_DEPT},
        defaults={
            "name": "Computer Applications — Demonstration",
            "semester": DEMO_EXAM_SEMESTER,
            "credits": 3,
        },
    )

    # ── Exam (tomorrow so it never expires) ──
    tomorrow = date.today() + timedelta(days=1)
    exam, _ = _find_or_create(
        db, Exam,
        unique_filters={
            "subject_id": subject.id,
            "exam_date": tomorrow,
            "start_time": time(9, 0),
        },
        defaults={
            "exam_name": "ExamGuard Demo Examination",
            "end_time": time(11, 0),
            "semester": DEMO_EXAM_SEMESTER,
            "department": DEMO_EXAM_DEPT,
        },
    )

    # ── Student ──
    student, _ = _find_or_create(
        db, Student,
        unique_filters={"usn": DEMO_STUDENT_USN},
        defaults={"name": "Demo Candidate"},
    )

    # ── Exam Registration ──
    registration, _ = _find_or_create(
        db, ExamRegistration,
        unique_filters={"student_id": student.id, "exam_id": exam.id},
        defaults={"status": "REGISTERED"},
    )

    # ── Exam Hall ──
    hall, _ = _find_or_create(
        db, ExamHall,
        unique_filters={
            "building": DEMO_HALL_BUILDING,
            "room_number": DEMO_HALL_ROOM,
        },
        defaults={
            "name": "Demo Hall A",
            "capacity": 30,
            "rows": 5,
            "columns": 6,
        },
    )

    # ── Seat Assignment ──
    seat, _ = _find_or_create(
        db, SeatAssignment,
        unique_filters={
            "exam_registration_id": registration.id,
            "exam_hall_id": hall.id,
        },
        defaults={
            "seat_number": "1",
            "row_number": 1,
            "column_number": 1,
            "exam_id": exam.id,
            "student_id": student.id,
        },
    )

    # ── Entry Point ──
    entry_point, _ = _find_or_create(
        db, EntryPoint,
        unique_filters={"code": DEMO_ENTRY_CODE},
        defaults={
            "name": "Demo Main Entry",
            "description": "Primary entry point for demo examinations",
            "location_detail": "Ground floor, Demo Building",
            "exam_hall_id": hall.id,
        },
    )

    # ── Examination Session ──
    session, _ = _find_or_create(
        db, ExaminationSession,
        unique_filters={"exam_id": exam.id, "exam_hall_id": hall.id},
        defaults={
            "status": "NOT_STARTED",
            "gate_status": "GATES_CLOSED",
            "expected_capacity": 30,
            "notes": "Demo session for live presentations",
            "created_by": "demo-loader",
        },
    )

    # ── Identity Verification Attempt ──
    attempt, _ = _find_or_create(
        db, IdentityVerificationAttempt,
        unique_filters={"exam_registration_id": registration.id},
        defaults={
            "student_id": student.id,
            "hall_ticket_id": None,
            "verification_method": "FACE",
            "status": "CREATED",
            "decision": "PENDING",
        },
    )

    # ── Invigilator Assignment (for the current user) ──
    invigilator_assignment_id = None
    user = _get_demo_user(db, claims)
    if user:
        ia, is_new = _find_or_create(
            db, InvigilatorAssignment,
            unique_filters={
                "user_id": user.id,
                "exam_id": exam.id,
                "exam_hall_id": hall.id,
            },
            defaults={
                "entry_point_id": entry_point.id,
                "notes": "Auto-assigned by demo data loader",
            },
        )
        invigilator_assignment_id = ia.id

    db.commit()

    return DemoLoadResponse(
        status="ready",
        message="Demo data loaded successfully",
        demo_exam_id=exam.id,
        demo_hall_id=hall.id,
        demo_student_id=student.id,
        demo_session_id=session.id,
        demo_attempt_id=attempt.id,
        demo_invigilator_assignment_id=invigilator_assignment_id,
    )


@router.post("/reset")
def demo_reset(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    """Reset demo data by soft-deleting demo records.

    Only deletes records with deterministic demo identifiers.
    Never touches real examination data.
    """
    deleted = 0

    # Find demo subject
    subject = db.execute(
        select(Subject).filter_by(code=DEMO_SUBJECT_CODE)
    ).scalar_one_or_none()
    if not subject:
        return {"status": "nothing_to_reset", "message": "No demo data found"}

    # Find all demo exams
    exams = db.execute(
        select(Exam).filter_by(subject_id=subject.id)
    ).scalars().all()

    for exam in exams:
        # Delete identity verification attempts for demo registrations
        regs = db.execute(
            select(ExamRegistration).filter_by(exam_id=exam.id)
        ).scalars().all()
        for reg in regs:
            attempts = db.execute(
                select(IdentityVerificationAttempt).filter_by(
                    exam_registration_id=reg.id
                )
            ).scalars().all()
            for att in attempts:
                db.delete(att)
                deleted += 1

            # Delete seat assignments
            seats = db.execute(
                select(SeatAssignment).filter_by(exam_registration_id=reg.id)
            ).scalars().all()
            for s in seats:
                db.delete(s)
                deleted += 1

            db.delete(reg)
            deleted += 1

        # Delete examination sessions
        sessions = db.execute(
            select(ExaminationSession).filter_by(exam_id=exam.id)
        ).scalars().all()
        for sess in sessions:
            db.delete(sess)
            deleted += 1

        db.delete(exam)
        deleted += 1

    # Delete demo student
    student = db.execute(
        select(Student).filter_by(usn=DEMO_STUDENT_USN)
    ).scalar_one_or_none()
    if student:
        db.delete(student)
        deleted += 1

    # Delete demo hall
    hall = db.execute(
        select(ExamHall).filter_by(
            building=DEMO_HALL_BUILDING,
            room_number=DEMO_HALL_ROOM,
        )
    ).scalar_one_or_none()
    if hall:
        db.delete(hall)
        deleted += 1

    # Delete demo entry point
    ep = db.execute(
        select(EntryPoint).filter_by(code=DEMO_ENTRY_CODE)
    ).scalar_one_or_none()
    if ep:
        db.delete(ep)
        deleted += 1

    # Soft-delete demo subject
    subject.is_active = False
    deleted += 1

    db.commit()

    return {
        "status": "reset",
        "message": f"Demo data reset complete. {deleted} records removed.",
        "records_deleted": deleted,
    }

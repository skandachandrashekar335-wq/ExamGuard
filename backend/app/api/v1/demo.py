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
from pydantic import BaseModel, Field
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
DEMO_STUDENT_USNS = ["DEMO001", "DEMO002", "DEMO003"]
DEMO_STUDENT_NAMES = ["Demo Candidate 1", "Demo Candidate 2", "Demo Candidate 3"]
DEMO_HALL_BUILDING = "Demo Building"
DEMO_HALL_ROOM = "A1"
DEMO_ENTRY_CODE = "DEMO_MAIN"


class DemoLoadResponse(BaseModel):
    status: str
    message: str
    demo_exam_id: int
    demo_hall_id: int
    demo_student_ids: list[int]
    demo_student_usns: list[str]
    demo_session_id: int
    demo_attempt_ids: list[int]
    demo_invigilator_assignment_id: int | None = None


class DemoStatusResponse(BaseModel):
    loaded: bool
    demo_exam_id: int | None = None
    demo_hall_id: int | None = None
    demo_student_ids: list[int] | None = None
    demo_student_usns: list[str] | None = None
    demo_session_id: int | None = None
    demo_attempt_ids: list[int] | None = None


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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.REVIEWER, Role.INVIGILATOR])),
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
    students = db.execute(
        select(Student).filter(Student.usn.in_(DEMO_STUDENT_USNS))
    ).scalars().all()

    session = None
    attempts = None
    if exam:
        session = db.execute(
            select(ExaminationSession).filter_by(exam_id=exam.id)
        ).scalar_one_or_none()
    if students:
        attempts = db.execute(
            select(IdentityVerificationAttempt)
            .filter(IdentityVerificationAttempt.exam_registration_id.in_(
                db.select(ExamRegistration.exam_registration_id)
                .where(ExamRegistration.student_id.in_([s.id for s in students]))
            ))
        ).scalars().all()

    return DemoStatusResponse(
        loaded=True,
        demo_exam_id=exam.id if exam else None,
        demo_hall_id=session.exam_hall_id if session else None,
        demo_student_ids=[s.id for s in students] if students else None,
        demo_student_usns=[s.usn for s in students] if students else None,
        demo_session_id=session.id if session else None,
        demo_attempt_ids=[a.id for a in attempts] if attempts else None,
    )


@router.get("/reference-image")
def demo_reference_image(
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.REVIEWER, Role.INVIGILATOR])),
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
    claims: dict = Depends(get_current_user),
):
    """Load (or reload) the deterministic demo scenario.

    Idempotent: calling multiple times produces the same records.
    Creates subject → exam → student → registration → hall → seat
    assignment → examination session → identity verification attempt.

    The identity verification attempt is created in CREATED status
    with method=FACE, ready for the real face verification pipeline.

    Any authenticated ExamGuard user may load the demo scenario.
    The endpoint is restricted to creating only the fixed demo
    scenario — no arbitrary exams, students, or records are
    permitted, and no frontend-controlled payload is accepted.
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

    # ── Students (3 candidates) ──
    students = []
    for i, (usn, name) in enumerate(zip(DEMO_STUDENT_USNS, DEMO_STUDENT_NAMES), 1):
        student, _ = _find_or_create(
            db, Student,
            unique_filters={"usn": usn},
            defaults={"name": name},
        )
        students.append(student)

    # ── Exam Registrations (one per student) ──
    registrations = []
    for student in students:
        registration, _ = _find_or_create(
            db, ExamRegistration,
            unique_filters={"student_id": student.id, "exam_id": exam.id},
            defaults={"status": "REGISTERED"},
        )
        registrations.append(registration)

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

    # ── Seat Assignments (one per student) ──
    seat_assignments = []
    for i, (student, registration) in enumerate(zip(students, registrations), 1):
        seat, _ = _find_or_create(
            db, SeatAssignment,
            unique_filters={
                "exam_registration_id": registration.id,
                "exam_hall_id": hall.id,
            },
            defaults={
                "seat_number": str(i),
                "row_number": 1,
                "column_number": i,
                "exam_id": exam.id,
                "student_id": student.id,
            },
        )
        seat_assignments.append(seat)

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

    # ── Identity Verification Attempts (one per student) ──
    attempts = []
    for student, registration in zip(students, registrations):
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
        attempts.append(attempt)

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
        demo_student_ids=[s.id for s in students],
        demo_student_usns=[s.usn for s in students],
        demo_session_id=session.id,
        demo_attempt_ids=[a.id for a in attempts],
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

    # Delete demo students
    for usn in DEMO_STUDENT_USNS:
        student = db.execute(
            select(Student).filter_by(usn=usn)
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


# ── Demo-specific presentation workflow endpoints ────────────────
# These endpoints allow any authenticated user to perform demo-specific
# operations (upload reference face, assign invigilator, start session)
# but ONLY on deterministic demo records. They do NOT weaken normal RBAC.

def _is_demo_attempt(db: Session, attempt_id: int) -> bool:
    """Check if an attempt belongs to a demo student."""
    attempt = db.execute(
        select(IdentityVerificationAttempt).filter_by(id=attempt_id)
    ).scalar_one_or_none()
    if not attempt:
        return False
    student = db.execute(
        select(Student).filter(Student.usn.in_(DEMO_STUDENT_USNS))
        .filter(Student.id == attempt.student_id)
    ).scalar_one_or_none()
    return student is not None


def _get_demo_session(db: Session) -> "ExaminationSession | None":
    """Get the deterministic demo examination session."""
    subject = db.execute(
        select(Subject).filter_by(code=DEMO_SUBJECT_CODE)
    ).scalar_one_or_none()
    if not subject:
        return None
    exam = db.execute(
        select(Exam).filter_by(subject_id=subject.id)
    ).scalar_one_or_none()
    if not exam:
        return None
    return db.execute(
        select(ExaminationSession).filter_by(exam_id=exam.id)
    ).scalar_one_or_none()


class DemoUploadReferenceRequest(BaseModel):
    attempt_id: int = Field(..., gt=0)
    reference_image: str = Field(..., min_length=1, description="Base64-encoded face image")
    image_format: str = Field(default="image/jpeg")


class DemoAssignInvigilatorRequest(BaseModel):
    email: str = Field(..., min_length=1, description="Invigilator email address")


class DemoStartSessionRequest(BaseModel):
    performed_by: str | None = None


@router.post("/upload-reference-face")
def demo_upload_reference_face(
    body: DemoUploadReferenceRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Upload a reference face for a demo student.

    Any authenticated user may call this endpoint, but ONLY for attempts
    belonging to deterministic demo students (DEMO001-003). Real
    production reference-face upload still requires ADMIN/OPERATOR via
    the normal /identity-verifications/{id}/reference-face endpoint.
    """
    import base64

    if not _is_demo_attempt(db, body.attempt_id):
        raise HTTPException(
            status_code=422,
            detail="Attempt is not a demo student reference. Use the standard endpoint.",
        )

    attempt = db.execute(
        select(IdentityVerificationAttempt).filter_by(id=body.attempt_id)
    ).scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    try:
        ref_bytes = base64.b64decode(body.reference_image, validate=True)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid base64 encoding")

    if len(ref_bytes) == 0:
        raise HTTPException(status_code=422, detail="Image is empty")

    from app.core.config import get_settings
    settings = get_settings()
    max_size = settings.FACE_VERIFICATION_MAX_IMAGE_SIZE_MB * 1024 * 1024
    if len(ref_bytes) > max_size:
        raise HTTPException(
            status_code=422,
            detail=f"Image exceeds {settings.FACE_VERIFICATION_MAX_IMAGE_SIZE_MB}MB limit",
        )

    from app.storage.cloudinary import CloudinaryStorage
    storage = CloudinaryStorage()
    ext = ".png" if body.image_format == "image/png" else ".jpg"
    key = f"face-references/attempt-{body.attempt_id}{ext}"

    try:
        url = storage.save(key, ref_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {e}")

    attempt.reference_face_url = url
    db.commit()
    db.refresh(attempt)

    return {
        "status": "saved",
        "attempt_id": body.attempt_id,
        "reference_face_url": url,
    }


@router.post("/assign-invigilator")
def demo_assign_invigilator(
    body: DemoAssignInvigilatorRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Assign an invigilator to the demo session by email.

    Any authenticated user may call this, but it ONLY modifies the
    deterministic demo session's invigilator assignment.
    """
    session = _get_demo_session(db)
    if not session:
        raise HTTPException(status_code=404, detail="Demo session not loaded. Load demo data first.")

    user = db.execute(
        select(User).filter(User.email.ilike(body.email))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"No user found with email {body.email}. The invigilator must sign in at least once.",
        )

    exam = db.execute(select(Exam).filter_by(id=session.exam_id)).scalar_one_or_none()
    entry_point = db.execute(
        select(EntryPoint).filter_by(code=DEMO_ENTRY_CODE)
    ).scalar_one_or_none()

    ia, _ = _find_or_create(
        db, InvigilatorAssignment,
        unique_filters={
            "user_id": user.id,
            "exam_id": session.exam_id,
            "exam_hall_id": session.exam_hall_id,
        },
        defaults={
            "entry_point_id": entry_point.id if entry_point else None,
            "notes": "Assigned via demo presentation workflow",
        },
    )
    db.commit()

    return {
        "status": "assigned",
        "assignment_id": ia.id,
        "user_id": user.id,
        "email": user.email,
        "exam_id": session.exam_id,
        "exam_hall_id": session.exam_hall_id,
    }


@router.post("/start-session")
def demo_start_session(
    body: DemoStartSessionRequest = DemoStartSessionRequest(),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Start the demo examination session.

    Transitions the deterministic demo session from NOT_STARTED → IN_PROGRESS.
    Any authenticated user may call this, but ONLY the demo session is affected.
    """
    from app.services import examination_session as session_svc

    session = _get_demo_session(db)
    if not session:
        raise HTTPException(status_code=404, detail="Demo session not loaded. Load demo data first.")

    try:
        updated = session_svc.start_session(
            db, session.id,
            performed_by=body.performed_by or _user.get("email", "demo-presenter"),
        )
        return {
            "status": "started",
            "session_id": updated.id,
            "session_status": updated.status,
            "gate_status": updated.gate_status,
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/session-status")
def demo_session_status(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Get the current demo session status."""
    session = _get_demo_session(db)
    if not session:
        return {"loaded": False}

    exam = db.execute(select(Exam).filter_by(id=session.exam_id)).scalar_one_or_none()
    hall = db.execute(
        select(ExamHall).filter_by(id=session.exam_hall_id)
    ).scalar_one_or_none()

    return {
        "loaded": True,
        "session_id": session.id,
        "session_status": session.status,
        "gate_status": session.gate_status,
        "exam_name": exam.exam_name if exam else None,
        "exam_date": str(exam.exam_date) if exam else None,
        "hall_name": hall.name if hall else None,
        "started_at": str(session.started_at) if session.started_at else None,
    }

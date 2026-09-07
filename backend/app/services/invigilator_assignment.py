"""Invigilator assignment service.

Manages CRUD for invigilator-to-exam/hall/entry-point/camera assignments.
Also provides lookup helpers used by the auth and session services.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.invigilator_assignment import InvigilatorAssignment
from app.models.user import User

logger = logging.getLogger(__name__)


def create_assignment(
    db: Session,
    *,
    user_id: int,
    exam_id: int,
    exam_hall_id: int,
    entry_point_id: int | None = None,
    camera_id: int | None = None,
    notes: str | None = None,
) -> InvigilatorAssignment:
    """Create an invigilator assignment."""
    # Validate user exists and has INVIGILATOR role
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise LookupError(f"User {user_id} not found")
    if user.role != "INVIGILATOR":
        raise ValueError(f"User {user_id} has role '{user.role}', expected 'INVIGILATOR'")

    # Check for duplicate active assignment
    existing = (
        db.query(InvigilatorAssignment)
        .filter(
            InvigilatorAssignment.user_id == user_id,
            InvigilatorAssignment.exam_id == exam_id,
            InvigilatorAssignment.exam_hall_id == exam_hall_id,
            InvigilatorAssignment.is_active == True,
        )
        .first()
    )
    if existing:
        raise ValueError(
            f"Active assignment already exists for user {user_id} "
            f"exam {exam_id} hall {exam_hall_id} (assignment {existing.id})"
        )

    assignment = InvigilatorAssignment(
        user_id=user_id,
        exam_id=exam_id,
        exam_hall_id=exam_hall_id,
        entry_point_id=entry_point_id,
        camera_id=camera_id,
        notes=notes,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    logger.info(
        "INVIGILATOR_ASSIGNMENT_AUDIT: id=%d user_id=%d exam_id=%d hall_id=%d",
        assignment.id, user_id, exam_id, exam_hall_id,
    )
    return assignment


def get_assignment(db: Session, assignment_id: int) -> InvigilatorAssignment | None:
    return (
        db.query(InvigilatorAssignment)
        .filter(InvigilatorAssignment.id == assignment_id)
        .first()
    )


def list_assignments(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    user_id: int | None = None,
    exam_id: int | None = None,
    exam_hall_id: int | None = None,
    include_inactive: bool = False,
) -> dict:
    query = db.query(InvigilatorAssignment)

    if user_id is not None:
        query = query.filter(InvigilatorAssignment.user_id == user_id)
    if exam_id is not None:
        query = query.filter(InvigilatorAssignment.exam_id == exam_id)
    if exam_hall_id is not None:
        query = query.filter(InvigilatorAssignment.exam_hall_id == exam_hall_id)
    if not include_inactive:
        query = query.filter(InvigilatorAssignment.is_active == True)

    total = query.count()
    items = (
        query.order_by(InvigilatorAssignment.created_at.desc())
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


def deactivate_assignment(db: Session, assignment_id: int) -> InvigilatorAssignment:
    assignment = get_assignment(db, assignment_id)
    if not assignment:
        raise LookupError(f"Assignment {assignment_id} not found")
    if not assignment.is_active:
        raise ValueError(f"Assignment {assignment_id} is already inactive")
    assignment.is_active = False
    db.commit()
    db.refresh(assignment)
    logger.info("INVIGILATOR_ASSIGNMENT_AUDIT: id=%d event=deactivated", assignment_id)
    return assignment


def get_assignment_for_user_exam(
    db: Session,
    user_id: int,
    exam_id: int,
) -> InvigilatorAssignment | None:
    """Get the active invigilator assignment for a specific user+exam."""
    return (
        db.query(InvigilatorAssignment)
        .filter(
            InvigilatorAssignment.user_id == user_id,
            InvigilatorAssignment.exam_id == exam_id,
            InvigilatorAssignment.is_active == True,
        )
        .first()
    )


def get_all_assignments_for_user(
    db: Session,
    user_id: int,
) -> list[InvigilatorAssignment]:
    """Get all active invigilator assignments for a user."""
    return (
        db.query(InvigilatorAssignment)
        .filter(
            InvigilatorAssignment.user_id == user_id,
            InvigilatorAssignment.is_active == True,
        )
        .all()
    )


def get_assignments_for_exam(
    db: Session,
    exam_id: int,
) -> list[InvigilatorAssignment]:
    """Get all active invigilator assignments for an exam."""
    return (
        db.query(InvigilatorAssignment)
        .filter(
            InvigilatorAssignment.exam_id == exam_id,
            InvigilatorAssignment.is_active == True,
        )
        .all()
    )

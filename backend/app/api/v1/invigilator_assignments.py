"""Invigilator assignment REST API.

Endpoints for managing invigilator-to-exam/hall/entry-point/camera assignments.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Role, require_role
from app.core.database import get_db
from app.models.user import User
from app.services import invigilator_assignment as svc

router = APIRouter(
    prefix="/invigilator-assignments",
    tags=["Invigilator Assignments"],
)


class InvigilatorAssignmentCreate(BaseModel):
    user_id: int = Field(..., gt=0, description="User ID (must have INVIGILATOR role)")
    exam_id: int = Field(..., gt=0)
    exam_hall_id: int = Field(..., gt=0)
    entry_point_id: int | None = Field(default=None, gt=0)
    camera_id: int | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=2000)


class InvigilatorAssignmentResponse(BaseModel):
    id: int
    user_id: int
    exam_id: int
    exam_hall_id: int
    entry_point_id: int | None
    camera_id: int | None
    is_active: bool
    notes: str | None
    created_at: str
    updated_at: str

    # Enriched fields
    user_email: str | None = None
    user_name: str | None = None
    exam_name: str | None = None
    hall_name: str | None = None


class InvigilatorAssignmentListResponse(BaseModel):
    items: list[InvigilatorAssignmentResponse]
    total: int
    page: int
    page_size: int


def _enrich(a) -> InvigilatorAssignmentResponse:
    resp = InvigilatorAssignmentResponse(
        id=a.id,
        user_id=a.user_id,
        exam_id=a.exam_id,
        exam_hall_id=a.exam_hall_id,
        entry_point_id=a.entry_point_id,
        camera_id=a.camera_id,
        is_active=a.is_active,
        notes=a.notes,
        created_at=str(a.created_at),
        updated_at=str(a.updated_at),
    )
    if a.user:
        resp.user_email = a.user.email
        resp.user_name = a.user.full_name
    if a.exam:
        resp.exam_name = a.exam.exam_name
    if a.exam_hall:
        resp.hall_name = a.exam_hall.name or f"{a.exam_hall.building} {a.exam_hall.room_number}"
    return resp


@router.post(
    "",
    response_model=InvigilatorAssignmentResponse,
    status_code=201,
    summary="Create an invigilator assignment",
)
def create_assignment(
    body: InvigilatorAssignmentCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    try:
        a = svc.create_assignment(
            db,
            user_id=body.user_id,
            exam_id=body.exam_id,
            exam_hall_id=body.exam_hall_id,
            entry_point_id=body.entry_point_id,
            camera_id=body.camera_id,
            notes=body.notes,
        )
        return _enrich(a)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get(
    "",
    response_model=InvigilatorAssignmentListResponse,
    summary="List invigilator assignments",
)
def list_assignments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int | None = Query(None),
    exam_id: int | None = Query(None),
    exam_hall_id: int | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    _: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    result = svc.list_assignments(
        db,
        page=page,
        page_size=page_size,
        user_id=user_id,
        exam_id=exam_id,
        exam_hall_id=exam_hall_id,
        include_inactive=include_inactive,
    )
    return InvigilatorAssignmentListResponse(
        items=[_enrich(a) for a in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get(
    "/{assignment_id}",
    response_model=InvigilatorAssignmentResponse,
    summary="Get an invigilator assignment",
)
def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    a = svc.get_assignment(db, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return _enrich(a)


@router.delete(
    "/{assignment_id}",
    response_model=InvigilatorAssignmentResponse,
    summary="Deactivate an invigilator assignment",
)
def deactivate_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    try:
        a = svc.deactivate_assignment(db, assignment_id)
        return _enrich(a)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get(
    "/by-user/{user_id}",
    response_model=list[InvigilatorAssignmentResponse],
    summary="Get all active assignments for a user",
)
def get_assignments_for_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    assignments = svc.get_all_assignments_for_user(db, user_id)
    return [_enrich(a) for a in assignments]


@router.get(
    "/by-exam/{exam_id}",
    response_model=list[InvigilatorAssignmentResponse],
    summary="Get all active assignments for an exam",
)
def get_assignments_for_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    assignments = svc.get_assignments_for_exam(db, exam_id)
    return [_enrich(a) for a in assignments]

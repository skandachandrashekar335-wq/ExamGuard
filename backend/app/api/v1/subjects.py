from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.subject import (
    SubjectCreate,
    SubjectListResponse,
    SubjectResponse,
    SubjectUpdate,
)
from app.services import subject as subject_service

router = APIRouter(prefix="/subjects", tags=["Subjects"])


@router.post(
    "",
    response_model=SubjectResponse,
    status_code=201,
    summary="Create a new subject",
)
def create_subject(data: SubjectCreate, db: Session = Depends(get_db)):
    try:
        return subject_service.create_subject(db, data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=SubjectListResponse, summary="List subjects")
def list_subjects(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by code or name"),
    department: str | None = Query(None, description="Filter by department"),
    semester: int | None = Query(None, ge=1, le=8, description="Filter by semester"),
    include_inactive: bool = Query(False, description="Include deactivated subjects"),
    db: Session = Depends(get_db),
):
    subjects, total = subject_service.list_subjects(
        db,
        page=page,
        page_size=page_size,
        search=search,
        department=department,
        semester=semester,
        include_inactive=include_inactive,
    )
    return SubjectListResponse(
        items=[SubjectResponse.model_validate(s) for s in subjects],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{subject_id}", response_model=SubjectResponse, summary="Get a subject")
def get_subject(subject_id: int, db: Session = Depends(get_db)):
    subject = subject_service.get_subject(db, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


@router.patch("/{subject_id}", response_model=SubjectResponse, summary="Update a subject")
def update_subject(subject_id: int, data: SubjectUpdate, db: Session = Depends(get_db)):
    try:
        return subject_service.update_subject(db, subject_id, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete(
    "/{subject_id}",
    response_model=SubjectResponse,
    summary="Deactivate a subject (soft delete)",
)
def deactivate_subject(subject_id: int, db: Session = Depends(get_db)):
    try:
        return subject_service.deactivate_subject(db, subject_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

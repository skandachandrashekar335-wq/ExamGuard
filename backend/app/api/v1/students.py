from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.student import (
    StudentCreate,
    StudentListResponse,
    StudentResponse,
    StudentUpdate,
)
from app.services import student as student_service

router = APIRouter(prefix="/students", tags=["Students"])


@router.post(
    "",
    response_model=StudentResponse,
    status_code=201,
    summary="Create a new student",
)
def create_student(data: StudentCreate, db: Session = Depends(get_db)):
    try:
        return student_service.create_student(db, data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=StudentListResponse, summary="List students")
def list_students(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by USN or name"),
    include_inactive: bool = Query(False, description="Include deactivated students"),
    db: Session = Depends(get_db),
):
    students, total = student_service.list_students(
        db, page=page, page_size=page_size, search=search, include_inactive=include_inactive
    )
    return StudentListResponse(
        items=[StudentResponse.model_validate(s) for s in students],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{student_id}", response_model=StudentResponse, summary="Get a student")
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = student_service.get_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.patch("/{student_id}", response_model=StudentResponse, summary="Update a student")
def update_student(student_id: int, data: StudentUpdate, db: Session = Depends(get_db)):
    try:
        return student_service.update_student(db, student_id, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete(
    "/{student_id}",
    response_model=StudentResponse,
    summary="Deactivate a student (soft delete)",
)
def deactivate_student(student_id: int, db: Session = Depends(get_db)):
    try:
        return student_service.deactivate_student(db, student_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

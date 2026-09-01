from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.exam_hall import (
    ExamHallCreate,
    ExamHallListResponse,
    ExamHallResponse,
    ExamHallUpdate,
)
from app.services import exam_hall as hall_service

router = APIRouter(prefix="/exam-halls", tags=["Exam Halls"])


@router.post(
    "",
    response_model=ExamHallResponse,
    status_code=201,
    summary="Create a new exam hall",
)
def create_hall(data: ExamHallCreate, db: Session = Depends(get_db)):
    try:
        return hall_service.create_hall(db, data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=ExamHallListResponse, summary="List exam halls")
def list_halls(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by building, room number, or name"),
    include_inactive: bool = Query(False, description="Include deactivated halls"),
    db: Session = Depends(get_db),
):
    halls, total = hall_service.list_halls(
        db,
        page=page,
        page_size=page_size,
        search=search,
        include_inactive=include_inactive,
    )
    return ExamHallListResponse(
        items=[ExamHallResponse.model_validate(h) for h in halls],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{hall_id}", response_model=ExamHallResponse, summary="Get an exam hall")
def get_hall(hall_id: int, db: Session = Depends(get_db)):
    hall = hall_service.get_hall(db, hall_id)
    if not hall:
        raise HTTPException(status_code=404, detail="Exam hall not found")
    return hall


@router.patch("/{hall_id}", response_model=ExamHallResponse, summary="Update an exam hall")
def update_hall(hall_id: int, data: ExamHallUpdate, db: Session = Depends(get_db)):
    try:
        return hall_service.update_hall(db, hall_id, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete(
    "/{hall_id}",
    response_model=ExamHallResponse,
    summary="Deactivate an exam hall (soft delete)",
)
def deactivate_hall(hall_id: int, db: Session = Depends(get_db)):
    try:
        return hall_service.deactivate_hall(db, hall_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

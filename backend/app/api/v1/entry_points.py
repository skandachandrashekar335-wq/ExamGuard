from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.entry_point import (
    EntryPointCreate,
    EntryPointListResponse,
    EntryPointResponse,
    EntryPointUpdate,
)
from app.services import entry_point as entry_point_service

router = APIRouter(prefix="/entry-points", tags=["Entry Points"])


@router.post(
    "",
    response_model=EntryPointResponse,
    status_code=201,
    summary="Create a new entry point",
)
def create_entry_point(data: EntryPointCreate, db: Session = Depends(get_db)):
    try:
        return entry_point_service.create_entry_point(db, data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=EntryPointListResponse, summary="List entry points")
def list_entry_points(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by name, code, description, or location"),
    exam_hall_id: int | None = Query(None, description="Filter by exam hall"),
    include_inactive: bool = Query(False, description="Include deactivated entry points"),
    db: Session = Depends(get_db),
):
    entry_points, total = entry_point_service.list_entry_points(
        db,
        page=page,
        page_size=page_size,
        search=search,
        exam_hall_id=exam_hall_id,
        include_inactive=include_inactive,
    )
    return EntryPointListResponse(
        items=[EntryPointResponse.model_validate(ep) for ep in entry_points],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{entry_point_id}", response_model=EntryPointResponse, summary="Get an entry point")
def get_entry_point(entry_point_id: int, db: Session = Depends(get_db)):
    entry_point = entry_point_service.get_entry_point(db, entry_point_id)
    if not entry_point:
        raise HTTPException(status_code=404, detail="Entry point not found")
    return entry_point


@router.patch("/{entry_point_id}", response_model=EntryPointResponse, summary="Update an entry point")
def update_entry_point(entry_point_id: int, data: EntryPointUpdate, db: Session = Depends(get_db)):
    try:
        return entry_point_service.update_entry_point(db, entry_point_id, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete(
    "/{entry_point_id}",
    response_model=EntryPointResponse,
    summary="Deactivate an entry point (soft delete)",
)
def deactivate_entry_point(entry_point_id: int, db: Session = Depends(get_db)):
    try:
        return entry_point_service.deactivate_entry_point(db, entry_point_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

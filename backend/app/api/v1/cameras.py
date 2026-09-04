from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.camera import (
    CameraCreate,
    CameraListResponse,
    CameraResponse,
    CameraUpdate,
)
from app.services import camera as camera_service

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.post(
    "",
    response_model=CameraResponse,
    status_code=201,
    summary="Create a new camera",
)
def create_camera(data: CameraCreate, db: Session = Depends(get_db)):
    try:
        return camera_service.create_camera(db, data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=CameraListResponse, summary="List cameras")
def list_cameras(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by name, device identifier, manufacturer, or model"),
    exam_hall_id: int | None = Query(None, description="Filter by exam hall"),
    status: str | None = Query(None, description="Filter by status"),
    include_inactive: bool = Query(False, description="Include deactivated cameras"),
    db: Session = Depends(get_db),
):
    cameras, total = camera_service.list_cameras(
        db,
        page=page,
        page_size=page_size,
        search=search,
        exam_hall_id=exam_hall_id,
        status=status,
        include_inactive=include_inactive,
    )
    return CameraListResponse(
        items=[CameraResponse.model_validate(c) for c in cameras],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{camera_id}", response_model=CameraResponse, summary="Get a camera")
def get_camera(camera_id: int, db: Session = Depends(get_db)):
    camera = camera_service.get_camera(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.patch("/{camera_id}", response_model=CameraResponse, summary="Update a camera")
def update_camera(camera_id: int, data: CameraUpdate, db: Session = Depends(get_db)):
    try:
        return camera_service.update_camera(db, camera_id, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete(
    "/{camera_id}",
    response_model=CameraResponse,
    summary="Deactivate a camera (soft delete)",
)
def deactivate_camera(camera_id: int, db: Session = Depends(get_db)):
    try:
        return camera_service.deactivate_camera(db, camera_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

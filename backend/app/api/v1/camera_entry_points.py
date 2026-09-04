from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.camera_entry_point import (
    CameraEntryPointMappingCreate,
    CameraEntryPointMappingListResponse,
    CameraEntryPointMappingResponse,
    CameraEntryPointMappingUpdate,
)
from app.services import camera_entry_point as mapping_service

router = APIRouter(prefix="/camera-entry-points", tags=["Camera Entry Points"])


@router.post(
    "",
    response_model=CameraEntryPointMappingResponse,
    status_code=201,
    summary="Create a camera-to-entry-point mapping",
)
def create_mapping(data: CameraEntryPointMappingCreate, db: Session = Depends(get_db)):
    try:
        return mapping_service.create_mapping(db, data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=CameraEntryPointMappingListResponse, summary="List mappings")
def list_mappings(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    camera_id: int | None = Query(None, description="Filter by camera"),
    entry_point_id: int | None = Query(None, description="Filter by entry point"),
    include_disabled: bool = Query(False, description="Include disabled mappings"),
    db: Session = Depends(get_db),
):
    mappings, total = mapping_service.list_mappings(
        db,
        page=page,
        page_size=page_size,
        camera_id=camera_id,
        entry_point_id=entry_point_id,
        include_disabled=include_disabled,
    )
    return CameraEntryPointMappingListResponse(
        items=[CameraEntryPointMappingResponse.model_validate(m) for m in mappings],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{mapping_id}", response_model=CameraEntryPointMappingResponse, summary="Get a mapping")
def get_mapping(mapping_id: int, db: Session = Depends(get_db)):
    mapping = mapping_service.get_mapping(db, mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return mapping


@router.patch("/{mapping_id}", response_model=CameraEntryPointMappingResponse, summary="Update a mapping")
def update_mapping(mapping_id: int, data: CameraEntryPointMappingUpdate, db: Session = Depends(get_db)):
    try:
        return mapping_service.update_mapping(db, mapping_id, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/{mapping_id}",
    response_model=CameraEntryPointMappingResponse,
    summary="Disable a mapping (soft delete)",
)
def deactivate_mapping(mapping_id: int, db: Session = Depends(get_db)):
    try:
        return mapping_service.deactivate_mapping(db, mapping_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

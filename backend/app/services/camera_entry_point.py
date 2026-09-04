from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.camera_entry_point import CameraEntryPointMapping
from app.schemas.camera_entry_point import (
    CameraEntryPointMappingCreate,
    CameraEntryPointMappingUpdate,
)


def create_mapping(db: Session, data: CameraEntryPointMappingCreate) -> CameraEntryPointMapping:
    existing = (
        db.query(CameraEntryPointMapping)
        .filter(
            CameraEntryPointMapping.camera_id == data.camera_id,
            CameraEntryPointMapping.entry_point_id == data.entry_point_id,
        )
        .first()
    )
    if existing:
        raise ValueError(
            f"Mapping between camera {data.camera_id} and entry point {data.entry_point_id} already exists"
        )

    mapping = CameraEntryPointMapping(
        camera_id=data.camera_id,
        entry_point_id=data.entry_point_id,
    )
    db.add(mapping)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Mapping between camera {data.camera_id} and entry point {data.entry_point_id} already exists"
        )

    db.refresh(mapping)
    return mapping


def get_mapping(db: Session, mapping_id: int) -> CameraEntryPointMapping | None:
    return db.query(CameraEntryPointMapping).filter(
        CameraEntryPointMapping.id == mapping_id
    ).first()


def list_mappings(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    camera_id: int | None = None,
    entry_point_id: int | None = None,
    include_disabled: bool = False,
) -> tuple[list[CameraEntryPointMapping], int]:
    query = db.query(CameraEntryPointMapping)

    if not include_disabled:
        query = query.filter(CameraEntryPointMapping.is_enabled == True)

    if camera_id is not None:
        query = query.filter(CameraEntryPointMapping.camera_id == camera_id)

    if entry_point_id is not None:
        query = query.filter(CameraEntryPointMapping.entry_point_id == entry_point_id)

    total = query.count()
    mappings = (
        query.order_by(CameraEntryPointMapping.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return mappings, total


def update_mapping(db: Session, mapping_id: int, data: CameraEntryPointMappingUpdate) -> CameraEntryPointMapping:
    mapping = db.query(CameraEntryPointMapping).filter(
        CameraEntryPointMapping.id == mapping_id
    ).first()
    if not mapping:
        raise LookupError(f"Mapping with id {mapping_id} not found")

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(mapping, field, value)

    db.commit()
    db.refresh(mapping)
    return mapping


def deactivate_mapping(db: Session, mapping_id: int) -> CameraEntryPointMapping:
    mapping = db.query(CameraEntryPointMapping).filter(
        CameraEntryPointMapping.id == mapping_id
    ).first()
    if not mapping:
        raise LookupError(f"Mapping with id {mapping_id} not found")

    mapping.is_enabled = False
    db.commit()
    db.refresh(mapping)
    return mapping

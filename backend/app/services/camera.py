from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.camera import Camera, CameraStatus
from app.schemas.camera import CameraCreate, CameraUpdate


def create_camera(db: Session, data: CameraCreate) -> Camera:
    device_identifier = data.device_identifier.strip()
    name = data.name.strip()

    existing = (
        db.query(Camera)
        .filter(Camera.device_identifier == device_identifier)
        .first()
    )
    if existing:
        raise ValueError(
            f"Camera with device identifier '{device_identifier}' already exists"
        )

    camera = Camera(
        name=name,
        device_identifier=device_identifier,
        camera_type=data.camera_type.strip() if data.camera_type else None,
        manufacturer=data.manufacturer.strip() if data.manufacturer else None,
        model_name=data.model_name.strip() if data.model_name else None,
        resolution_width=data.resolution_width,
        resolution_height=data.resolution_height,
        exam_hall_id=data.exam_hall_id,
        connection_info=data.connection_info,
    )
    db.add(camera)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Camera with device identifier '{device_identifier}' already exists"
        )

    db.refresh(camera)
    return camera


def get_camera(db: Session, camera_id: int) -> Camera | None:
    return db.query(Camera).filter(Camera.id == camera_id).first()


def list_cameras(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    exam_hall_id: int | None = None,
    status: str | None = None,
    include_inactive: bool = False,
) -> tuple[list[Camera], int]:
    query = db.query(Camera)

    if not include_inactive:
        query = query.filter(Camera.is_active == True)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Camera.name.ilike(pattern),
                Camera.device_identifier.ilike(pattern),
                Camera.manufacturer.ilike(pattern),
                Camera.model_name.ilike(pattern),
            )
        )

    if exam_hall_id is not None:
        query = query.filter(Camera.exam_hall_id == exam_hall_id)

    if status is not None:
        query = query.filter(Camera.status == status.strip())

    total = query.count()
    cameras = (
        query.order_by(Camera.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return cameras, total


def update_camera(db: Session, camera_id: int, data: CameraUpdate) -> Camera:
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise LookupError(f"Camera with id {camera_id} not found")

    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] is not None:
        update_data["name"] = update_data["name"].strip()

    if "device_identifier" in update_data and update_data["device_identifier"] is not None:
        update_data["device_identifier"] = update_data["device_identifier"].strip()

    if "camera_type" in update_data and update_data["camera_type"] is not None:
        update_data["camera_type"] = update_data["camera_type"].strip()

    if "manufacturer" in update_data and update_data["manufacturer"] is not None:
        update_data["manufacturer"] = update_data["manufacturer"].strip()

    if "model_name" in update_data and update_data["model_name"] is not None:
        update_data["model_name"] = update_data["model_name"].strip()

    new_device_identifier = update_data.get("device_identifier", camera.device_identifier)

    if new_device_identifier != camera.device_identifier:
        existing = (
            db.query(Camera)
            .filter(
                Camera.device_identifier == new_device_identifier,
                Camera.id != camera_id,
            )
            .first()
        )
        if existing:
            raise ValueError(
                f"Camera with device identifier '{new_device_identifier}' already exists"
            )

    for field, value in update_data.items():
        setattr(camera, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Camera with device identifier '{new_device_identifier}' already exists"
        )

    db.refresh(camera)
    return camera


def deactivate_camera(db: Session, camera_id: int) -> Camera:
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise LookupError(f"Camera with id {camera_id} not found")

    camera.is_active = False
    camera.status = CameraStatus.DISABLED.value
    db.commit()
    db.refresh(camera)
    return camera

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entry_point import EntryPoint
from app.schemas.entry_point import EntryPointCreate, EntryPointUpdate


def create_entry_point(db: Session, data: EntryPointCreate) -> EntryPoint:
    name = data.name.strip()
    code = data.code.strip().upper()

    existing = (
        db.query(EntryPoint)
        .filter(EntryPoint.code == code)
        .first()
    )
    if existing:
        raise ValueError(
            f"Entry point with code '{code}' already exists"
        )

    entry_point = EntryPoint(
        name=name,
        code=code,
        description=data.description,
        location_detail=data.location_detail.strip() if data.location_detail else None,
        exam_hall_id=data.exam_hall_id,
    )
    db.add(entry_point)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Entry point with code '{code}' already exists"
        )

    db.refresh(entry_point)
    return entry_point


def get_entry_point(db: Session, entry_point_id: int) -> EntryPoint | None:
    return db.query(EntryPoint).filter(EntryPoint.id == entry_point_id).first()


def list_entry_points(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    exam_hall_id: int | None = None,
    include_inactive: bool = False,
) -> tuple[list[EntryPoint], int]:
    query = db.query(EntryPoint)

    if not include_inactive:
        query = query.filter(EntryPoint.is_active == True)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                EntryPoint.name.ilike(pattern),
                EntryPoint.code.ilike(pattern),
                EntryPoint.description.ilike(pattern),
                EntryPoint.location_detail.ilike(pattern),
            )
        )

    if exam_hall_id is not None:
        query = query.filter(EntryPoint.exam_hall_id == exam_hall_id)

    total = query.count()
    entry_points = (
        query.order_by(EntryPoint.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return entry_points, total


def update_entry_point(db: Session, entry_point_id: int, data: EntryPointUpdate) -> EntryPoint:
    entry_point = db.query(EntryPoint).filter(EntryPoint.id == entry_point_id).first()
    if not entry_point:
        raise LookupError(f"Entry point with id {entry_point_id} not found")

    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] is not None:
        update_data["name"] = update_data["name"].strip()

    if "code" in update_data and update_data["code"] is not None:
        update_data["code"] = update_data["code"].strip().upper()

    if "location_detail" in update_data and update_data["location_detail"] is not None:
        update_data["location_detail"] = update_data["location_detail"].strip()

    new_code = update_data.get("code", entry_point.code)

    if new_code != entry_point.code:
        existing = (
            db.query(EntryPoint)
            .filter(
                EntryPoint.code == new_code,
                EntryPoint.id != entry_point_id,
            )
            .first()
        )
        if existing:
            raise ValueError(
                f"Entry point with code '{new_code}' already exists"
            )

    for field, value in update_data.items():
        setattr(entry_point, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Entry point with code '{new_code}' already exists"
        )

    db.refresh(entry_point)
    return entry_point


def deactivate_entry_point(db: Session, entry_point_id: int) -> EntryPoint:
    entry_point = db.query(EntryPoint).filter(EntryPoint.id == entry_point_id).first()
    if not entry_point:
        raise LookupError(f"Entry point with id {entry_point_id} not found")

    entry_point.is_active = False
    db.commit()
    db.refresh(entry_point)
    return entry_point

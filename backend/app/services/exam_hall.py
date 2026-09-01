from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.exam_hall import ExamHall
from app.schemas.exam_hall import ExamHallCreate, ExamHallUpdate


def create_hall(db: Session, data: ExamHallCreate) -> ExamHall:
    building = data.building.strip()
    room_number = data.room_number.strip()
    name = data.name.strip() if data.name else None

    existing = (
        db.query(ExamHall)
        .filter(ExamHall.building == building, ExamHall.room_number == room_number)
        .first()
    )
    if existing:
        raise ValueError(
            f"Hall '{building}' room '{room_number}' already exists"
        )

    hall = ExamHall(
        building=building,
        room_number=room_number,
        name=name,
        capacity=data.capacity,
        rows=data.rows,
        columns=data.columns,
    )
    db.add(hall)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Hall '{building}' room '{room_number}' already exists"
        )

    db.refresh(hall)
    return hall


def get_hall(db: Session, hall_id: int) -> ExamHall | None:
    return db.query(ExamHall).filter(ExamHall.id == hall_id).first()


def list_halls(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    include_inactive: bool = False,
) -> tuple[list[ExamHall], int]:
    query = db.query(ExamHall)

    if not include_inactive:
        query = query.filter(ExamHall.is_active == True)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ExamHall.building.ilike(pattern),
                ExamHall.room_number.ilike(pattern),
                ExamHall.name.ilike(pattern),
            )
        )

    total = query.count()
    halls = (
        query.order_by(ExamHall.building, ExamHall.room_number)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return halls, total


def update_hall(db: Session, hall_id: int, data: ExamHallUpdate) -> ExamHall:
    hall = db.query(ExamHall).filter(ExamHall.id == hall_id).first()
    if not hall:
        raise LookupError(f"Hall with id {hall_id} not found")

    update_data = data.model_dump(exclude_unset=True)

    if "building" in update_data and update_data["building"] is not None:
        update_data["building"] = update_data["building"].strip()

    if "room_number" in update_data and update_data["room_number"] is not None:
        update_data["room_number"] = update_data["room_number"].strip()

    if "name" in update_data and update_data["name"] is not None:
        update_data["name"] = update_data["name"].strip()

    new_building = update_data.get("building", hall.building)
    new_room_number = update_data.get("room_number", hall.room_number)

    if new_building != hall.building or new_room_number != hall.room_number:
        existing = (
            db.query(ExamHall)
            .filter(
                ExamHall.building == new_building,
                ExamHall.room_number == new_room_number,
                ExamHall.id != hall_id,
            )
            .first()
        )
        if existing:
            raise ValueError(
                f"Hall '{new_building}' room '{new_room_number}' already exists"
            )

    for field, value in update_data.items():
        setattr(hall, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Hall '{new_building}' room '{new_room_number}' already exists"
        )

    db.refresh(hall)
    return hall


def deactivate_hall(db: Session, hall_id: int) -> ExamHall:
    hall = db.query(ExamHall).filter(ExamHall.id == hall_id).first()
    if not hall:
        raise LookupError(f"Hall with id {hall_id} not found")

    hall.is_active = False
    db.commit()
    db.refresh(hall)
    return hall

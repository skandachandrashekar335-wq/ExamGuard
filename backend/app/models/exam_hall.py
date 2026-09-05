from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class ExamHall(Base):
    __tablename__ = "exam_halls"
    __table_args__ = (
        UniqueConstraint("building", "room_number", name="uq_hall_building_room"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    building: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    room_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    rows: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Seating rows (optional)",
    )
    columns: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Seating columns (optional)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        index=True,
        comment="Soft-delete flag. Inactive halls are hidden from active operations.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    seat_assignments: Mapped[list["SeatAssignment"]] = relationship(  # noqa: F821
        back_populates="hall",
    )
    cameras: Mapped[list["Camera"]] = relationship(  # noqa: F821
        back_populates="hall",
    )
    entry_points: Mapped[list["EntryPoint"]] = relationship(  # noqa: F821
        back_populates="hall",
    )
    sessions: Mapped[list["ExaminationSession"]] = relationship(  # noqa: F821
        back_populates="hall",
    )

    def __repr__(self) -> str:
        return f"<ExamHall id={self.id} building={self.building!r} room={self.room_number!r}>"

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class EntryPoint(Base):
    __tablename__ = "entry_points"
    __table_args__ = (
        UniqueConstraint("code", name="uq_entry_point_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable entry point name",
    )
    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Short unique code (e.g. MAIN_GATE, NORTH_ENTRY)",
    )
    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    location_detail: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Physical location detail (floor, wing, etc.)",
    )
    exam_hall_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("exam_halls.id"),
        nullable=True,
        index=True,
        comment="Exam hall this entry point serves",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        index=True,
        comment="Soft-delete flag. Inactive entry points are hidden from active operations.",
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

    hall: Mapped["ExamHall | None"] = relationship(  # noqa: F821
        back_populates="entry_points",
    )
    camera_mappings: Mapped[list["CameraEntryPointMapping"]] = relationship(  # noqa: F821
        back_populates="entry_point",
    )

    def __repr__(self) -> str:
        return f"<EntryPoint id={self.id} code={self.code!r}>"

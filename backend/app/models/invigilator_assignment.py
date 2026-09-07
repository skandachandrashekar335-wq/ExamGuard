"""Invigilator assignment model.

Links a User (with INVIGILATOR role) to a specific Exam, ExamHall,
EntryPoint, and optionally a Camera. This is the authoritative mapping
that determines what an invigilator can access and operate.

The backend enforces:
- An invigilator can only see their assigned examination/hall
- An invigilator can only start exams they are assigned to
- An invigilator cannot access another invigilator's session
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class InvigilatorAssignment(Base):
    __tablename__ = "invigilator_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)

    # The invigilator user
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="User with INVIGILATOR role",
    )

    # The exam this invigilator is assigned to
    exam_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exams.id"),
        nullable=False,
        index=True,
        comment="Examination this invigilator is assigned to",
    )

    # The hall they are responsible for
    exam_hall_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exam_halls.id"),
        nullable=False,
        index=True,
        comment="Exam hall this invigilator is responsible for",
    )

    # Entry point they monitor
    entry_point_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("entry_points.id"),
        nullable=True,
        index=True,
        comment="Entry point this invigilator monitors (optional)",
    )

    # Camera they control
    camera_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("cameras.id"),
        nullable=True,
        index=True,
        comment="Camera assigned to this invigilator (optional)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        index=True,
        comment="Soft-delete flag",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional notes about this assignment",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id], lazy="select")
    exam = relationship("Exam", foreign_keys=[exam_id], lazy="select")
    exam_hall = relationship("ExamHall", foreign_keys=[exam_hall_id], lazy="select")
    entry_point = relationship("EntryPoint", foreign_keys=[entry_point_id], lazy="select")
    camera = relationship("Camera", foreign_keys=[camera_id], lazy="select")

    def __repr__(self) -> str:
        return (
            f"<InvigilatorAssignment id={self.id} user_id={self.user_id} "
            f"exam_id={self.exam_id} hall_id={self.exam_hall_id}>"
        )

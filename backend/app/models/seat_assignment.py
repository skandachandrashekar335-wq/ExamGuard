import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class SeatAssignmentStatus(str, enum.Enum):
    ASSIGNED = "ASSIGNED"
    CANCELLED = "CANCELLED"


class SeatAssignment(Base):
    __tablename__ = "seat_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_registration_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exam_registrations.id"),
        nullable=False,
        index=True,
    )
    exam_hall_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exam_halls.id"),
        nullable=False,
        index=True,
    )
    seat_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    row_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Seating row (optional)",
    )
    column_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Seating column (optional)",
    )
    exam_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exams.id"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("students.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=SeatAssignmentStatus.ASSIGNED.value,
        index=True,
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

    registration: Mapped["ExamRegistration"] = relationship(  # noqa: F821
        back_populates="seat_assignments",
    )
    hall: Mapped["ExamHall"] = relationship(  # noqa: F821
        back_populates="seat_assignments",
    )
    exam: Mapped["Exam"] = relationship(  # noqa: F821
        back_populates="seat_assignments",
    )
    student: Mapped["Student"] = relationship(  # noqa: F821
        back_populates="seat_assignments",
    )

    def __repr__(self) -> str:
        return (
            f"<SeatAssignment id={self.id} "
            f"seat={self.seat_number!r} "
            f"status={self.status!r}>"
        )

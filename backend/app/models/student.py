from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    usn: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
        comment="University Seat Number / Student ID",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        index=True,
        comment="Soft-delete flag. Inactive students are hidden from active operations.",
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

    registrations: Mapped[list["ExamRegistration"]] = relationship(  # noqa: F821
        back_populates="student",
    )
    seat_assignments: Mapped[list["SeatAssignment"]] = relationship(  # noqa: F821
        back_populates="student",
    )

    def __repr__(self) -> str:
        return f"<Student id={self.id} usn={self.usn!r} name={self.name!r}>"

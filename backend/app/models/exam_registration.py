import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class RegistrationStatus(str, enum.Enum):
    REGISTERED = "REGISTERED"
    CANCELLED = "CANCELLED"


class ExamRegistration(Base):
    __tablename__ = "exam_registrations"
    __table_args__ = (
        UniqueConstraint("student_id", "exam_id", name="uq_registration_student_exam"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("students.id"),
        nullable=False,
        index=True,
    )
    exam_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exams.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=RegistrationStatus.REGISTERED.value,
        index=True,
    )
    registered_at: Mapped[datetime] = mapped_column(
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

    student: Mapped["Student"] = relationship(back_populates="registrations")  # noqa: F821
    exam: Mapped["Exam"] = relationship(back_populates="registrations")  # noqa: F821
    seat_assignments: Mapped[list["SeatAssignment"]] = relationship(  # noqa: F821
        back_populates="registration",
    )

    def __repr__(self) -> str:
        return (
            f"<ExamRegistration id={self.id} "
            f"student_id={self.student_id} exam_id={self.exam_id} "
            f"status={self.status!r}>"
        )

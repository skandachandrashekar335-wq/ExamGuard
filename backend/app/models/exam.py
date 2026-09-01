from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Exam(Base):
    __tablename__ = "exams"
    __table_args__ = (
        UniqueConstraint("subject_id", "exam_date", "start_time", name="uq_exam_subject_date_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("subjects.id"),
        nullable=False,
        index=True,
    )
    exam_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    exam_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )
    end_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )
    semester: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Semester number (1-8)",
    )
    department: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        index=True,
        comment="Soft-delete flag. Inactive exams are hidden from active operations.",
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

    subject: Mapped["Subject"] = relationship(back_populates="exams")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Exam id={self.id} exam_name={self.exam_name!r} exam_date={self.exam_date!r}>"

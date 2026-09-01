from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("code", "department", name="uq_subject_code_department"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Subject code (e.g. CS501)",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    department: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    semester: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Semester number (1-8)",
    )
    credits: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Credit hours (optional)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        index=True,
        comment="Soft-delete flag. Inactive subjects are hidden from active operations.",
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

    def __repr__(self) -> str:
        return f"<Subject id={self.id} code={self.code!r} name={self.name!r}>"

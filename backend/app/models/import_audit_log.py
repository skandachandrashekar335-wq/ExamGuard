import enum
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ImportType(str, enum.Enum):
    STUDENTS = "students"
    SUBJECTS_EXAMS = "subjects_exams"
    REGISTRATIONS = "registrations"
    REGISTRATION_CANCELLATIONS = "registration_cancellations"
    SEAT_ASSIGNMENTS = "seat_assignments"
    SEAT_ASSIGNMENT_CANCELLATIONS = "seat_assignment_cancellations"


class ImportOperation(str, enum.Enum):
    IMPORT = "import"
    CANCELLATION = "cancellation"


class ImportAuditStatus(str, enum.Enum):
    STARTED = "started"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class ImportAuditLog(Base):
    __tablename__ = "import_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=ImportAuditStatus.STARTED.value, index=True
    )
    total_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    successful_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    skipped_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    failed_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    error_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    actor: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="Future-compatible: will be populated when authentication is implemented",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<ImportAuditLog id={self.id} "
            f"type={self.import_type!r} status={self.status!r}>"
        )

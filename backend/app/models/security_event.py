import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class SecurityEventType(str, enum.Enum):
    SIGNAL_DETECTED = "SIGNAL_DETECTED"
    RISK_THRESHOLD_EXCEEDED = "RISK_THRESHOLD_EXCEEDED"
    ENTRY_ESCALATED = "ENTRY_ESCALATED"
    DUPLICATE_ENTRY_DETECTED = "DUPLICATE_ENTRY_DETECTED"
    IDENTITY_MISMATCH_DETECTED = "IDENTITY_MISMATCH_DETECTED"
    MANUAL_FLAG = "MANUAL_FLAG"
    ATTENDANCE_CORRECTED = "ATTENDANCE_CORRECTED"
    CAMERA_OFFLINE_DURING_EXAM = "CAMERA_OFFLINE_DURING_EXAM"
    UNUSUAL_PATTERN = "UNUSUAL_PATTERN"
    PROXY_RISK_CRITICAL = "PROXY_RISK_CRITICAL"


class SecurityEventSeverity(str, enum.Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SecurityAlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of security event",
    )
    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Event severity level",
    )
    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Domain entity type this event relates to",
    )
    entity_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Domain entity ID",
    )
    entry_verification_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("entry_verifications.id"),
        nullable=True,
        index=True,
        comment="Related entry verification if applicable",
    )
    student_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("students.id"),
        nullable=True,
        index=True,
        comment="Related student if applicable",
    )
    exam_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("exams.id"),
        nullable=True,
        index=True,
        comment="Related exam if applicable",
    )
    hall_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("exam_halls.id"),
        nullable=True,
        index=True,
        comment="Related exam hall if applicable",
    )
    entry_point_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("entry_points.id"),
        nullable=True,
        comment="Related entry point if applicable",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable event description",
    )
    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON-encoded structured evidence/context data",
    )
    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Source that produced this event (e.g. signal_detection, proxy_risk, manual)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="When this event was created",
    )

    entry_verification: Mapped["EntryVerification | None"] = relationship()  # noqa: F821
    student: Mapped["Student | None"] = relationship()  # noqa: F821
    exam: Mapped["Exam | None"] = relationship()  # noqa: F821
    exam_hall: Mapped["ExamHall | None"] = relationship()  # noqa: F821
    entry_point: Mapped["EntryPoint | None"] = relationship()  # noqa: F821
    alerts: Mapped[list["SecurityAlert"]] = relationship(back_populates="security_event")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<SecurityEvent id={self.id} "
            f"event_type={self.event_type!r} "
            f"severity={self.severity!r} "
            f"entity_type={self.entity_type!r}>"
        )


class SecurityAlert(Base):
    __tablename__ = "security_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    security_event_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("security_events.id"),
        nullable=False,
        index=True,
        comment="Security event that triggered this alert",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=SecurityAlertStatus.OPEN.value,
        index=True,
        comment="Alert lifecycle status",
    )
    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Alert severity (inherited from event)",
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable alert message",
    )
    assigned_to: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Future-compatible: operator assigned to this alert",
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the alert was acknowledged",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the alert was resolved",
    )
    resolution_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notes from the operator on resolution",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="When the alert was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="When the alert was last updated",
    )

    security_event: Mapped["SecurityEvent"] = relationship(back_populates="alerts")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<SecurityAlert id={self.id} "
            f"status={self.status!r} "
            f"severity={self.severity!r}>"
        )

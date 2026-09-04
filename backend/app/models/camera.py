import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class CameraStatus(str, enum.Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"
    DISABLED = "DISABLED"


class Camera(Base):
    __tablename__ = "cameras"
    __table_args__ = (
        UniqueConstraint("device_identifier", name="uq_camera_device_identifier"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable camera name",
    )
    device_identifier: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique device identifier (serial number, MAC, etc.)",
    )
    camera_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Camera type/protocol (e.g. IP, USB, RTSP)",
    )
    manufacturer: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    model_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    resolution_width: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Max resolution width in pixels",
    )
    resolution_height: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Max resolution height in pixels",
    )
    exam_hall_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("exam_halls.id"),
        nullable=True,
        index=True,
        comment="Exam hall this camera is installed in",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=CameraStatus.UNKNOWN.value,
        index=True,
        comment="Device operational status",
    )
    connection_info: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Connection metadata (IP, endpoint URL) — no credentials",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        index=True,
        comment="Soft-delete flag. Inactive cameras are hidden from active operations.",
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
        back_populates="cameras",
    )
    entry_point_mappings: Mapped[list["CameraEntryPointMapping"]] = relationship(  # noqa: F821
        back_populates="camera",
    )

    def __repr__(self) -> str:
        return f"<Camera id={self.id} name={self.name!r} status={self.status!r}>"

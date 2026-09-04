from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class CameraEntryPointMapping(Base):
    __tablename__ = "camera_entry_points"
    __table_args__ = (
        UniqueConstraint(
            "camera_id",
            "entry_point_id",
            name="uq_camera_entry_point",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cameras.id"),
        nullable=False,
        index=True,
    )
    entry_point_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("entry_points.id"),
        nullable=False,
        index=True,
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Whether this mapping is currently active",
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

    camera: Mapped["Camera"] = relationship(  # noqa: F821
        back_populates="entry_point_mappings",
    )
    entry_point: Mapped["EntryPoint"] = relationship(  # noqa: F821
        back_populates="camera_mappings",
    )

    def __repr__(self) -> str:
        return f"<CameraEntryPointMapping id={self.id} camera_id={self.camera_id} entry_point_id={self.entry_point_id}>"

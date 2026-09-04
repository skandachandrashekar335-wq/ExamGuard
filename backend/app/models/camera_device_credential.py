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


class CredentialStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class CameraDeviceCredential(Base):
    """Device credential for secure camera-to-ExamGuard communication.

    Stores a SHA-256 hash of the device secret. The raw secret is only
    returned once at provisioning time and never stored in plaintext.
    """

    __tablename__ = "camera_device_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Camera this credential belongs to",
    )
    label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable label for this credential",
    )
    secret_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="SHA-256 hash of the device secret (never store plaintext)",
    )
    secret_prefix: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        comment="First 8 chars of secret for identification (not the hash)",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=CredentialStatus.ACTIVE.value,
        index=True,
        comment="Credential status (ACTIVE, REVOKED)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        index=True,
        comment="Soft-delete flag",
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
        back_populates="device_credentials",
    )

    def __repr__(self) -> str:
        return (
            f"<CameraDeviceCredential id={self.id} camera_id={self.camera_id} "
            f"prefix={self.secret_prefix!r} status={self.status!r}>"
        )

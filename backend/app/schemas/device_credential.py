from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceCredentialCreate(BaseModel):
    """Request to provision a new device credential."""

    camera_id: int = Field(
        ...,
        description="Camera ID this credential belongs to",
    )
    label: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable label for this credential",
    )


class DeviceCredentialResponse(BaseModel):
    """Response for credential operations (never includes secret)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    label: str
    secret_prefix: str
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DeviceCredentialProvisionResponse(BaseModel):
    """Response when creating a credential (includes raw secret ONCE)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    label: str
    secret: str = Field(
        ...,
        description="Raw device secret (shown only once at provisioning)",
    )
    secret_prefix: str
    status: str
    created_at: datetime


class DeviceHealthRequest(BaseModel):
    """Request from a device to report health status.

    The device authenticates via the X-Device-Credential header.
    The camera_id is derived from the authenticated credential.
    """

    status: str = Field(
        ...,
        description="Observed device status (ONLINE, OFFLINE)",
    )
    observed_at: datetime | None = Field(
        default=None,
        description="When observation was made (defaults to server time)",
    )
    reason: str | None = Field(
        default=None,
        max_length=50,
        description="Reason category (DEVICE_RESPONDED, DEVICE_UNREACHABLE)",
    )


class DeviceHealthResponse(BaseModel):
    """Response after device reports health status."""

    model_config = ConfigDict(from_attributes=True)

    camera_id: int
    status: str
    last_seen_at: datetime | None
    last_health_check_at: datetime | None
    health_reason: str | None
    is_active: bool

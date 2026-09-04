from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthObservationCreate(BaseModel):
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


class HealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    camera_id: int
    status: str
    last_seen_at: datetime | None
    last_health_check_at: datetime | None
    health_reason: str | None
    is_active: bool

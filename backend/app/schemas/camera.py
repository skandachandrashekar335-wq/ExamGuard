from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CameraCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable camera name",
        examples=["Main Hall Camera 1"],
    )
    device_identifier: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique device identifier",
        examples=["CAM-001"],
    )
    camera_type: str | None = Field(
        default=None,
        max_length=100,
        description="Camera type/protocol",
        examples=["IP"],
    )
    manufacturer: str | None = Field(
        default=None,
        max_length=100,
    )
    model_name: str | None = Field(
        default=None,
        max_length=100,
    )
    resolution_width: int | None = Field(
        default=None,
        gt=0,
        description="Max resolution width in pixels",
    )
    resolution_height: int | None = Field(
        default=None,
        gt=0,
        description="Max resolution height in pixels",
    )
    exam_hall_id: int | None = Field(
        default=None,
        description="Exam hall this camera is installed in",
    )
    connection_info: str | None = Field(
        default=None,
        description="Connection metadata (IP, endpoint URL) — no credentials",
    )


class CameraUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Human-readable camera name",
    )
    device_identifier: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Unique device identifier",
    )
    camera_type: str | None = Field(
        default=None,
        max_length=100,
        description="Camera type/protocol",
    )
    manufacturer: str | None = Field(
        default=None,
        max_length=100,
    )
    model_name: str | None = Field(
        default=None,
        max_length=100,
    )
    resolution_width: int | None = Field(
        default=None,
        gt=0,
        description="Max resolution width in pixels",
    )
    resolution_height: int | None = Field(
        default=None,
        gt=0,
        description="Max resolution height in pixels",
    )
    exam_hall_id: int | None = Field(
        default=None,
        description="Exam hall this camera is installed in",
    )
    connection_info: str | None = Field(
        default=None,
        description="Connection metadata (IP, endpoint URL) — no credentials",
    )
    status: str | None = Field(
        default=None,
        description="Device operational status (ONLINE, OFFLINE, UNKNOWN, DISABLED)",
    )
    is_active: bool | None = Field(
        default=None,
        description="Set to false to deactivate a camera",
    )


class CameraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    device_identifier: str
    camera_type: str | None
    manufacturer: str | None
    model_name: str | None
    resolution_width: int | None
    resolution_height: int | None
    exam_hall_id: int | None
    status: str
    connection_info: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CameraListResponse(BaseModel):
    items: list[CameraResponse]
    page: int
    page_size: int
    total: int

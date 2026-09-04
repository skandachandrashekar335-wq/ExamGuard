from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CameraEntryPointMappingCreate(BaseModel):
    camera_id: int = Field(
        ...,
        description="Camera ID",
    )
    entry_point_id: int = Field(
        ...,
        description="Entry point ID",
    )


class CameraEntryPointMappingUpdate(BaseModel):
    is_enabled: bool | None = Field(
        default=None,
        description="Whether this mapping is currently active",
    )


class CameraEntryPointMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    entry_point_id: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class CameraEntryPointMappingListResponse(BaseModel):
    items: list[CameraEntryPointMappingResponse]
    page: int
    page_size: int
    total: int

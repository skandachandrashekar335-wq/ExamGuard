from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EntryPointCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable entry point name",
        examples=["Main Gate"],
    )
    code: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Short unique code",
        examples=["MAIN_GATE"],
    )
    description: str | None = Field(
        default=None,
        max_length=500,
    )
    location_detail: str | None = Field(
        default=None,
        max_length=255,
        description="Physical location detail",
        examples=["Ground floor, east wing"],
    )
    exam_hall_id: int | None = Field(
        default=None,
        description="Exam hall this entry point serves",
    )


class EntryPointUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Human-readable entry point name",
    )
    code: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Short unique code",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
    )
    location_detail: str | None = Field(
        default=None,
        max_length=255,
        description="Physical location detail",
    )
    exam_hall_id: int | None = Field(
        default=None,
        description="Exam hall this entry point serves",
    )
    is_active: bool | None = Field(
        default=None,
        description="Set to false to deactivate an entry point",
    )


class EntryPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: str | None
    location_detail: str | None
    exam_hall_id: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class EntryPointListResponse(BaseModel):
    items: list[EntryPointResponse]
    page: int
    page_size: int
    total: int

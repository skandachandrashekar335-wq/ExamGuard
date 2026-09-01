from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SubjectCreate(BaseModel):
    code: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Subject code (e.g. CS501)",
        examples=["CS501"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Subject name",
        examples=["Machine Learning"],
    )
    department: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Department offering the subject",
        examples=["Computer Science"],
    )
    semester: int = Field(
        ...,
        ge=1,
        le=8,
        description="Semester number (1-8)",
        examples=[5],
    )
    credits: int | None = Field(
        default=None,
        gt=0,
        description="Credit hours (optional)",
        examples=[4],
    )


class SubjectUpdate(BaseModel):
    code: str | None = Field(
        default=None,
        min_length=1,
        max_length=20,
        description="Subject code (e.g. CS501)",
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Subject name",
    )
    department: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Department offering the subject",
    )
    semester: int | None = Field(
        default=None,
        ge=1,
        le=8,
        description="Semester number (1-8)",
    )
    credits: int | None = Field(
        default=None,
        gt=0,
        description="Credit hours (optional)",
    )
    is_active: bool | None = Field(
        default=None,
        description="Set to false to deactivate a subject",
    )


class SubjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    department: str
    semester: int
    credits: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SubjectListResponse(BaseModel):
    items: list[SubjectResponse]
    page: int
    page_size: int
    total: int

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StudentCreate(BaseModel):
    usn: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="University Seat Number / Student ID",
        examples=["1DS23BC001"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full name of the student",
        examples=["Rahul Kumar"],
    )


class StudentUpdate(BaseModel):
    usn: str | None = Field(
        default=None,
        min_length=1,
        max_length=20,
        description="University Seat Number / Student ID",
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Full name of the student",
    )
    is_active: bool | None = Field(
        default=None,
        description="Set to false to deactivate a student",
    )


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usn: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StudentListResponse(BaseModel):
    items: list[StudentResponse]
    page: int
    page_size: int
    total: int

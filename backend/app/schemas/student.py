from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_text(value: object) -> object:
    """Trim identity fields before length checks so whitespace-only values fail."""
    if isinstance(value, str):
        return value.strip()
    return value


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

    @field_validator("usn", "name", mode="before")
    @classmethod
    def strip_identity(cls, value: object) -> object:
        return _strip_text(value)


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

    @field_validator("usn", "name", mode="before")
    @classmethod
    def strip_identity(cls, value: object) -> object:
        return _strip_text(value)
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

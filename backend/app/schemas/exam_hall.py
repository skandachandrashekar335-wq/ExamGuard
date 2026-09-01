from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExamHallCreate(BaseModel):
    building: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Building name",
        examples=["Block A"],
    )
    room_number: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Room number",
        examples=["101"],
    )
    name: str | None = Field(
        default=None,
        max_length=255,
        description="Optional hall name",
        examples=["Main Auditorium"],
    )
    capacity: int = Field(
        ...,
        gt=0,
        description="Seating capacity",
        examples=[120],
    )
    rows: int | None = Field(
        default=None,
        gt=0,
        description="Number of seating rows (optional)",
        examples=[10],
    )
    columns: int | None = Field(
        default=None,
        gt=0,
        description="Number of seating columns (optional)",
        examples=[12],
    )

    @model_validator(mode="after")
    def validate_dimensions(self):
        if self.rows is not None and self.columns is not None:
            if self.rows * self.columns < self.capacity:
                raise ValueError(
                    f"rows x columns ({self.rows} x {self.columns} = {self.rows * self.columns}) "
                    f"must be >= capacity ({self.capacity})"
                )
        return self


class ExamHallUpdate(BaseModel):
    building: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Building name",
    )
    room_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Room number",
    )
    name: str | None = Field(
        default=None,
        max_length=255,
        description="Optional hall name",
    )
    capacity: int | None = Field(
        default=None,
        gt=0,
        description="Seating capacity",
    )
    rows: int | None = Field(
        default=None,
        gt=0,
        description="Number of seating rows (optional)",
    )
    columns: int | None = Field(
        default=None,
        gt=0,
        description="Number of seating columns (optional)",
    )
    is_active: bool | None = Field(
        default=None,
        description="Set to false to deactivate a hall",
    )

    @model_validator(mode="after")
    def validate_dimensions(self):
        if self.rows is not None and self.columns is not None:
            if self.capacity is not None:
                if self.rows * self.columns < self.capacity:
                    raise ValueError(
                        f"rows x columns ({self.rows} x {self.columns} = {self.rows * self.columns}) "
                        f"must be >= capacity ({self.capacity})"
                    )
        return self


class ExamHallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    building: str
    room_number: str
    name: str | None
    capacity: int
    rows: int | None
    columns: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ExamHallListResponse(BaseModel):
    items: list[ExamHallResponse]
    page: int
    page_size: int
    total: int

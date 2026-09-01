from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SeatAssignmentCreate(BaseModel):
    exam_registration_id: int = Field(
        ...,
        gt=0,
        description="Exam registration ID",
        examples=[1],
    )
    exam_hall_id: int = Field(
        ...,
        gt=0,
        description="Exam hall ID",
        examples=[1],
    )
    seat_number: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Seat identifier (e.g. A1, R1-C1)",
        examples=["A1"],
    )
    row_number: int | None = Field(
        default=None,
        gt=0,
        description="Seating row number (optional)",
        examples=[1],
    )
    column_number: int | None = Field(
        default=None,
        gt=0,
        description="Seating column number (optional)",
        examples=[1],
    )


class SeatAssignmentUpdate(BaseModel):
    status: str = Field(
        ...,
        description="New assignment status",
        examples=["ASSIGNED"],
    )


class SeatAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_registration_id: int
    exam_hall_id: int
    seat_number: str
    row_number: int | None
    column_number: int | None
    exam_id: int
    student_id: int
    status: str
    created_at: datetime
    updated_at: datetime


class SeatAssignmentWithDetails(SeatAssignmentResponse):
    student_usn: str | None = None
    student_name: str | None = None
    hall_building: str | None = None
    hall_room_number: str | None = None


class SeatAssignmentListResponse(BaseModel):
    items: list[SeatAssignmentWithDetails]
    page: int
    page_size: int
    total: int

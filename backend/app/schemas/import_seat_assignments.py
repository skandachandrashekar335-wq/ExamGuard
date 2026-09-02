from pydantic import BaseModel, Field


class SeatAssignmentItem(BaseModel):
    exam_registration_id: int = Field(
        ...,
        gt=0,
        description="Exam registration ID",
    )
    seat_number: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Seat identifier (e.g. A1, R1-C1)",
    )
    row_number: int | None = Field(
        default=None,
        gt=0,
        description="Seating row number (optional)",
    )
    column_number: int | None = Field(
        default=None,
        gt=0,
        description="Seating column number (optional)",
    )


class BulkSeatAssignmentRequest(BaseModel):
    exam_hall_id: int = Field(
        ...,
        gt=0,
        description="Exam hall ID to assign seats in",
    )
    assignments: list[SeatAssignmentItem] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="List of seat assignments (max 200)",
    )


class BulkSeatAssignmentItemResult(BaseModel):
    exam_registration_id: int
    seat_number: str
    status: str
    assignment_id: int | None = None
    error: str | None = None


class BulkSeatAssignmentResponse(BaseModel):
    total: int
    assigned: int
    skipped: int
    failed: int
    results: list[BulkSeatAssignmentItemResult]


class BulkCancelSeatRequest(BaseModel):
    assignment_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="List of assignment IDs to cancel (max 200)",
    )


class BulkCancelSeatItemResult(BaseModel):
    assignment_id: int
    status: str
    error: str | None = None


class BulkCancelSeatResponse(BaseModel):
    total: int
    cancelled: int
    skipped: int
    failed: int
    results: list[BulkCancelSeatItemResult]

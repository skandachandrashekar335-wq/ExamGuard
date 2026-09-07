from pydantic import BaseModel, ConfigDict


class SeatMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hall_ticket_id: int
    exam_registration_id: int
    student_id: int | None
    student_usn: str | None
    student_name: str | None
    exam_id: int | None
    seat_assignment_id: int | None
    seat_number: str | None
    exam_hall_id: int | None
    exam_hall_name: str | None
    status: str
    reasons: list[str]


class SeatMappingListResponse(BaseModel):
    items: list[SeatMappingResponse]
    total: int
    unresolved: int

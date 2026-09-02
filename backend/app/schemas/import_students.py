from pydantic import BaseModel, Field


class ImportStudentItem(BaseModel):
    usn: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="University Seat Number / Student ID",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full name of the student",
    )


class ImportStudentRequest(BaseModel):
    students: list[ImportStudentItem] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of students to import (max 500)",
    )


class ImportStudentItemResult(BaseModel):
    usn: str
    status: str
    error: str | None = None


class ImportStudentResponse(BaseModel):
    total: int
    created: int
    skipped: int
    failed: int
    results: list[ImportStudentItemResult]

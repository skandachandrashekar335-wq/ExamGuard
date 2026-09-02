from pydantic import BaseModel, Field


class BatchVerifyRequest(BaseModel):
    document_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of document IDs to verify (max 100)",
    )


class BatchVerifyItemResult(BaseModel):
    document_id: int
    step: str
    status: str
    error: str | None = None
    extraction_result_id: int | None = None
    match_result_id: int | None = None
    outcome_id: int | None = None
    overall_status: str | None = None
    decision: str | None = None
    ocr_avg_confidence: float | None = None


class BatchVerifyResponse(BaseModel):
    total: int
    processed: int
    matched: int
    verified: int
    failed: int
    results: list[BatchVerifyItemResult]

from pydantic import BaseModel, Field


class ImportItemResult(BaseModel):
    """Base result for a single imported item."""
    status: str = Field(..., description="Result status")
    error: str | None = Field(default=None, description="Error message if failed")


class ImportSummary(BaseModel):
    """Summary of a bulk import operation."""
    total: int
    created: int
    skipped: int
    failed: int


class ImportTypeLimit(BaseModel):
    """Configuration for a single import type."""
    import_type: str
    max_items: int


class ImportStatusResponse(BaseModel):
    """Response for the import status endpoint."""
    import_types: list[ImportTypeLimit]

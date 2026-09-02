from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ImportAuditLogCreate(BaseModel):
    """Internal schema for creating an audit log entry."""
    import_type: str
    operation: str
    total_rows: int = 0


class ImportAuditLogSummary(BaseModel):
    """Summary fields for list views."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_type: str
    operation: str
    status: str
    total_rows: int
    successful_rows: int
    skipped_rows: int
    failed_rows: int
    started_at: datetime
    completed_at: datetime | None = None


class ImportAuditLogDetail(BaseModel):
    """Full detail for a single audit log entry."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_type: str
    operation: str
    status: str
    total_rows: int
    successful_rows: int
    skipped_rows: int
    failed_rows: int
    error_summary: str | None = None
    actor: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class ImportAuditLogListResponse(BaseModel):
    """Paginated list of audit logs."""
    items: list[ImportAuditLogSummary]
    total: int
    page: int
    page_size: int

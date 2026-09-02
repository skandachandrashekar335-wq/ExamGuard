from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.import_audit_log import (
    ImportAuditLogDetail,
    ImportAuditLogListResponse,
    ImportAuditLogSummary,
)
from app.services import import_audit_log as audit_service

router = APIRouter(prefix="/import", tags=["Import"])


@router.get(
    "/audit",
    response_model=ImportAuditLogListResponse,
    summary="List import audit logs with optional filters",
)
def list_audit_logs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    import_type: str | None = Query(
        None, description="Filter by import type"
    ),
    status: str | None = Query(
        None, description="Filter by status"
    ),
    db: Session = Depends(get_db),
):
    result = audit_service.list_audit_logs(
        db,
        page=page,
        page_size=page_size,
        import_type=import_type,
        status=status,
    )
    return ImportAuditLogListResponse(
        items=[ImportAuditLogSummary.model_validate(log) for log in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get(
    "/audit/{audit_id}",
    response_model=ImportAuditLogDetail,
    summary="Get import audit log detail",
)
def get_audit_log(
    audit_id: int,
    db: Session = Depends(get_db),
):
    log = audit_service.get_audit_log(db, audit_id)
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return ImportAuditLogDetail.model_validate(log)

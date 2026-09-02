import logging
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.import_audit_log import (
    ImportAuditLog,
    ImportAuditStatus,
)
from app.schemas.import_audit_log import ImportAuditLogCreate

logger = logging.getLogger(__name__)

MAX_ERROR_SUMMARY_LENGTH = 2000


def create_audit_log(
    db: Session, data: ImportAuditLogCreate
) -> ImportAuditLog:
    log = ImportAuditLog(
        import_type=data.import_type,
        operation=data.operation,
        status=ImportAuditStatus.STARTED.value,
        total_rows=data.total_rows,
        successful_rows=0,
        skipped_rows=0,
        failed_rows=0,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def complete_audit_log(
    db: Session,
    audit_log_id: int,
    *,
    successful: int,
    skipped: int,
    failed: int,
    error_summary: str | None = None,
) -> ImportAuditLog | None:
    log = db.query(ImportAuditLog).filter(ImportAuditLog.id == audit_log_id).first()
    if not log:
        logger.warning("Audit log %s not found for completion", audit_log_id)
        return None

    log.successful_rows = successful
    log.skipped_rows = skipped
    log.failed_rows = failed
    log.completed_at = datetime.now(timezone.utc)

    if failed > 0 and (successful > 0 or skipped > 0):
        log.status = ImportAuditStatus.COMPLETED_WITH_ERRORS.value
    elif failed > 0:
        log.status = ImportAuditStatus.FAILED.value
    else:
        log.status = ImportAuditStatus.COMPLETED.value

    if error_summary:
        log.error_summary = error_summary[:MAX_ERROR_SUMMARY_LENGTH]

    db.commit()
    db.refresh(log)
    return log


def fail_audit_log(
    db: Session,
    audit_log_id: int,
    error_summary: str | None = None,
) -> ImportAuditLog | None:
    log = db.query(ImportAuditLog).filter(ImportAuditLog.id == audit_log_id).first()
    if not log:
        return None

    log.status = ImportAuditStatus.FAILED.value
    log.completed_at = datetime.now(timezone.utc)
    if error_summary:
        log.error_summary = error_summary[:MAX_ERROR_SUMMARY_LENGTH]

    db.commit()
    db.refresh(log)
    return log


def list_audit_logs(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    import_type: str | None = None,
    status: str | None = None,
) -> dict:
    query = db.query(ImportAuditLog)

    if import_type:
        query = query.filter(ImportAuditLog.import_type == import_type)
    if status:
        query = query.filter(ImportAuditLog.status == status)

    total = query.count()
    items = (
        query.order_by(desc(ImportAuditLog.started_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_audit_log(
    db: Session, audit_log_id: int
) -> ImportAuditLog | None:
    return (
        db.query(ImportAuditLog)
        .filter(ImportAuditLog.id == audit_log_id)
        .first()
    )

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.import_registrations import (
    BulkCancelRequest,
    BulkCancelResponse,
    BulkRegistrationRequest,
    BulkRegistrationResponse,
)
from app.services import import_registrations as import_service

router = APIRouter(prefix="/import", tags=["Import"])


@router.post(
    "/registrations",
    response_model=BulkRegistrationResponse,
    status_code=201,
    summary="Bulk register students for an exam",
)
def bulk_register_students(
    data: BulkRegistrationRequest,
    db: Session = Depends(get_db),
):
    return import_service.bulk_register(db, data.exam_id, data.student_ids)


@router.post(
    "/registrations/cancel",
    response_model=BulkCancelResponse,
    status_code=200,
    summary="Bulk cancel registrations",
)
def bulk_cancel_registrations(
    data: BulkCancelRequest,
    db: Session = Depends(get_db),
):
    return import_service.bulk_cancel(db, data.registration_ids)

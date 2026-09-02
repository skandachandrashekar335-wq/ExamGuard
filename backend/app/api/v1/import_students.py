from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.import_students import (
    ImportStudentRequest,
    ImportStudentResponse,
)
from app.services import import_students as import_service

router = APIRouter(prefix="/import", tags=["Import"])


@router.post(
    "/students",
    response_model=ImportStudentResponse,
    status_code=201,
    summary="Bulk import students",
)
def bulk_import_students(
    data: ImportStudentRequest,
    db: Session = Depends(get_db),
):
    return import_service.import_students(db, data.students)

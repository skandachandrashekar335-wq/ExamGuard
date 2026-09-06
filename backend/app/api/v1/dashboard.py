from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_role
from app.core.database import get_db
from app.schemas.dashboard import ExamDashboardResponse
from app.services import dashboard

router = APIRouter(prefix="/exams", tags=["Exams"])


@router.get(
    "/{exam_id}/dashboard",
    response_model=ExamDashboardResponse,
    summary="Get verification dashboard for an exam",
)
def get_exam_dashboard(exam_id: int, db: Session = Depends(get_db),
                       _: dict = Depends(require_role(["OPERATOR"]))):
    try:
        data = dashboard.get_exam_dashboard(db, exam_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return ExamDashboardResponse(**data)

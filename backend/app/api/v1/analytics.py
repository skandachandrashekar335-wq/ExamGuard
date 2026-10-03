"""Analytics API routes.

Provides REST endpoints for all analytics services.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import (
    Role,
    require_role,
    get_invigilator_scope,
    check_invigilator_scope,
    constrain_scope_filters,
)
from app.core.database import SessionLocal
from app.models.document import Document
from app.services.analytics.attendance import (
    get_exam_summary,
    list_attendance,
    list_excused_attendance,
    attendance_timeline,
    attendance_status_timeline,
    export_exam_attendance,
)
from app.services.analytics.verification import (
    get_verification_summary,
    get_exam_verification_distribution,
    get_ocr_confidence_distribution,
    get_match_status_distribution,
    get_decision_trend,
    export_document_verification,
)
from app.services.analytics.proxy_risk import (
    get_signal_type_counts,
    get_signal_strength_distribution,
    get_risk_level_distribution,
    get_average_risk_score,
    get_signal_breakdown_by_type,
    export_exam_proxy_risk,
)
from app.services.analytics.hall_utilization import (
    get_exam_hall_utilization,
    export_exam_hall_utilization,
)
from app.services.analytics.exam_statistics import (
    get_exam_statistics,
    list_exam_statistics,
    get_department_statistics,
    export_exam_report,
)

from app.models.exam import Exam

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _scoped_exam_id(db: Session, _user: dict, exam_id: int | None) -> int | None:
    """Narrow an analytics exam filter to the caller's assignment scope."""
    return constrain_scope_filters(
        get_invigilator_scope(_user, db), exam_id=exam_id
    )[0]


def _enforce_document_scope(db: Session, _user: dict, document_id: int) -> None:
    """Restrict document analytics to the caller's assigned exam scope."""
    scope = get_invigilator_scope(_user, db)
    if scope is None:
        return
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.exam_id is None:
        raise HTTPException(
            status_code=403,
            detail="Access denied: document is outside your assigned exam",
        )
    check_invigilator_scope(scope, resource_exam_id=document.exam_id)


@router.get("/attendance/summary/{exam_id}", response_model=dict)
def analytics_attendance_summary(
    exam_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get attendance summary for an exam."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return get_exam_summary(db, exam_id)


@router.get("/attendance/list", response_model=dict)
def analytics_attendance_list(
    exam_id: int = Query(...),
    hall_id: int | None = Query(None),
    status: str | None = Query(None),
    student_id: int | None = Query(None),
    page: int = Query(1),
    page_size: int = Query(20),
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """List attendance records for an exam with filters."""
    exam_id, hall_id = constrain_scope_filters(
        get_invigilator_scope(_user, db), exam_id, hall_id
    )
    return list_attendance(db, exam_id, hall_id=hall_id, status=status,
                          student_id=student_id, page=page, page_size=page_size)


@router.get("/attendance/excused/{exam_id}", response_model=dict)
def analytics_attendance_excused(
    exam_id: int,
    page: int = Query(1),
    page_size: int = Query(20),
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """List excused attendance records for an exam."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return list_excused_attendance(db, exam_id, page=page, page_size=page_size)


@router.get("/attendance/timeline/{exam_id}", response_model=dict)
def analytics_attendance_timeline(
    exam_id: int,
    days: int = Query(30),
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get attendance timeline for an exam."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return attendance_timeline(db, exam_id, days=days)


@router.get("/attendance/status-timeline/{exam_id}", response_model=dict)
def analytics_attendance_status_timeline(
    exam_id: int,
    days: int = Query(30),
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get present/excused/absent breakdown by date."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return attendance_status_timeline(db, exam_id, days=days)


@router.get("/attendance/export/{exam_id}", response_model=dict)
def analytics_attendance_export(
    exam_id: int,
    status: str | None = Query(None),
    hall_id: int | None = Query(None),
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Export attendance data for an exam."""
    exam_id, hall_id = constrain_scope_filters(
        get_invigilator_scope(_user, db), exam_id, hall_id
    )
    return export_exam_attendance(db, exam_id, status=status, hall_id=hall_id)


@router.get("/verification/summary/{document_id}", response_model=dict)
def analytics_verification_summary(
    document_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get verification summary for a document."""
    _enforce_document_scope(db, _user, document_id)
    return get_verification_summary(db, document_id)


@router.get("/verification/distribution/{exam_id}", response_model=dict)
def analytics_verification_distribution(
    exam_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get verification decision distribution for an exam."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return get_exam_verification_distribution(db, exam_id)


@router.get("/verification/ocr-distribution/{exam_id}", response_model=dict)
def analytics_ocr_confidence_distribution(
    exam_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get OCR confidence distribution for an exam."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return get_ocr_confidence_distribution(db, exam_id)


@router.get("/verification/match-distribution/{exam_id}", response_model=dict)
def analytics_match_status_distribution(
    exam_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get hall-ticket match status distribution for an exam."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return get_match_status_distribution(db, exam_id)


@router.get("/verification/decision-trend", response_model=dict)
def analytics_decision_trend(
    exam_id: int | None = Query(None),
    days: int = Query(30),
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get verification decision trend over time."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return get_decision_trend(db, exam_id, days=days)


@router.get("/verification/export/{document_id}", response_model=dict)
def analytics_verification_export(
    document_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Export verification data for a document."""
    _enforce_document_scope(db, _user, document_id)
    return export_document_verification(db, document_id)


@router.get("/proxy-risk/average/{exam_id}", response_model=dict)
def analytics_proxy_risk_average(
    exam_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get average risk score for an exam."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return get_average_risk_score(db, exam_id)


@router.get("/proxy-risk/signal-types/{exam_id}", response_model=dict)
def analytics_proxy_risk_signal_types(
    exam_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get signal type counts for an exam."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return get_signal_type_counts(db, exam_id)


@router.get("/proxy-risk/strength-distribution/{exam_id}", response_model=dict)
def analytics_proxy_risk_strength_distribution(
    exam_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get signal strength distribution for an exam."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return get_signal_strength_distribution(db, exam_id)


@router.get("/proxy-risk/risk-levels/{exam_id}", response_model=dict)
def analytics_proxy_risk_risk_levels(
    exam_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get risk level distribution for an exam."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return get_risk_level_distribution(db, exam_id)


@router.get("/proxy-risk/breakdown/{exam_id}", response_model=dict)
def analytics_proxy_risk_breakdown(
    exam_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get per-signal-type breakdown for an exam."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return get_signal_breakdown_by_type(db, exam_id)


@router.get("/proxy-risk/export/{exam_id}", response_model=dict)
def analytics_proxy_risk_export(
    exam_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Export proxy risk data for an exam."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return export_exam_proxy_risk(db, exam_id)


@router.get("/hall-utilization/{exam_id}", response_model=dict)
def analytics_hall_utilization(
    exam_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get hall utilization for an exam."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return get_exam_hall_utilization(db, exam_id)


@router.get("/hall-utilization/export/{exam_id}", response_model=dict)
def analytics_hall_utilization_export(
    exam_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Export hall utilization data for an exam."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    return export_exam_hall_utilization(db, exam_id)


@router.get("/statistics/{exam_id}", response_model=dict)
def analytics_exam_statistics(
    exam_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get comprehensive examination statistics."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return get_exam_statistics(db, exam_id)


@router.get("/statistics/list", response_model=dict)
def analytics_exam_statistics_list(
    hall_id: int | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """List examination statistics with filters."""
    if get_invigilator_scope(_user, db) is not None:
        raise HTTPException(
            status_code=403,
            detail="Access denied: restricted to your assigned exam",
        )
    return list_exam_statistics(db, hall_id=hall_id, status=status)


@router.get("/statistics/department", response_model=dict)
def analytics_department_statistics(
    department_filter: str | None = Query(None),
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get department-level statistics across exams."""
    if get_invigilator_scope(_user, db) is not None:
        raise HTTPException(
            status_code=403,
            detail="Access denied: restricted to your assigned exam",
        )
    return get_department_statistics(db, department_filter=department_filter)


@router.get("/statistics/report/{exam_id}", response_model=dict)
def analytics_exam_report(
    exam_id: int,
    db: Session = Depends(SessionLocal),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    """Get comprehensive examination report."""
    exam_id = _scoped_exam_id(db, _user, exam_id)
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return export_exam_report(db, exam_id)
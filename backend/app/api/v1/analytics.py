"""Analytics API routes.

Provides REST endpoints for all analytics services.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
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


@router.get("/attendance/summary/{exam_id}", response_model=dict)
def analytics_attendance_summary(
    exam_id: int,
    db: Session = Depends(SessionLocal),
):
    """Get attendance summary for an exam."""
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
):
    """List attendance records for an exam with filters."""
    return list_attendance(db, exam_id, hall_id=hall_id, status=status,
                          student_id=student_id, page=page, page_size=page_size)


@router.get("/attendance/excused/{exam_id}", response_model=dict)
def analytics_attendance_excused(
    exam_id: int,
    page: int = Query(1),
    page_size: int = Query(20),
    db: Session = Depends(SessionLocal),
):
    """List excused attendance records for an exam."""
    return list_excused_attendance(db, exam_id, page=page, page_size=page_size)


@router.get("/attendance/timeline/{exam_id}", response_model=dict)
def analytics_attendance_timeline(
    exam_id: int,
    days: int = Query(30),
    db: Session = Depends(SessionLocal),
):
    """Get attendance timeline for an exam."""
    return attendance_timeline(db, exam_id, days=days)


@router.get("/attendance/status-timeline/{exam_id}", response_model=dict)
def analytics_attendance_status_timeline(
    exam_id: int,
    days: int = Query(30),
    db: Session = Depends(SessionLocal),
):
    """Get present/excused/absent breakdown by date."""
    return attendance_status_timeline(db, exam_id, days=days)


@router.get("/attendance/export/{exam_id}", response_model=dict)
def analytics_attendance_export(
    exam_id: int,
    status: str | None = Query(None),
    hall_id: int | None = Query(None),
    db: Session = Depends(SessionLocal),
):
    """Export attendance data for an exam."""
    return export_exam_attendance(db, exam_id, status=status, hall_id=hall_id)


@router.get("/verification/summary/{document_id}", response_model=dict)
def analytics_verification_summary(
    document_id: int,
    db: Session = Depends(SessionLocal),
):
    """Get verification summary for a document."""
    return get_verification_summary(db, document_id)


@router.get("/verification/distribution/{exam_id}", response_model=dict)
def analytics_verification_distribution(
    exam_id: int,
    db: Session = Depends(SessionLocal),
):
    """Get verification decision distribution for an exam."""
    return get_exam_verification_distribution(db, exam_id)


@router.get("/verification/ocr-distribution/{exam_id}", response_model=dict)
def analytics_ocr_confidence_distribution(
    exam_id: int,
    db: Session = Depends(SessionLocal),
):
    """Get OCR confidence distribution for an exam."""
    return get_ocr_confidence_distribution(db, exam_id)


@router.get("/verification/match-distribution/{exam_id}", response_model=dict)
def analytics_match_status_distribution(
    exam_id: int,
    db: Session = Depends(SessionLocal),
):
    """Get hall-ticket match status distribution for an exam."""
    return get_match_status_distribution(db, exam_id)


@router.get("/verification/decision-trend", response_model=dict)
def analytics_decision_trend(
    exam_id: int | None = Query(None),
    days: int = Query(30),
    db: Session = Depends(SessionLocal),
):
    """Get verification decision trend over time."""
    return get_decision_trend(db, exam_id, days=days)


@router.get("/verification/export/{document_id}", response_model=dict)
def analytics_verification_export(
    document_id: int,
    db: Session = Depends(SessionLocal),
):
    """Export verification data for a document."""
    return export_document_verification(db, document_id)


@router.get("/proxy-risk/average/{exam_id}", response_model=dict)
def analytics_proxy_risk_average(
    exam_id: int,
    db: Session = Depends(SessionLocal),
):
    """Get average risk score for an exam."""
    return get_average_risk_score(db, exam_id)


@router.get("/proxy-risk/signal-types/{exam_id}", response_model=dict)
def analytics_proxy_risk_signal_types(
    exam_id: int,
    db: Session = Depends(SessionLocal),
):
    """Get signal type counts for an exam."""
    return get_signal_type_counts(db, exam_id)


@router.get("/proxy-risk/strength-distribution/{exam_id}", response_model=dict)
def analytics_proxy_risk_strength_distribution(
    exam_id: int,
    db: Session = Depends(SessionLocal),
):
    """Get signal strength distribution for an exam."""
    return get_signal_strength_distribution(db, exam_id)


@router.get("/proxy-risk/risk-levels/{exam_id}", response_model=dict)
def analytics_proxy_risk_risk_levels(
    exam_id: int,
    db: Session = Depends(SessionLocal),
):
    """Get risk level distribution for an exam."""
    return get_risk_level_distribution(db, exam_id)


@router.get("/proxy-risk/breakdown/{exam_id}", response_model=dict)
def analytics_proxy_risk_breakdown(
    exam_id: int,
    db: Session = Depends(SessionLocal),
):
    """Get per-signal-type breakdown for an exam."""
    return get_signal_breakdown_by_type(db, exam_id)


@router.get("/proxy-risk/export/{exam_id}", response_model=dict)
def analytics_proxy_risk_export(
    exam_id: int,
    db: Session = Depends(SessionLocal),
):
    """Export proxy risk data for an exam."""
    return export_exam_proxy_risk(db, exam_id)


@router.get("/hall-utilization/{exam_id}", response_model=dict)
def analytics_hall_utilization(
    exam_id: int,
    db: Session = Depends(SessionLocal),
):
    """Get hall utilization for an exam."""
    return get_exam_hall_utilization(db, exam_id)


@router.get("/hall-utilization/export/{exam_id}", response_model=dict)
def analytics_hall_utilization_export(
    exam_id: int,
    db: Session = Depends(SessionLocal),
):
    """Export hall utilization data for an exam."""
    return export_exam_hall_utilization(db, exam_id)


@router.get("/statistics/{exam_id}", response_model=dict)
def analytics_exam_statistics(
    exam_id: int,
    db: Session = Depends(SessionLocal),
):
    """Get comprehensive examination statistics."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return get_exam_statistics(db, exam_id)


@router.get("/statistics/list", response_model=dict)
def analytics_exam_statistics_list(
    hall_id: int | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(SessionLocal),
):
    """List examination statistics with filters."""
    return list_exam_statistics(db, hall_id=hall_id, status=status)


@router.get("/statistics/department", response_model=dict)
def analytics_department_statistics(
    department_filter: str | None = Query(None),
    db: Session = Depends(SessionLocal),
):
    """Get department-level statistics across exams."""
    return get_department_statistics(db, department_filter=department_filter)


@router.get("/statistics/report/{exam_id}", response_model=dict)
def analytics_exam_report(
    exam_id: int,
    db: Session = Depends(SessionLocal),
):
    """Get comprehensive examination report."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return export_exam_report(db, exam_id)
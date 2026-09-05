"""Proxy risk assessment REST API (Phase 11.4).

Thin API layer exposing signal detection and risk assessment through
existing service functions. No scoring or detection logic in routers.

Phase 11 remains ADVISORY. These endpoints do NOT:
- mutate EntryVerification status
- automatically escalate EntryVerification
- grant/deny entry
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entry_verification import EntryVerification
from app.models.proxy_risk import ProxyRiskAssessment, SecuritySignal
from app.schemas.proxy_risk import (
    ProxyRiskAssessmentListResponse,
    ProxyRiskAssessmentResponse,
    SecuritySignalListResponse,
    SecuritySignalResponse,
)
from app.services import proxy_risk
from app.services.signal_detection import detect_signals

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/entry-verifications",
    tags=["Proxy Risk Assessment"],
)


def _get_entry_verification_or_404(
    db: Session, entry_verification_id: int
) -> EntryVerification:
    """Look up entry verification or raise 404."""
    ev = db.query(EntryVerification).filter(
        EntryVerification.id == entry_verification_id
    ).first()
    if ev is None:
        raise HTTPException(
            status_code=404,
            detail=f"Entry verification {entry_verification_id} not found",
        )
    return ev


def _parse_signals_summary(signals_summary_json: str | None) -> dict | None:
    """Parse signals_summary_json and extract audit fields."""
    if not signals_summary_json:
        return None
    try:
        return json.loads(signals_summary_json)
    except (json.JSONDecodeError, TypeError):
        return None


def _assessment_to_response(
    assessment: ProxyRiskAssessment,
) -> ProxyRiskAssessmentResponse:
    """Convert ProxyRiskAssessment model to response schema with audit fields."""
    summary = _parse_signals_summary(assessment.signals_summary_json)
    return ProxyRiskAssessmentResponse(
        id=assessment.id,
        entry_verification_id=assessment.entry_verification_id,
        risk_level=assessment.risk_level,
        risk_score=assessment.risk_score,
        signal_count=summary.get("signal_count") if summary else None,
        strong_signal_count=summary.get("strong_signal_count") if summary else None,
        explanation=summary.get("explanation") if summary else None,
        policy_version=assessment.policy_version,
        assessed_at=assessment.assessed_at,
    )


# ---------------------------------------------------------------------------
# 1. Detect signals
# ---------------------------------------------------------------------------


@router.post(
    "/{entry_verification_id}/risk/signals/detect",
    response_model=list[SecuritySignalResponse],
    status_code=201,
    summary="Detect security signals for an entry verification",
)
def detect_security_signals(
    entry_verification_id: int,
    db: Session = Depends(get_db),
):
    """Run deterministic signal detection for an entry verification.

    Idempotent — calling twice does not produce duplicate signals.
    Does not modify EntryVerification authorization state.
    """
    _get_entry_verification_or_404(db, entry_verification_id)
    try:
        new_signals = detect_signals(db, entry_verification_id)
        if new_signals:
            db.commit()
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Signal detection failed for entry_verification %d", entry_verification_id)
        raise HTTPException(
            status_code=500,
            detail="Signal detection failed due to an internal error",
        )
    return new_signals


# ---------------------------------------------------------------------------
# 2. List security signals
# ---------------------------------------------------------------------------


@router.get(
    "/{entry_verification_id}/risk/signals",
    response_model=SecuritySignalListResponse,
    summary="List security signals for an entry verification",
)
def list_security_signals(
    entry_verification_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """Return security signals for an entry verification with pagination."""
    _get_entry_verification_or_404(db, entry_verification_id)

    query = (
        db.query(SecuritySignal)
        .filter(SecuritySignal.entry_verification_id == entry_verification_id)
        .order_by(SecuritySignal.id)
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return SecuritySignalListResponse(
        items=[
            SecuritySignalResponse(
                id=s.id,
                entry_verification_id=s.entry_verification_id,
                signal_type=s.signal_type,
                strength=s.strength,
                source=s.source,
                description=s.description,
                created_at=s.created_at,
            )
            for s in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# 3. Assess risk
# ---------------------------------------------------------------------------


@router.post(
    "/{entry_verification_id}/risk/assess",
    response_model=ProxyRiskAssessmentResponse,
    status_code=201,
    summary="Assess proxy risk for an entry verification",
)
def assess_risk(
    entry_verification_id: int,
    db: Session = Depends(get_db),
):
    """Create a new historical ProxyRiskAssessment for an entry verification.

    Each call creates a separate historical record (append-only).
    Does not modify EntryVerification authorization state.
    """
    _get_entry_verification_or_404(db, entry_verification_id)
    try:
        assessment = proxy_risk.assess_entry_verification(db, entry_verification_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        logger.exception("Risk assessment failed for entry_verification %d", entry_verification_id)
        raise HTTPException(
            status_code=500,
            detail="Risk assessment failed due to an internal error",
        )
    return _assessment_to_response(assessment)


# ---------------------------------------------------------------------------
# 4. List historical risk assessments
# ---------------------------------------------------------------------------


@router.get(
    "/{entry_verification_id}/risk/assessments",
    response_model=ProxyRiskAssessmentListResponse,
    summary="List historical risk assessments",
)
def list_risk_assessments(
    entry_verification_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """Return historical risk assessments in chronological order."""
    _get_entry_verification_or_404(db, entry_verification_id)

    query = (
        db.query(ProxyRiskAssessment)
        .filter(ProxyRiskAssessment.entry_verification_id == entry_verification_id)
        .order_by(ProxyRiskAssessment.id)
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return ProxyRiskAssessmentListResponse(
        items=[_assessment_to_response(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# 5. Get latest assessment
# ---------------------------------------------------------------------------


@router.get(
    "/{entry_verification_id}/risk",
    response_model=ProxyRiskAssessmentResponse,
    summary="Get the latest risk assessment",
)
def get_latest_risk_assessment(
    entry_verification_id: int,
    db: Session = Depends(get_db),
):
    """Return the most recent persisted risk assessment.

    Returns 404 if no assessment exists — does not manufacture a result.
    """
    _get_entry_verification_or_404(db, entry_verification_id)

    assessment = (
        db.query(ProxyRiskAssessment)
        .filter(ProxyRiskAssessment.entry_verification_id == entry_verification_id)
        .order_by(ProxyRiskAssessment.id.desc())
        .first()
    )
    if assessment is None:
        raise HTTPException(
            status_code=404,
            detail="No risk assessment found for this entry verification",
        )
    return _assessment_to_response(assessment)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.camera_health import HealthObservationCreate, HealthResponse
from app.services import camera_health

router = APIRouter(prefix="/cameras", tags=["Camera Health"])


@router.get(
    "/{camera_id}/health",
    response_model=HealthResponse,
    summary="Get camera health status",
)
def get_camera_health(camera_id: int, db: Session = Depends(get_db)):
    camera = camera_health.get_camera_health(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return HealthResponse(
        camera_id=camera.id,
        status=camera.status,
        last_seen_at=camera.last_seen_at,
        last_health_check_at=camera.last_health_check_at,
        health_reason=camera.health_reason,
        is_active=camera.is_active,
    )


@router.post(
    "/{camera_id}/health-observations",
    response_model=HealthResponse,
    status_code=201,
    summary="Record a health observation for a camera",
)
def record_health_observation(
    camera_id: int,
    data: HealthObservationCreate,
    db: Session = Depends(get_db),
):
    try:
        camera = camera_health.record_health_observation(
            db,
            camera_id,
            data.status,
            observed_at=data.observed_at,
            reason=data.reason,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return HealthResponse(
        camera_id=camera.id,
        status=camera.status,
        last_seen_at=camera.last_seen_at,
        last_health_check_at=camera.last_health_check_at,
        health_reason=camera.health_reason,
        is_active=camera.is_active,
    )

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.camera_health import HealthObservationCreate, HealthResponse
from app.services import camera_health
from app.services.monitoring.publisher import publish_camera_offline, publish_camera_online

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
        # Capture previous status before the observation
        from app.models.camera import Camera
        existing = db.query(Camera).filter(Camera.id == camera_id).first()
        previous_status = existing.status if existing else None

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

    # Publish camera status event after successful commit
    if data.status.strip().upper() == "ONLINE":
        publish_camera_online(
            camera_id=camera_id,
            previous_status=previous_status,
        )
    elif data.status.strip().upper() == "OFFLINE":
        publish_camera_offline(
            camera_id=camera_id,
            reason=data.reason,
            previous_status=previous_status,
        )

    return HealthResponse(
        camera_id=camera.id,
        status=camera.status,
        last_seen_at=camera.last_seen_at,
        last_health_check_at=camera.last_health_check_at,
        health_reason=camera.health_reason,
        is_active=camera.is_active,
    )

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.camera import Camera, CameraStatus, HealthReason

VALID_OBSERVATION_STATUSES = {CameraStatus.ONLINE.value, CameraStatus.OFFLINE.value}
VALID_REASONS = {r.value for r in HealthReason}


def record_health_observation(
    db: Session,
    camera_id: int,
    status: str,
    *,
    observed_at: datetime | None = None,
    reason: str | None = None,
) -> Camera:
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise LookupError(f"Camera with id {camera_id} not found")

    if not camera.is_active:
        raise ValueError(
            f"Cannot record health observation for inactive camera {camera_id}"
        )

    status = status.strip().upper()
    if status not in VALID_OBSERVATION_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_OBSERVATION_STATUSES))}"
        )

    if reason is not None:
        reason = reason.strip().upper()
        if reason not in VALID_REASONS:
            raise ValueError(
                f"Invalid reason '{reason}'. Must be one of: {', '.join(sorted(VALID_REASONS))}"
            )

    now = datetime.now(timezone.utc)
    observation_time = observed_at if observed_at is not None else now

    if observation_time.tzinfo is None:
        observation_time = observation_time.replace(tzinfo=timezone.utc)

    if observation_time > now:
        raise ValueError("observed_at must not be in the future")

    camera.status = status
    camera.last_health_check_at = now
    camera.health_reason = reason

    if status == CameraStatus.ONLINE.value:
        camera.last_seen_at = observation_time

    db.commit()
    db.refresh(camera)
    return camera


def get_camera_health(db: Session, camera_id: int) -> Camera | None:
    return db.query(Camera).filter(Camera.id == camera_id).first()

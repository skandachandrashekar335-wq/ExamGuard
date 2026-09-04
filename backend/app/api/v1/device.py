"""Device communication API endpoint.

Provides a secure, authenticated endpoint for physical cameras/devices
to report health status to ExamGuard. The device authenticates via
a credential in the X-Device-Credential header. The camera identity
is derived from the authenticated credential.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.device_credential import (
    DeviceCredentialCreate,
    DeviceCredentialProvisionResponse,
    DeviceCredentialResponse,
    DeviceHealthRequest,
    DeviceHealthResponse,
)
from app.services import camera_health, device_credential

router = APIRouter(prefix="/device", tags=["Device Communication"])


@router.post(
    "/credentials",
    response_model=DeviceCredentialProvisionResponse,
    status_code=201,
    summary="Provision a new device credential",
)
def provision_credential(
    data: DeviceCredentialCreate,
    db: Session = Depends(get_db),
):
    """Provision a new device credential for a camera.

    Returns the raw secret ONCE. The caller must securely transmit
    the secret to the device operator. The raw secret is never
    returned again.
    """
    try:
        credential, raw_secret = device_credential.create_device_credential(
            db, data.camera_id, data.label
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return DeviceCredentialProvisionResponse(
        id=credential.id,
        camera_id=credential.camera_id,
        label=credential.label,
        secret=raw_secret,
        secret_prefix=credential.secret_prefix,
        status=credential.status,
        created_at=credential.created_at,
    )


@router.get(
    "/credentials",
    response_model=list[DeviceCredentialResponse],
    summary="List credentials for a camera",
)
def list_credentials(
    camera_id: int,
    db: Session = Depends(get_db),
):
    """List all credentials for a camera (without secrets)."""
    return device_credential.list_device_credentials(db, camera_id)


@router.get(
    "/credentials/{credential_id}",
    response_model=DeviceCredentialResponse,
    summary="Get a device credential",
)
def get_credential(
    credential_id: int,
    db: Session = Depends(get_db),
):
    """Get a device credential by ID (without secret)."""
    credential = device_credential.get_device_credential(db, credential_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Device credential not found")
    return credential


@router.post(
    "/credentials/{credential_id}/revoke",
    response_model=DeviceCredentialResponse,
    summary="Revoke a device credential",
)
def revoke_credential(
    credential_id: int,
    db: Session = Depends(get_db),
):
    """Revoke a device credential. The credential can no longer be used."""
    try:
        credential = device_credential.revoke_device_credential(db, credential_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return credential


@router.post(
    "/health",
    response_model=DeviceHealthResponse,
    status_code=201,
    summary="Device health heartbeat",
)
def device_health(
    data: DeviceHealthRequest,
    x_device_credential: str = Header(
        ...,
        description="Device authentication credential",
    ),
    db: Session = Depends(get_db),
):
    """Device health heartbeat endpoint.

    Authenticates the device via the X-Device-Credential header.
    The camera identity is derived from the authenticated credential.
    Calls record_health_observation() to update camera status.
    """
    try:
        credential = device_credential.authenticate_device(db, x_device_credential)
    except LookupError as e:
        raise HTTPException(status_code=401, detail="Invalid device credential")
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    try:
        camera = camera_health.record_health_observation(
            db,
            credential.camera_id,
            data.status,
            observed_at=data.observed_at,
            reason=data.reason,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return DeviceHealthResponse(
        camera_id=camera.id,
        status=camera.status,
        last_seen_at=camera.last_seen_at,
        last_health_check_at=camera.last_health_check_at,
        health_reason=camera.health_reason,
        is_active=camera.is_active,
    )

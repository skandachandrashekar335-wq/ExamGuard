"""Device credential service for secure camera-to-ExamGuard communication.

Provides secure credential provisioning, authentication, and revocation.
Secrets are hashed with SHA-256 before storage. Raw secrets are only
returned once at provisioning time.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.camera import Camera, CameraStatus
from app.models.camera_device_credential import CameraDeviceCredential, CredentialStatus


def _hash_secret(secret: str) -> str:
    """Hash a secret using SHA-256."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _generate_secret() -> str:
    """Generate a secure random secret (32 bytes = 64 hex chars)."""
    return secrets.token_hex(32)


def _constant_time_compare(val1: str, val2: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    return hmac.compare_digest(val1.encode("utf-8"), val2.encode("utf-8"))


def create_device_credential(
    db: Session,
    camera_id: int,
    label: str,
) -> tuple[CameraDeviceCredential, str]:
    """Provision a new device credential for a camera.

    Returns the credential object and the raw secret (shown once).
    The raw secret must be securely transmitted to the device operator.
    """
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise LookupError(f"Camera with id {camera_id} not found")

    if not camera.is_active:
        raise ValueError(
            f"Cannot create credential for inactive camera {camera_id}"
        )

    raw_secret = _generate_secret()
    secret_hash = _hash_secret(raw_secret)
    secret_prefix = raw_secret[:8]

    credential = CameraDeviceCredential(
        camera_id=camera_id,
        label=label.strip(),
        secret_hash=secret_hash,
        secret_prefix=secret_prefix,
        status=CredentialStatus.ACTIVE.value,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)

    return credential, raw_secret


def authenticate_device(
    db: Session,
    secret: str,
) -> CameraDeviceCredential:
    """Authenticate a device credential and return the credential if valid.

    Raises LookupError if credential not found or invalid.
    Raises ValueError if credential is revoked or camera inactive.
    """
    if not secret or not secret.strip():
        raise LookupError("Invalid device credential")

    secret = secret.strip()
    secret_hash = _hash_secret(secret)

    credentials = db.query(CameraDeviceCredential).all()

    for credential in credentials:
        if _constant_time_compare(credential.secret_hash, secret_hash):
            if credential.status == CredentialStatus.REVOKED.value:
                raise ValueError("Device credential has been revoked")

            if not credential.is_active:
                raise ValueError("Device credential is inactive")

            camera = db.query(Camera).filter(Camera.id == credential.camera_id).first()
            if not camera:
                raise LookupError("Camera associated with credential not found")

            if not camera.is_active:
                raise ValueError(
                    f"Camera {credential.camera_id} associated with credential is inactive"
                )

            return credential

    raise LookupError("Invalid device credential")


def revoke_device_credential(
    db: Session,
    credential_id: int,
) -> CameraDeviceCredential:
    """Revoke a device credential.

    The credential can no longer be used for authentication after revocation.
    """
    credential = (
        db.query(CameraDeviceCredential)
        .filter(CameraDeviceCredential.id == credential_id)
        .first()
    )
    if not credential:
        raise LookupError(f"Device credential with id {credential_id} not found")

    credential.status = CredentialStatus.REVOKED.value
    db.commit()
    db.refresh(credential)
    return credential


def list_device_credentials(
    db: Session,
    camera_id: int,
) -> list[CameraDeviceCredential]:
    """List all credentials for a camera (without secrets)."""
    return (
        db.query(CameraDeviceCredential)
        .filter(CameraDeviceCredential.camera_id == camera_id)
        .order_by(CameraDeviceCredential.created_at.desc())
        .all()
    )


def get_device_credential(
    db: Session,
    credential_id: int,
) -> CameraDeviceCredential | None:
    """Get a device credential by ID (without secret)."""
    return (
        db.query(CameraDeviceCredential)
        .filter(CameraDeviceCredential.id == credential_id)
        .first()
    )

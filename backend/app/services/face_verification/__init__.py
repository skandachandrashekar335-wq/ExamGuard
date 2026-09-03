"""Face verification provider abstraction.

This module defines the interface between ExamGuard and face
verification providers. The key architectural principle:

    AI/perception = evidence.
    Business logic = authority.

Providers produce evidence signals (similarity scores, liveness
results, quality assessments). The decision engine evaluates
these signals to produce MATCH / NO_MATCH / INCONCLUSIVE decisions.

Providers NEVER directly authorize or deny exam entry.

Usage:
    from app.services.face_verification import (
        FaceVerificationProvider,
        FaceVerificationRequest,
        FaceVerificationResult,
        get_face_verification_provider,
    )

    provider = get_face_verification_provider()
    result = provider.verify(FaceVerificationRequest(
        reference_image=ref_bytes,
        probe_image=probe_bytes,
    ))
    # result.identity_match_score, result.liveness_passed, etc.
    # These are evidence signals — NOT decisions.
"""

from app.services.face_verification.factory import get_face_verification_provider
from app.services.face_verification.protocol import FaceVerificationProvider
from app.services.face_verification.providers.deterministic import (
    DeterministicProvider,
    ProviderUnavailableError,
)
from app.services.face_verification.types import (
    FaceVerificationError,
    FaceVerificationErrorType,
    FaceVerificationRequest,
    FaceVerificationResult,
    ProviderCapabilities,
    ProviderStatus,
)

__all__ = [
    "DeterministicProvider",
    "FaceVerificationError",
    "FaceVerificationErrorType",
    "FaceVerificationProvider",
    "FaceVerificationRequest",
    "FaceVerificationResult",
    "ProviderCapabilities",
    "ProviderStatus",
    "ProviderUnavailableError",
    "get_face_verification_provider",
]

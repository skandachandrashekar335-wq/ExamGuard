"""Data types for face verification provider abstraction.

These types define the contract between ExamGuard and face verification
providers. Providers produce evidence; ExamGuard's decision engine
evaluates that evidence.

AI/perception = evidence.
Business logic = authority.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class FaceVerificationErrorType(str, enum.Enum):
    """Categorizes provider-level failures."""

    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    INVALID_INPUT = "INVALID_INPUT"
    NO_FACE_DETECTED = "NO_FACE_DETECTED"
    MULTIPLE_FACES_DETECTED = "MULTIPLE_FACES_DETECTED"
    LIVENESS_UNAVAILABLE = "LIVENESS_UNAVAILABLE"
    IDENTITY_MATCH_UNAVAILABLE = "IDENTITY_MATCH_UNAVAILABLE"
    PROVIDER_REJECTED = "PROVIDER_REJECTED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class FaceVerificationRequest:
    """Input to a face verification provider.

    Attributes:
        reference_image: Reference/enrollment image bytes (the enrolled student face).
        probe_image: Probe/capture image bytes (the live capture to verify against).
        reference_image_format: MIME type or format of the reference image (e.g. "image/jpeg").
        probe_image_format: MIME type or format of the probe image.
        context: Optional metadata dict for provider-specific context
                 (e.g. student_id, attempt_id for logging — NOT biometric data).
    """

    reference_image: bytes
    probe_image: bytes
    reference_image_format: str = "image/jpeg"
    probe_image_format: str = "image/jpeg"
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FaceVerificationError:
    """Provider-level error (NOT a verification decision).

    A provider error means the provider could not produce evidence.
    This is different from a verification failure (NO_MATCH).
    Provider errors should NOT automatically become DENY unless
    the decision policy explicitly says so.

    Attributes:
        error_type: Category of the error.
        message: Human-readable error description.
        provider_name: Name of the provider that produced this error.
        provider_version: Version of the provider.
        retryable: Whether retrying might succeed.
    """

    error_type: FaceVerificationErrorType
    message: str
    provider_name: str = ""
    provider_version: str = ""
    retryable: bool = False


@dataclass(frozen=True)
class FaceVerificationResult:
    """Output from a face verification provider.

    This is evidence — NOT a decision. The decision engine evaluates
    these signals to produce MATCH / NO_MATCH / INCONCLUSIVE.

    Provider may produce partial results. For example:
    - identity_match_score without liveness (if liveness unavailable)
    - liveness without identity_match_score (if identity match unavailable)
    - Neither (if provider failed to produce usable signals)

    Attributes:
        identity_match_score: Similarity score [0.0, 1.0] between reference and probe.
            None if identity match was not performed or failed.
        liveness_score: Liveness detection score [0.0, 1.0].
            None if liveness detection was not performed or failed.
        liveness_passed: Whether liveness check passed.
            None if liveness was not performed.
        image_quality_score: Quality score [0.0, 1.0] for the probe image.
            None if quality assessment was not performed.
        provider_name: Identifies which provider produced this result.
        provider_version: Version of the provider.
        evidence_metadata: Provider-specific metadata dict.
            Must NOT contain raw images, biometric templates, or
            sensitive provider payloads. Should contain only
            non-sensitive diagnostic information.
    """

    identity_match_score: float | None = None
    liveness_score: float | None = None
    liveness_passed: bool | None = None
    image_quality_score: float | None = None
    provider_name: str = ""
    provider_version: str = ""
    evidence_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderCapabilities:
    """Describes what a provider supports.

    Allows the system to understand provider capabilities without
    making assumptions.

    Attributes:
        supports_liveness: Whether the provider can perform liveness detection.
        supports_identity_match: Whether the provider can perform identity matching.
        supports_image_quality: Whether the provider can assess image quality.
        max_image_size_bytes: Maximum allowed image size. None = no limit.
        supported_formats: List of supported image MIME types.
        provider_name: Human-readable provider name.
        provider_version: Provider version string.
    """

    supports_liveness: bool = False
    supports_identity_match: bool = True
    supports_image_quality: bool = False
    max_image_size_bytes: int | None = None
    supported_formats: tuple[str, ...] = ("image/jpeg",)
    provider_name: str = ""
    provider_version: str = ""


@dataclass(frozen=True)
class ProviderStatus:
    """Health status of a provider.

    Attributes:
        available: Whether the provider is currently available.
        message: Optional status message.
        provider_name: Provider name.
        provider_version: Provider version.
    """

    available: bool = True
    message: str = ""
    provider_name: str = ""
    provider_version: str = ""

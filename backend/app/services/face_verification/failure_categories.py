"""Typed failure categories for the face verification pipeline.

Establishes clear separation between different failure modes so they
are NOT flattened into one generic failure. Each category maps to a
specific decision or domain outcome.

Categories:
    A. INVALID_INPUT — malformed request, bad base64, unsupported format
    B. PROVIDER_UNAVAILABLE — provider cannot produce evidence at all
    C. PROVIDER_TIMEOUT — provider exceeded time limit
    D. PROVIDER_INITIALIZATION — provider failed to load models
    E. NO_FACE_DETECTED — face detection found zero faces
    F. MULTIPLE_FACES — face detection found >1 faces (ambiguous)
    G. RECOGNITION_FAILED — embedding extraction failed
    H. LIVENESS_FAILED — anti-spoofing detected spoof (or failed)
    I. INSUFFICIENT_EVIDENCE — evidence present but not enough for decision
    J. IDENTITY_MISMATCH — evidence indicates different person
    K. POLICY_DECISION — decision engine produced final verdict
    L. HUMAN_OVERRIDE — authorized human overrode automated decision

Architecture:
    INVALID_INPUT → reject request (422)
    PROVIDER_* → verification could not be completed (fail attempt)
    NO_FACE / MULTIPLE_FACES → verification input failure (fail attempt)
    IDENTITY_MISMATCH → actual verification evidence indicates mismatch
    INSUFFICIENT_EVIDENCE → INCONCLUSIVE / review
    POLICY_DECISION → automated decision recorded
    HUMAN_OVERRIDE → authorized override with audit trail
"""

from __future__ import annotations

import enum


class FailureCategory(str, enum.Enum):
    """Categories of failures in the verification pipeline.

    These must not be flattened into one generic failure.
    Each category has distinct semantic meaning and maps to
    a different domain outcome.
    """

    # Input validation failures (request-level, before provider)
    INVALID_INPUT = "INVALID_INPUT"
    EMPTY_IMAGE = "EMPTY_IMAGE"
    OVERSIZED_IMAGE = "OVERSIZED_IMAGE"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    CORRUPTED_IMAGE = "CORRUPTED_IMAGE"
    IMAGE_TOO_SMALL = "IMAGE_TOO_SMALL"
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"
    DECOMPRESSION_BOMB = "DECOMPRESSION_BOMB"

    # Provider-level failures (provider could not produce evidence)
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_INITIALIZATION = "PROVIDER_INITIALIZATION"
    PROVIDER_INTERNAL_ERROR = "PROVIDER_INTERNAL_ERROR"

    # Face detection failures (detection worked, but input is unusable)
    NO_FACE_DETECTED = "NO_FACE_DETECTED"
    MULTIPLE_FACES = "MULTIPLE_FACES"

    # Recognition failures (detection OK, recognition failed)
    RECOGNITION_FAILED = "RECOGNITION_FAILED"

    # Liveness failures (anti-spoofing)
    LIVENESS_SPOOF_DETECTED = "LIVENESS_SPOOF_DETECTED"
    LIVENESS_UNAVAILABLE = "LIVENESS_UNAVAILABLE"

    # Evidence/decision outcomes
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    POLICY_DECISION = "POLICY_DECISION"

    # Human review/override
    HUMAN_OVERRIDE = "HUMAN_OVERRIDE"
    REVIEW_REQUESTED = "REVIEW_REQUESTED"

    # Lifecycle
    ATTEMPT_NOT_FOUND = "ATTEMPT_NOT_FOUND"
    WRONG_STATUS = "WRONG_STATUS"
    WRONG_METHOD = "WRONG_METHOD"
    DUPLICATE_EVIDENCE = "DUPLICATE_EVIDENCE"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_ERROR = "PROVIDER_ERROR"


# Mapping: failure category → whether the provider could not produce evidence
# (True = provider failure, not identity mismatch)
PROVIDER_FAILURE_CATEGORIES: set[FailureCategory] = {
    FailureCategory.PROVIDER_UNAVAILABLE,
    FailureCategory.PROVIDER_TIMEOUT,
    FailureCategory.PROVIDER_INITIALIZATION,
    FailureCategory.PROVIDER_INTERNAL_ERROR,
    FailureCategory.PROVIDER_ERROR,
}

# Mapping: failure category → whether this is an input validation error
INPUT_VALIDATION_CATEGORIES: set[FailureCategory] = {
    FailureCategory.INVALID_INPUT,
    FailureCategory.EMPTY_IMAGE,
    FailureCategory.OVERSIZED_IMAGE,
    FailureCategory.UNSUPPORTED_FORMAT,
    FailureCategory.CORRUPTED_IMAGE,
    FailureCategory.IMAGE_TOO_SMALL,
    FailureCategory.IMAGE_TOO_LARGE,
    FailureCategory.DECOMPRESSION_BOMB,
}

# Mapping: failure category → whether this is a face detection issue
FACE_DETECTION_CATEGORIES: set[FailureCategory] = {
    FailureCategory.NO_FACE_DETECTED,
    FailureCategory.MULTIPLE_FACES,
}


def categorize_provider_error(error_type: str) -> FailureCategory:
    """Map a provider error type string to a FailureCategory.

    Args:
        error_type: The FaceVerificationErrorType value string.

    Returns:
        The corresponding FailureCategory.
    """
    mapping = {
        "PROVIDER_UNAVAILABLE": FailureCategory.PROVIDER_UNAVAILABLE,
        "TIMEOUT": FailureCategory.PROVIDER_TIMEOUT,
        "INVALID_INPUT": FailureCategory.INVALID_INPUT,
        "NO_FACE_DETECTED": FailureCategory.NO_FACE_DETECTED,
        "MULTIPLE_FACES_DETECTED": FailureCategory.MULTIPLE_FACES,
        "LIVENESS_UNAVAILABLE": FailureCategory.LIVENESS_UNAVAILABLE,
        "IDENTITY_MATCH_UNAVAILABLE": FailureCategory.RECOGNITION_FAILED,
        "PROVIDER_REJECTED": FailureCategory.PROVIDER_ERROR,
        "INTERNAL_ERROR": FailureCategory.PROVIDER_INTERNAL_ERROR,
    }
    return mapping.get(error_type, FailureCategory.PROVIDER_ERROR)


def is_provider_failure(category: FailureCategory) -> bool:
    """Check if a failure category represents a provider-level failure.

    Provider failures mean the provider could NOT produce evidence.
    This is different from identity mismatch (provider produced evidence
    indicating different person).
    """
    return category in PROVIDER_FAILURE_CATEGORIES


def is_input_validation(category: FailureCategory) -> bool:
    """Check if a failure category represents an input validation error."""
    return category in INPUT_VALIDATION_CATEGORIES


def is_face_detection(category: FailureCategory) -> bool:
    """Check if a failure category represents a face detection issue."""
    return category in FACE_DETECTION_CATEGORIES

"""Image validation utilities for face verification pipeline.

Provides robust input validation for face verification requests:
- Base64 decoding with strict error handling
- Image format verification via magic bytes
- Image size limits (configurable)
- Image dimension limits (min/max)
- Corrupted image detection
- Decompression bomb protection

All validation is stateless and produces no logging of image content.
Raw image bytes are never persisted or returned in error details.
"""

from __future__ import annotations

import io
import struct

import cv2
import numpy as np

from app.core.config import get_settings


# Magic byte signatures for supported image formats
_MAGIC_BYTES = {
    "image/jpeg": [
        b"\xff\xd8\xff",  # JPEG/JFIF/EXIF
    ],
    "image/png": [
        b"\x89PNG\r\n\x1a\n",  # PNG
    ],
}

# Maximum reasonable image dimensions (prevents decompression bombs)
MAX_IMAGE_DIMENSION = 16384  # 16K pixels per side
MIN_IMAGE_DIMENSION = 16     # Minimum viable face image

# Maximum decoded image memory (pixels * channels * bytes_per_pixel)
# 16384 * 16384 * 3 * 1 byte = ~768 MB — dangerous decompression bomb
MAX_DECODED_PIXELS = MAX_IMAGE_DIMENSION * MAX_IMAGE_DIMENSION


class ImageValidationError(Exception):
    """Raised when image input fails validation.

    Attributes:
        error_type: Categorizes the validation failure.
        message: Human-readable error description.
    """

    def __init__(self, error_type: str, message: str) -> None:
        self.error_type = error_type
        self.message = message
        super().__init__(message)


def validate_image_bytes(
    image_bytes: bytes,
    *,
    field_name: str = "image",
    max_size_bytes: int | None = None,
    supported_formats: tuple[str, ...] = ("image/jpeg", "image/png"),
) -> None:
    """Validate raw image bytes before processing.

    Checks:
    1. Non-empty
    2. Size limit
    3. Magic bytes match a supported format
    4. Decodable by OpenCV (corruption check)
    5. Reasonable dimensions (decompression bomb protection)

    Args:
        image_bytes: Raw image file bytes.
        field_name: Name of the field for error messages (e.g. "reference_image").
        max_size_bytes: Maximum allowed size. None uses config default.
        supported_formats: Allowed image MIME types.

    Raises:
        ImageValidationError: If any validation fails.
    """
    if not image_bytes:
        raise ImageValidationError(
            error_type="EMPTY_IMAGE",
            message=f"{field_name} is empty",
        )

    settings = get_settings()
    if max_size_bytes is None:
        max_size_bytes = settings.FACE_VERIFICATION_MAX_IMAGE_SIZE_MB * 1024 * 1024

    if len(image_bytes) > max_size_bytes:
        raise ImageValidationError(
            error_type="OVERSIZED_IMAGE",
            message=(
                f"{field_name} exceeds maximum size: "
                f"{len(image_bytes)} bytes > {max_size_bytes} bytes"
            ),
        )

    _validate_magic_bytes(image_bytes, field_name, supported_formats)
    _validate_decodable(image_bytes, field_name)


def _validate_magic_bytes(
    image_bytes: bytes,
    field_name: str,
    supported_formats: tuple[str, ...],
) -> None:
    """Verify image bytes start with a known format signature."""
    detected_format = detect_image_format(image_bytes)
    if detected_format not in supported_formats:
        raise ImageValidationError(
            error_type="UNSUPPORTED_FORMAT",
            message=(
                f"{field_name} has unsupported format: "
                f"detected {detected_format or 'unknown'}, "
                f"allowed: {', '.join(supported_formats)}"
            ),
        )


def _validate_decodable(image_bytes: bytes, field_name: str) -> None:
    """Verify OpenCV can decode the image (catches corruption)."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise ImageValidationError(
            error_type="CORRUPTED_IMAGE",
            message=f"{field_name} is corrupted or cannot be decoded",
        )

    height, width = image.shape[:2]

    if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
        raise ImageValidationError(
            error_type="IMAGE_TOO_SMALL",
            message=(
                f"{field_name} dimensions too small: {width}x{height}, "
                f"minimum: {MIN_IMAGE_DIMENSION}x{MIN_IMAGE_DIMENSION}"
            ),
        )

    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise ImageValidationError(
            error_type="IMAGE_TOO_LARGE",
            message=(
                f"{field_name} dimensions too large: {width}x{height}, "
                f"maximum: {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION}"
            ),
        )

    total_pixels = width * height
    if total_pixels > MAX_DECODED_PIXELS:
        raise ImageValidationError(
            error_type="DECOMPRESSION_BOMB",
            message=(
                f"{field_name} pixel count exceeds safe limit: "
                f"{total_pixels} > {MAX_DECODED_PIXELS}"
            ),
        )


def detect_image_format(image_bytes: bytes) -> str | None:
    """Detect image format from magic bytes.

    Args:
        image_bytes: Raw image file bytes.

    Returns:
        MIME type string (e.g. "image/jpeg") or None if unknown.
    """
    if len(image_bytes) < 8:
        return None

    for mime_type, signatures in _MAGIC_BYTES.items():
        for sig in signatures:
            if image_bytes[:len(sig)] == sig:
                return mime_type

    return None


def decode_image_safely(image_bytes: bytes) -> np.ndarray:
    """Decode image bytes to OpenCV array with validation.

    This is the safe entry point for image decoding in the pipeline.
    Validates before decoding.

    Args:
        image_bytes: Raw image file bytes.

    Returns:
        numpy array in BGR format (OpenCV convention).

    Raises:
        ImageValidationError: If decoding fails.
    """
    validate_image_bytes(image_bytes)
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise ImageValidationError(
            error_type="CORRUPTED_IMAGE",
            message="Image could not be decoded after validation passed",
        )
    return image

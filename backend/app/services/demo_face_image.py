"""Generate a deterministic synthetic face image for demo/testing purposes.

Produces a simple but recognizable face-like image that UniFace can detect.
This is NOT a real person — it is a geometric illustration used solely for
demonstrating the face verification pipeline.

The image is deterministic: the same PNG bytes are produced every call,
ensuring the demo candidate's reference face is stable across sessions.
"""

from io import BytesIO
import hashlib

try:
    from PIL import Image, ImageDraw
except ImportError:
    raise ImportError(
        "Pillow is required for demo face generation. "
        "Install with: pip install Pillow"
    )

# Fixed canvas size
_SIZE = 256
_BG = (240, 235, 228)       # warm off-white background
_SKIN = (210, 180, 150)     # neutral skin tone
_HAIR = (60, 45, 35)        # dark brown hair
_EYE_W = (255, 255, 255)    # eye white
_IRIS = (70, 110, 80)       # green iris
_PUPIL = (20, 20, 20)       # black pupil
_NOSE = (190, 160, 130)     # slightly darker than skin
_MOUTH = (170, 90, 90)      # muted red
_LIP_LINE = (140, 70, 70)   # darker lip line


def _draw_face(img: "Image.Image") -> None:
    """Draw a simple face illustration on the image."""
    draw = ImageDraw.Draw(img)
    cx, cy = _SIZE // 2, _SIZE // 2 + 10  # center of face

    # Hair (oval behind head)
    draw.ellipse([cx - 85, cy - 115, cx + 85, cy + 15], fill=_HAIR)

    # Face oval
    draw.ellipse([cx - 70, cy - 85, cx + 70, cy + 85], fill=_SKIN)

    # Ears
    draw.ellipse([cx - 80, cy - 20, cx - 55, cy + 20], fill=_SKIN)
    draw.ellipse([cx + 55, cy - 20, cx + 80, cy + 20], fill=_SKIN)

    # Eyes — white
    draw.ellipse([cx - 45, cy - 25, cx - 10, cy + 5], fill=_EYE_W)
    draw.ellipse([cx + 10, cy - 25, cx + 45, cy + 5], fill=_EYE_W)

    # Iris
    draw.ellipse([cx - 32, cy - 16, cx - 18, cy - 2], fill=_IRIS)
    draw.ellipse([cx + 18, cy - 16, cx + 32, cy - 2], fill=_IRIS)

    # Pupil
    draw.ellipse([cx - 27, cy - 12, cx - 22, cy - 7], fill=_PUPIL)
    draw.ellipse([cx + 22, cy - 12, cx + 27, cy - 7], fill=_PUPIL)

    # Eyebrows
    draw.arc([cx - 48, cy - 42, cx - 8, cy - 22], 180, 360, fill=_HAIR, width=3)
    draw.arc([cx + 8, cy - 42, cx + 48, cy - 22], 180, 360, fill=_HAIR, width=3)

    # Nose
    draw.line([cx, cy - 8, cx - 8, cy + 20], fill=_NOSE, width=2)
    draw.line([cx - 8, cy + 20, cx + 8, cy + 20], fill=_NOSE, width=2)

    # Mouth
    draw.arc([cx - 25, cy + 30, cx + 25, cy + 55], 0, 180, fill=_LIP_LINE, width=2)

    # Neck
    draw.rectangle([cx - 15, cy + 85, cx + 15, cy + 120], fill=_SKIN)


def generate_demo_face_png() -> bytes:
    """Generate a deterministic synthetic face image as PNG bytes.

    Returns the same bytes on every call, suitable for use as a stable
    reference face image for the demo candidate.
    """
    img = Image.new("RGB", (_SIZE, _SIZE), _BG)
    _draw_face(img)
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def demo_face_hash() -> str:
    """Return a short hex hash of the demo face for idempotency checks."""
    return hashlib.sha256(generate_demo_face_png()).hexdigest()[:16]

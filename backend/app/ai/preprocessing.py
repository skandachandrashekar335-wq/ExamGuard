import math

import cv2
import numpy as np
from numpy.typing import NDArray


def to_grayscale(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    if len(image.shape) == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def denoise(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    return cv2.medianBlur(image, 3)


def adaptive_threshold(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    gray = to_grayscale(image)
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )


def deskew(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    gray = to_grayscale(image) if len(image.shape) == 3 else image
    if len(gray.shape) != 2:
        return image

    coords = np.column_stack(np.where(gray > 0))
    if len(coords) < 50:
        return image

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) < 0.5:
        return image

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def normalize_resolution(
    image: NDArray[np.uint8], target_dpi: int = 300, current_dpi: int = 72
) -> NDArray[np.uint8]:
    scale = target_dpi / current_dpi
    if abs(scale - 1.0) < 0.1:
        return image

    h, w = image.shape[:2]
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)


def preprocess_image(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    result = to_grayscale(image)
    result = denoise(result)
    result = deskew(result)
    return result

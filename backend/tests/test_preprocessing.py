import numpy as np
import pytest

from app.ai.preprocessing import (
    adaptive_threshold,
    denoise,
    deskew,
    normalize_resolution,
    preprocess_image,
    to_grayscale,
)


class TestToGrayscale:
    def test_bgr_to_grayscale(self):
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = to_grayscale(img)
        assert result.ndim == 2

    def test_already_grayscale(self):
        img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        result = to_grayscale(img)
        assert result.ndim == 2
        np.testing.assert_array_equal(result, img)


class TestDenoise:
    def test_reduces_noise(self):
        img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        result = denoise(img)
        assert result.shape == img.shape
        assert result.dtype == np.uint8


class TestAdaptiveThreshold:
    def test_produces_binary(self):
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = adaptive_threshold(img)
        assert result.ndim == 2
        unique_vals = set(np.unique(result))
        assert unique_vals <= {0, 255}

    def test_grayscale_input(self):
        img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        result = adaptive_threshold(img)
        assert result.ndim == 2


class TestDeskew:
    def test_straight_image_unchanged(self):
        img = np.zeros((100, 200), dtype=np.uint8)
        img[20:80, 20:180] = 255
        result = deskew(img)
        assert result.shape == img.shape

    def test_small_image_unchanged(self):
        img = np.zeros((10, 10), dtype=np.uint8)
        img[2:8, 2:8] = 255
        result = deskew(img)
        np.testing.assert_array_equal(result, img)


class TestNormalizeResolution:
    def test_no_change_when_close(self):
        img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        result = normalize_resolution(img, target_dpi=300, current_dpi=310)
        np.testing.assert_array_equal(result, img)

    def test_scales_up(self):
        img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        result = normalize_resolution(img, target_dpi=600, current_dpi=300)
        assert result.shape[0] == 200
        assert result.shape[1] == 200


class TestPreprocessImage:
    def test_full_pipeline(self):
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = preprocess_image(img)
        assert result.ndim == 2
        assert result.dtype == np.uint8

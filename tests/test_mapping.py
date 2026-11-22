"""
Unit tests for Step 5:
Direct Linear Transformation (DLT) 8x8 system, planar homography,
camera-to-board coordinate mapping, validation error estimation, and exchange format.
"""

import unittest
import numpy as np

from config import settings
from modules.calibration import (
    compute_homography_dlt,
    transform_point_homography,
    evaluate_calibration_error,
    BoardCalibrator,
)
from modules.mapping import CoordinateMapper


class TestMappingStep5(unittest.TestCase):
    """Test suite for Step 5 calibration and mapping algorithms."""

    def test_dlt_homography_exactness(self):
        """Verify DLT 8x8 system solution reproduces exact target corners with zero fitting error."""
        # Simulated camera corners (trapezoid under perspective tilt)
        src = np.array([
            [100.0, 80.0],    # Top-Left
            [540.0, 60.0],    # Top-Right
            [570.0, 430.0],   # Bottom-Right
            [70.0, 440.0],    # Bottom-Left
        ], dtype=np.float64)

        # Whiteboard corners (1280x720)
        dst = np.array([
            [0.0, 0.0],
            [1280.0, 0.0],
            [1280.0, 720.0],
            [0.0, 720.0],
        ], dtype=np.float64)

        H = compute_homography_dlt(src, dst)

        self.assertEqual(H.shape, (3, 3))
        self.assertEqual(H[2, 2], 1.0)

        # Reproject all 4 corners
        for (x, y), (u, v) in zip(src, dst):
            u_est, v_est = transform_point_homography(x, y, H)
            err = np.hypot(u_est - u, v_est - v)
            self.assertLess(err, 1e-4, f"DLT error must be practically zero, got {err}")

    def test_reprojection_validation_error(self):
        """Verify calibration evaluation metrics computation on validation points."""
        src = np.array(settings.DEFAULT_CAMERA_CORNERS, dtype=np.float64)
        dst = np.array([
            [0.0, 0.0],
            [1280.0, 0.0],
            [1280.0, 720.0],
            [0.0, 720.0],
        ], dtype=np.float64)

        H = compute_homography_dlt(src, dst)
        metrics = evaluate_calibration_error(src, dst, H)

        self.assertIn("mean_corner_error_px", metrics)
        self.assertLess(metrics["mean_corner_error_px"], 1e-3)

    def test_coordinate_mapper_clamping(self):
        """Verify that mapped board coordinates are strictly clamped within [0, BOARD_WIDTH] x [0, BOARD_HEIGHT]."""
        mapper = CoordinateMapper()

        # Test extreme out-of-bounds camera coordinates
        u_neg, v_neg = mapper.map_point(-1000.0, -1000.0)
        self.assertGreaterEqual(u_neg, 0.0)
        self.assertGreaterEqual(v_neg, 0.0)

        u_far, v_far = mapper.map_point(5000.0, 5000.0)
        self.assertLessEqual(u_far, float(settings.BOARD_WIDTH))
        self.assertLessEqual(v_far, float(settings.BOARD_HEIGHT))

    def test_mapped_pointer_exchange_format(self):
        """Verify that map_pointer enriches dictionary with 'u' and 'v' according to contract."""
        mapper = CoordinateMapper()
        raw_pointer = {
            "detected": True,
            "x": 320.0,
            "y": 240.0,
            "raw_x": 321.0,
            "raw_y": 239.5,
            "area": 1400,
        }

        mapped = mapper.map_pointer(raw_pointer)

        # Check all required keys
        for key in ("detected", "x", "y", "raw_x", "raw_y", "area", "u", "v"):
            self.assertIn(key, mapped)

        self.assertIsInstance(mapped["u"], float)
        self.assertIsInstance(mapped["v"], float)
        self.assertGreaterEqual(mapped["u"], 0.0)
        self.assertLessEqual(mapped["u"], float(settings.BOARD_WIDTH))
        self.assertGreaterEqual(mapped["v"], 0.0)
        self.assertLessEqual(mapped["v"], float(settings.BOARD_HEIGHT))


if __name__ == "__main__":
    unittest.main()

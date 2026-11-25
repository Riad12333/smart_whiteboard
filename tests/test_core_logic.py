"""
Unit tests for Core Logic (Step 4quinquies - Partie E).
Validates pure mathematical algorithms against reference test fixtures:
  - DLT Homography solver vs tests/fixtures/homography_cases.json
  - Point transformation
  - Jitter deadzone
  - Bresenham integer line rasterization
  - Pure stroke history transitions (Undo / Redo)
"""

import json
import unittest
from pathlib import Path
import numpy as np

from modules.core_logic import (
    compute_homography_dlt,
    transform_point_homography,
    apply_deadzone,
    bresenham_line,
    create_stroke,
    add_point_to_stroke,
    undo_stroke,
    redo_stroke,
)

FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures" / "homography_cases.json"


class TestCoreLogic(unittest.TestCase):
    """Test suite for pure stateless algorithms."""

    def setUp(self):
        with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
            self.fixture = json.load(f)

    def test_dlt_homography_against_fixture(self):
        """Verify that pure compute_homography_dlt matches expected matrix from fixture."""
        src = self.fixture["calibration_pairs"]["camera_src_corners"]
        dst = self.fixture["calibration_pairs"]["board_dst_corners"]
        expected_H = np.array(self.fixture["expected_homography_matrix_3x3"], dtype=np.float64)

        computed_H = compute_homography_dlt(src, dst)
        np.testing.assert_allclose(computed_H, expected_H, rtol=1e-5, atol=1e-5)

    def test_point_transformation_against_fixture(self):
        """Verify that point projection matches all expected test points in fixture."""
        H = np.array(self.fixture["expected_homography_matrix_3x3"], dtype=np.float64)

        for case in self.fixture["test_points"]:
            cam_pt = case["camera_point"]
            expected_bd = case["expected_board_point"]

            u, v = transform_point_homography(cam_pt[0], cam_pt[1], H)
            self.assertAlmostEqual(u, expected_bd[0], delta=0.01)
            self.assertAlmostEqual(v, expected_bd[1], delta=0.01)

    def test_bresenham_line_continuity(self):
        """Verify that Bresenham algorithm produces contiguous 8-connected grid lines."""
        pts = bresenham_line(10, 10, 20, 25)
        self.assertEqual(pts[0], (10, 10))
        self.assertEqual(pts[-1], (20, 25))

        # Check connectivity: each step has max(dx, dy) <= 1
        for i in range(len(pts) - 1):
            dx = abs(pts[i + 1][0] - pts[i][0])
            dy = abs(pts[i + 1][1] - pts[i][1])
            self.assertLessEqual(max(dx, dy), 1, "Adjacent Bresenham points must be 8-connected.")

    def test_pure_stroke_undo_redo(self):
        """Verify pure immutable stroke transitions."""
        stroke1 = create_stroke("PEN", (30, 30, 30), 7)
        stroke1 = add_point_to_stroke(stroke1, 100, 150)
        stroke2 = create_stroke("PEN", (25, 113, 194), 3)

        history = [stroke1, stroke2]
        redo_stack = []

        # Undo
        history, redo_stack = undo_stroke(history, redo_stack)
        self.assertEqual(len(history), 1)
        self.assertEqual(len(redo_stack), 1)
        self.assertEqual(redo_stack[0]["color"], [25, 113, 194])

        # Redo
        history, redo_stack = redo_stroke(history, redo_stack)
        self.assertEqual(len(history), 2)
        self.assertEqual(len(redo_stack), 0)

    def test_apply_deadzone(self):
        """Verify that movements smaller than deadzone are suppressed."""
        x, y, frozen = apply_deadzone(101.0, 101.0, 100.0, 100.0, deadzone_radius=3.0)
        self.assertTrue(frozen)
        self.assertEqual(x, 100.0)
        self.assertEqual(y, 100.0)

        x2, y2, frozen2 = apply_deadzone(110.0, 100.0, 100.0, 100.0, deadzone_radius=3.0)
        self.assertFalse(frozen2)
        self.assertEqual(x2, 110.0)


if __name__ == "__main__":
    unittest.main()

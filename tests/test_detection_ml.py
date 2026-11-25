"""
Unit tests for Step 4quinquies:
Machine Learning Hand Detector, 1€ Filter, Posture Verification,
Multi-hand Arbitration, Board Polygon Confinement, and Exchange Format.
"""

import math
import unittest
import numpy as np

from modules.detection_ml import (
    OneEuroFilter,
    PointFilter2D,
    verify_pointing_posture,
    HandMLDetector,
)


class TestDetectionML(unittest.TestCase):
    """Test suite for ML-based hand tracking and filters."""

    def test_one_euro_filter_stability_and_lag(self):
        """Verify that 1€ filter smoothes heavily when static and reacts fast when moving."""
        f = OneEuroFilter(min_cutoff=1.0, beta=0.01)

        # Static position with tiny noise at 60 Hz
        t = 0.0
        dt = 1.0 / 60.0
        val = 100.0

        filtered_vals = []
        for i in range(30):
            t += dt
            noisy = val + (0.5 if i % 2 == 0 else -0.5)
            filtered = f.filter(noisy, t)
            filtered_vals.append(filtered)

        # Standard deviation of filtered output should be lower than input noise (0.5)
        std_filtered = np.std(filtered_vals[-15:])
        self.assertLess(std_filtered, 0.45, "1€ filter must reduce high-frequency static noise.")

    def test_point_filter_2d_deadzone(self):
        """Verify that 2D filter suppresses sub-deadzone tremor."""
        pf = PointFilter2D(filter_type="ONE_EURO", deadzone=3.0)

        # Initial point
        sm_x1, sm_y1 = pf.update(200.0, 200.0, timestamp=0.0)
        self.assertEqual(sm_x1, 200.0)
        self.assertEqual(sm_y1, 200.0)

        # Tremor displacement of 1.5 px (sqrt(1 + 1) = 1.414 < 3.0)
        sm_x2, sm_y2 = pf.update(201.0, 201.0, timestamp=0.033)
        self.assertEqual(sm_x2, 200.0, "Sub-deadzone X must freeze.")
        self.assertEqual(sm_y2, 200.0, "Sub-deadzone Y must freeze.")

        # Large movement of 50 px (> 3.0)
        sm_x3, sm_y3 = pf.update(250.0, 200.0, timestamp=0.066)
        self.assertGreater(sm_x3, 205.0, "Movement beyond deadzone must be updated.")

    def test_pointing_posture_validation(self):
        """Verify that verify_pointing_posture accurately distinguishes pointing from other gestures."""
        # Construct synthetic landmarks (21, 3)
        # Wrist at (100, 300)
        landmarks = np.zeros((21, 3), dtype=np.float32)
        wrist = np.array([100.0, 300.0])
        landmarks[0, :2] = wrist

        # CASE 1: Valid Pointing Hand (Index extended up, others curled down)
        # Index: MCP 5, PIP 6, DIP 7, TIP 8
        landmarks[5, :2] = [100.0, 250.0]  # MCP
        landmarks[6, :2] = [100.0, 200.0]  # PIP
        landmarks[7, :2] = [100.0, 150.0]  # DIP
        landmarks[8, :2] = [100.0, 100.0]  # TIP (far from wrist)

        # Middle: MCP 9, PIP 10, DIP 11, TIP 12 (folded)
        landmarks[9, :2] = [120.0, 250.0]
        landmarks[10, :2] = [120.0, 200.0]  # PIP
        landmarks[11, :2] = [120.0, 230.0]
        landmarks[12, :2] = [120.0, 260.0]  # TIP folded closer to wrist than PIP!

        # Ring: MCP 13, PIP 14, DIP 15, TIP 16 (folded)
        landmarks[13, :2] = [140.0, 250.0]
        landmarks[14, :2] = [140.0, 200.0]  # PIP
        landmarks[15, :2] = [140.0, 230.0]
        landmarks[16, :2] = [140.0, 260.0]  # TIP folded

        # Pinky: MCP 17, PIP 18, DIP 19, TIP 20 (folded)
        landmarks[17, :2] = [160.0, 250.0]
        landmarks[18, :2] = [160.0, 200.0]  # PIP
        landmarks[19, :2] = [160.0, 230.0]
        landmarks[20, :2] = [160.0, 260.0]  # TIP folded

        self.assertTrue(verify_pointing_posture(landmarks), "Pointing posture must be recognized.")

        # CASE 2: Flat open hand (Middle finger also extended)
        landmarks[12, :2] = [120.0, 90.0]  # Middle tip extended far from wrist
        self.assertFalse(verify_pointing_posture(landmarks), "Flat open hand must not be accepted as pointing.")

        # CASE 3: Closed fist (Index also folded)
        landmarks[8, :2] = [100.0, 260.0]  # Index folded
        self.assertFalse(verify_pointing_posture(landmarks), "Closed fist must not be accepted as pointing.")

    def test_detector_initialization_and_exchange_format(self):
        """Verify HandMLDetector initializes cleanly and adheres to exchange dictionary format."""
        detector = HandMLDetector(require_pointing=False)

        # Test on dummy black frame
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(dummy_frame)

        # Check all required exchange format fields
        expected_keys = [
            "detected", "x", "y", "raw_x", "raw_y", "area",
            "landmarks", "score", "box", "pointing", "inference_time_ms"
        ]
        for key in expected_keys:
            self.assertIn(key, result, f"Exchange format missing key '{key}'")

        self.assertFalse(result["detected"], "Black frame should not trigger detection.")
        self.assertGreater(result["inference_time_ms"], 0.0, "Inference time must be measured.")

    def test_board_polygon_confinement(self):
        """Verify that pointer candidate is filtered out if outside board polygon."""
        detector = HandMLDetector(require_pointing=False)
        board_corners = [[100, 100], [500, 100], [500, 400], [100, 400]]
        detector.set_board_polygon(board_corners)

        # Inside point
        self.assertTrue(detector._is_inside_board(250, 250), "Center point must be inside board.")

        # Far outside point
        self.assertFalse(detector._is_inside_board(50, 50), "Outside point must be rejected.")


if __name__ == "__main__":
    unittest.main()

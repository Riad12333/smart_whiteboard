"""
Unit tests for Step 4:
Pointer stabilization, Exponential Moving Average (EMA), deadzone filtering,
tracking loss, reacquisition, and exchange format validation.
"""

import unittest
import numpy as np

from config import settings
from modules.detection import (
    PointerStabilizer,
    detect_pointer,
    SkinColorCalibrator,
)


class TestDetectionStep4(unittest.TestCase):
    """Test suite for Step 4 temporal smoothing and stability algorithms."""

    def test_stabilizer_reacquisition(self):
        """Verify that on first detection after being lost, stabilizer jumps directly to raw position."""
        stabilizer = PointerStabilizer(alpha=0.3, deadzone=3.0)
        self.assertFalse(stabilizer.is_active)

        # First frame detected at (100.0, 200.0)
        raw = {"detected": True, "raw_x": 100.0, "raw_y": 200.0, "area": 1200}
        out = stabilizer.update(raw)

        self.assertTrue(out["detected"])
        self.assertEqual(out["x"], 100.0, "First smoothed X must match raw X immediately.")
        self.assertEqual(out["y"], 200.0, "First smoothed Y must match raw Y immediately.")

    def test_stabilizer_deadzone(self):
        """Verify that movements smaller than DEADZONE_RADIUS are ignored (static holding)."""
        stabilizer = PointerStabilizer(alpha=0.35, deadzone=4.0)

        # Initial point
        stabilizer.update({"detected": True, "raw_x": 200.0, "raw_y": 200.0, "area": 1000})

        # Tiny tremor displacement of 1.5 pixels (sqrt(1^2 + 1^2) = 1.414 < 4.0)
        tremor_raw = {"detected": True, "raw_x": 201.0, "raw_y": 201.0, "area": 1000}
        out = stabilizer.update(tremor_raw)

        self.assertEqual(out["x"], 200.0, "Sub-deadzone displacement must not move smoothed X.")
        self.assertEqual(out["y"], 200.0, "Sub-deadzone displacement must not move smoothed Y.")
        self.assertEqual(out["raw_x"], 201.0, "raw_x must still preserve raw coordinate.")

    def test_stabilizer_ema_smoothing(self):
        """Verify mathematical correctness of Exponential Moving Average for larger movements."""
        alpha = 0.4
        stabilizer = PointerStabilizer(alpha=alpha, deadzone=2.0)

        # Frame 0
        stabilizer.update({"detected": True, "raw_x": 100.0, "raw_y": 100.0, "area": 1000})

        # Frame 1: Large movement to (150.0, 100.0)
        # Expected: X = 0.4 * 150.0 + 0.6 * 100.0 = 60.0 + 60.0 = 120.0
        out1 = stabilizer.update({"detected": True, "raw_x": 150.0, "raw_y": 100.0, "area": 1000})
        self.assertAlmostEqual(out1["x"], 120.0, places=2)
        self.assertEqual(out1["y"], 100.0)

    def test_tracking_loss_and_recovery(self):
        """Verify tracking loss transitions after MAX_LOST_FRAMES."""
        max_lost = 3
        stabilizer = PointerStabilizer(max_lost_frames=max_lost)

        # Valid point
        stabilizer.update({"detected": True, "raw_x": 300.0, "raw_y": 300.0, "area": 1500})
        self.assertTrue(stabilizer.is_active)

        # Lost frame 1 and 2: Still active (buffer)
        for _ in range(max_lost - 1):
            out = stabilizer.update({"detected": False, "raw_x": 0.0, "raw_y": 0.0, "area": 0})
            self.assertFalse(out["detected"])
            self.assertTrue(stabilizer.is_active)

        # Lost frame 3: Now marked completely inactive
        out = stabilizer.update({"detected": False, "raw_x": 0.0, "raw_y": 0.0, "area": 0})
        self.assertFalse(out["detected"])
        self.assertFalse(stabilizer.is_active)

    def test_pointer_exchange_format_contract(self):
        """Ensure the contract keys and types match the mandatory specification."""
        frame = np.zeros((settings.FRAME_HEIGHT, settings.FRAME_WIDTH, 3), dtype=np.uint8)
        stabilizer = PointerStabilizer()
        pointer, mask = detect_pointer(frame, stabilizer=stabilizer)

        mandatory_fields = {
            "detected": bool,
            "x": float,
            "y": float,
            "raw_x": float,
            "raw_y": float,
            "area": int,
        }

        for field, expected_type in mandatory_fields.items():
            self.assertIn(field, pointer)
            self.assertIsInstance(pointer[field], expected_type)


if __name__ == "__main__":
    unittest.main()

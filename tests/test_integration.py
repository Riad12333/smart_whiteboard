"""
Integration tests for Step 10:
End-to-end integration test verifying that the main application loop,
subsystem coordination, camera fallback, mapping, and dashboard execute without crash.
"""

import time
import unittest
import numpy as np

from config import settings
from modules.camera import CameraManager
from modules.detection import SkinColorCalibrator, PointerStabilizer, detect_pointer
from modules.calibration import BoardCalibrator
from modules.mapping import CoordinateMapper
from modules.remote import RemoteHandler
from modules.interface import WhiteboardInterface
from modules.interaction import InteractionManager
from main import TechnicalDashboard


class TestIntegrationStep10(unittest.TestCase):
    """Test suite for Step 10 End-to-End System Integration."""

    def test_full_pipeline_headless_run(self):
        """Run 30 full pipeline iterations with synthetic data to verify subsystem cohesion."""
        interface = WhiteboardInterface()
        interaction = InteractionManager(interface)
        remote = RemoteHandler()
        board_calib = BoardCalibrator()
        mapper = CoordinateMapper(calibrator=board_calib)
        stabilizer = PointerStabilizer()
        skin_calib = SkinColorCalibrator()
        dashboard = TechnicalDashboard()

        # Synthetic frame
        frame = np.full((settings.FRAME_HEIGHT, settings.FRAME_WIDTH, 3), 40, dtype=np.uint8)

        # Simulate hand pointing in center
        frame[200:260, 300:340] = [115, 140, 190]  # Skin tone

        for i in range(30):
            # 1. Detection
            raw_ptr, mask = detect_pointer(frame, calibrator=skin_calib, stabilizer=stabilizer)
            self.assertIn("detected", raw_ptr)

            # 2. Mapping
            mapped_ptr = mapper.map_pointer(raw_ptr)
            self.assertIn("u", mapped_ptr)
            self.assertIn("v", mapped_ptr)

            # 3. Remote event simulation (Every 10 frames trigger a click)
            evt = "LEFT_CLICK" if i == 10 else None

            # 4. Interaction
            action = interaction.process_interaction(mapped_ptr, evt)

            # 5. Interface render
            ui_frame = interface.render(mapped_ptr)
            self.assertEqual(ui_frame.shape, (settings.BOARD_HEIGHT, settings.BOARD_WIDTH, 3))

            # 6. Dashboard render
            dash_frame = dashboard.render(
                camera_frame=frame,
                pointer_data=mapped_ptr,
                calibrator=board_calib,
                skin_calibrator=skin_calib,
                stabilizer=stabilizer,
                remote_handler=remote,
                camera_fps=30.0,
                system_fps=60.0,
                mode="SKIN",
                mouse_mode=False,
            )
            self.assertEqual(dash_frame.shape, (settings.FRAME_HEIGHT, settings.FRAME_WIDTH, 3))

    def test_dashboard_render_hand_ml(self):
        """Verify TechnicalDashboard rendering with HAND_ML mode and 21-landmarks skeleton."""
        dashboard = TechnicalDashboard()
        board_calib = BoardCalibrator()
        skin_calib = SkinColorCalibrator()
        stabilizer = PointerStabilizer()
        remote = RemoteHandler()

        frame = np.zeros((settings.FRAME_HEIGHT, settings.FRAME_WIDTH, 3), dtype=np.uint8)

        # Synthetic 21 landmarks
        landmarks = np.zeros((21, 3), dtype=np.float32)
        for i in range(21):
            landmarks[i, :2] = [200.0 + i * 5, 200.0 + i * 3]

        ml_ptr = {
            "detected": True,
            "x": 240.0,
            "y": 224.0,
            "raw_x": 240.0,
            "raw_y": 224.0,
            "area": 12000,
            "landmarks": landmarks,
            "score": 0.94,
            "box": [180.0, 180.0, 320.0, 300.0],
            "pointing": True,
            "inference_time_ms": 11.8,
            "u": 480.0,
            "v": 336.0,
        }

        dash_frame = dashboard.render(
            camera_frame=frame,
            pointer_data=ml_ptr,
            calibrator=board_calib,
            skin_calibrator=skin_calib,
            stabilizer=stabilizer,
            remote_handler=remote,
            camera_fps=30.0,
            system_fps=45.0,
            mode="HAND_ML",
            mouse_mode=False,
        )

        self.assertEqual(dash_frame.shape, (settings.FRAME_HEIGHT, settings.FRAME_WIDTH, 3))
        # Ensure rendered frame is not completely blank (overlay was drawn)
        self.assertGreater(dash_frame.sum(), 0)


if __name__ == "__main__":
    unittest.main()

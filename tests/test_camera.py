"""
Unit and integration tests for camera acquisition and FPS measurement.
"""

import os
import unittest
import numpy as np

from config import settings
from modules.camera import CameraManager


class TestCameraManager(unittest.TestCase):
    """Test suite for CameraManager."""

    def test_camera_init_and_read(self):
        """Verify that camera opens and reads frames with expected shape and type."""
        cam = CameraManager()
        opened = cam.open()
        self.assertTrue(opened, "Camera should open successfully.")

        ret, frame = cam.read_frame()
        self.assertTrue(ret, "read_frame() should return True.")
        self.assertIsNotNone(frame, "Captured frame must not be None.")
        self.assertEqual(
            frame.shape,
            (settings.FRAME_HEIGHT, settings.FRAME_WIDTH, 3),
            f"Frame shape must be ({settings.FRAME_HEIGHT}, {settings.FRAME_WIDTH}, 3).",
        )
        self.assertEqual(frame.dtype, np.uint8, "Frame dtype must be uint8.")
        cam.release()

    def test_record_and_playback(self):
        """Verify recording a short clip and playing it back."""
        test_clip_path = "assets/test_record_temp.avi"
        cam = CameraManager()
        self.assertTrue(cam.open())

        # Record 1 second clip
        recorded = cam.record_clip(output_path=test_clip_path, duration_sec=1)
        self.assertTrue(recorded, "record_clip() should succeed.")
        cam.release()

        self.assertTrue(os.path.isfile(test_clip_path), "Recorded video file should exist.")

        # Reopen from the recorded video file
        file_cam = CameraManager(source=test_clip_path, loop_video=False)
        self.assertTrue(file_cam.open(), "Should open recorded video file.")

        frames_read = 0
        while True:
            ret, frame = file_cam.read_frame()
            if not ret or frame is None:
                break
            frames_read += 1
            self.assertEqual(frame.shape, (settings.FRAME_HEIGHT, settings.FRAME_WIDTH, 3))

        file_cam.release()
        self.assertGreater(frames_read, 0, "Must read at least one frame from recorded video.")

        # Clean up temporary test clip
        if os.path.exists(test_clip_path):
            os.remove(test_clip_path)


if __name__ == "__main__":
    unittest.main()

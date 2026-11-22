"""
Camera acquisition, video capture, FPS measurement, and recording module.
Part of the Smart Interactive Whiteboard project (USTHB 2026-2027).
"""

import os
import sys
import time
from collections import deque
from pathlib import Path
from typing import Optional, Tuple, Union

# Add project root to sys.path to allow direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from config import settings


class CameraManager:
    """Manages video acquisition from a physical camera, IP stream, or video file."""

    def __init__(
        self,
        source: Optional[Union[int, str]] = None,
        target_width: Optional[int] = None,
        target_height: Optional[int] = None,
        loop_video: bool = True,
    ):
        """
        Initialize the camera manager.

        :param source: Device index (int), stream URL (str), or video file path (str).
        :param target_width: Desired output frame width.
        :param target_height: Desired output frame height.
        :param loop_video: If True and source is a video file, automatically rewind upon EOF.
        """
        self.source = settings.CAMERA_SOURCE if source is None else source
        self.target_width = settings.FRAME_WIDTH if target_width is None else target_width
        self.target_height = settings.FRAME_HEIGHT if target_height is None else target_height
        self.loop_video = loop_video

        self.cap: Optional[cv2.VideoCapture] = None
        self.is_opened: bool = False
        self.is_file_source: bool = isinstance(self.source, str) and os.path.isfile(self.source)

        # FPS calculation variables
        self._frame_times: deque = deque(maxlen=settings.FPS_CALC_WINDOW)
        self._last_time: float = time.perf_counter()
        self.current_fps: float = 0.0

    def open(self) -> bool:
        """
        Open the video capture stream.
        OpenCV call: cv2.VideoCapture() is used for hardware camera/video stream access.
        """
        if self.is_opened and self.cap is not None:
            return True

        # Open capture device or file
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            print(f"[CameraManager] Error: Unable to open source '{self.source}'")
            self.is_opened = False
            return False

        # If it's a live device (integer index), request desired resolution
        if isinstance(self.source, int):
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)

        self.is_opened = True
        self._frame_times.clear()
        self._last_time = time.perf_counter()
        print(f"[CameraManager] Stream opened successfully: source={self.source}")
        return True

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Grab, decode, and resize the next frame.
        OpenCV call: cap.read() grabs the raw BGR frame.
        OpenCV call: cv2.resize() ensures strictly uniform dimensions (settings.FRAME_WIDTH, settings.FRAME_HEIGHT).
        """
        if not self.is_opened or self.cap is None:
            return False, None

        ret, frame = self.cap.read()

        # Handle end of video file (looping mode)
        if not ret:
            if self.is_file_source and self.loop_video:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if not ret:
                    return False, None
            else:
                return False, None

        # Resize to fixed target resolution if necessary
        h, w = frame.shape[:2]
        if w != self.target_width or h != self.target_height:
            frame = cv2.resize(
                frame,
                (self.target_width, self.target_height),
                interpolation=cv2.INTER_AREA if (w > self.target_width) else cv2.INTER_LINEAR,
            )

        # Compute smoothed FPS using a sliding time window
        now = time.perf_counter()
        dt = now - self._last_time
        self._last_time = now

        if dt > 0.0:
            self._frame_times.append(dt)
            # Moving average of instantaneous frame times:
            mean_dt = sum(self._frame_times) / len(self._frame_times)
            self.current_fps = 1.0 / mean_dt if mean_dt > 0.0 else 0.0

        return True, frame

    def get_fps(self) -> float:
        """Return the current smoothed frame rate."""
        return self.current_fps

    def record_clip(
        self,
        output_path: str = settings.VIDEO_TEST_PATH,
        duration_sec: int = settings.RECORD_DURATION_SEC,
    ) -> bool:
        """
        Record a live clip of given duration to disk.
        OpenCV call: cv2.VideoWriter() is used to encode and save test footage.
        """
        if not self.is_opened or self.cap is None:
            print("[CameraManager] Cannot record: camera is not opened.")
            return False

        # Ensure directory exists
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*settings.RECORD_FOURCC)
        fps = settings.FPS_TARGET if self.current_fps < 5.0 else self.current_fps
        writer = cv2.VideoWriter(
            output_path, fourcc, float(fps), (self.target_width, self.target_height)
        )

        if not writer.isOpened():
            print(f"[CameraManager] Error: Could not initialize VideoWriter for '{output_path}'")
            return False

        print(f"[CameraManager] Recording {duration_sec}s clip to '{output_path}'...")
        total_frames = int(fps * duration_sec)
        frames_written = 0

        for _ in range(total_frames):
            success, frame = self.read_frame()
            if not success or frame is None:
                break
            writer.write(frame)
            frames_written += 1

        writer.release()
        print(f"[CameraManager] Recording complete: {frames_written} frames saved to '{output_path}'.")
        return True

    def release(self) -> None:
        """
        Release hardware camera resources.
        OpenCV call: cap.release() frees the camera device.
        """
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.is_opened = False
        print("[CameraManager] Stream released.")


def run_preview() -> None:
    """
    Interactive test preview for Step 1.
    Displays live feed or test video with real-time FPS overlay.
    Controls:
      - Press 'r': record a 5-second test video to assets/test_video.avi
      - Press 'q' or ESC: exit
    """
    cam = CameraManager()
    if not cam.open():
        print("[CameraPreview] Failed to open camera. Exiting.")
        return

    window_name = "Camera Preview - Step 1 (Press 'r' to record, 'q' to quit)"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    fps_history = []
    print("\n--- Controls in Preview Window ---")
    print(" [r] : Record a 5-second test video clip")
    print(" [q] or [ESC] : Quit preview")
    print("----------------------------------\n")

    try:
        while True:
            ret, frame = cam.read_frame()
            if not ret or frame is None:
                print("[CameraPreview] Warning: Failed to read frame.")
                break

            fps = cam.get_fps()
            if fps > 0:
                fps_history.append(fps)

            # Draw visual overlay on preview
            # OpenCV call: cv2.putText() is used here solely for debug HUD
            hud_text = f"FPS: {fps:5.1f} | Resolution: {frame.shape[1]}x{frame.shape[0]}"
            cv2.rectangle(frame, (8, 8), (420, 42), (0, 0, 0), -1)
            cv2.putText(
                frame,
                hud_text,
                (14, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):  # 'q' or ESC
                break
            elif key == ord("r"):
                # Display recording message on frame
                rec_msg = frame.copy()
                cv2.putText(
                    rec_msg,
                    "RECORDING...",
                    (frame.shape[1] // 2 - 120, frame.shape[0] // 2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 0, 255),
                    3,
                )
                cv2.imshow(window_name, rec_msg)
                cv2.waitKey(100)
                cam.record_clip()

    finally:
        cam.release()
        cv2.destroyAllWindows()

    if fps_history:
        avg_fps = float(np.mean(fps_history))
        std_fps = float(np.std(fps_history))
        print("\n--- Real Performance Measurements ---")
        print(f" Average FPS : {avg_fps:.2f}")
        print(f" FPS Std Dev : {std_fps:.2f}")
        print(f" Total frames: {len(fps_history)}")
        print("--------------------------------------\n")


if __name__ == "__main__":
    run_preview()

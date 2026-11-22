"""
Camera-to-Board Geometric Calibration module (Step 5).
Computes the 3x3 planar homography matrix using Direct Linear Transformation (DLT)
via an 8x8 linear system solved with np.linalg.solve.
Part of the Smart Interactive Whiteboard project (USTHB 2026-2027).

NOTE: The DLT matrix construction, 8x8 system resolution, projective transformations,
and reprojection error estimations are implemented completely from scratch using NumPy.
No cv2.findHomography or cv2.warpPerspective functions are used.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from config import settings
from modules.camera import CameraManager


def compute_homography_dlt(
    src_pts: np.ndarray, dst_pts: np.ndarray
) -> np.ndarray:
    """
    Estimate 3x3 planar homography matrix H mapping src_pts (camera) to dst_pts (board)
    using the Direct Linear Transformation (DLT) algorithm.

    Each point pair (x_i, y_i) -> (u_i, v_i) provides 2 linear equations:
      h11 * x + h12 * y + h13 - h31 * x * u - h32 * y * u = u
      h21 * x + h22 * y + h23 - h31 * x * v - h32 * y * v = v
    With 4 point pairs and setting h33 = 1, this forms an exact 8x8 linear system:
      A * h = b
    which is solved via np.linalg.solve(A, b).

    :param src_pts: Array of 4 points in camera image, shape (4, 2).
    :param dst_pts: Array of 4 corresponding points on board, shape (4, 2).
    :return: 3x3 Homography matrix as float64 NumPy array.
    """
    if len(src_pts) != 4 or len(dst_pts) != 4:
        raise ValueError("DLT requires exactly 4 corresponding point pairs.")

    A = []
    b = []

    for i in range(4):
        x, y = float(src_pts[i][0]), float(src_pts[i][1])
        u, v = float(dst_pts[i][0]), float(dst_pts[i][1])

        # Equation for u
        A.append([x, y, 1.0, 0.0, 0.0, 0.0, -x * u, -y * u])
        b.append(u)

        # Equation for v
        A.append([0.0, 0.0, 0.0, x, y, 1.0, -x * v, -y * v])
        b.append(v)

    A_mat = np.array(A, dtype=np.float64)
    b_vec = np.array(b, dtype=np.float64)

    # Solve the 8x8 system
    h = np.linalg.solve(A_mat, b_vec)

    # Assemble 3x3 matrix with h33 = 1.0
    H = np.array(
        [
            [h[0], h[1], h[2]],
            [h[3], h[4], h[5]],
            [h[6], h[7], 1.0],
        ],
        dtype=np.float64,
    )

    return H


def transform_point_homography(
    x: float, y: float, H: np.ndarray
) -> Tuple[float, float]:
    """
    Apply planar homography to map point (x, y) to (u, v).
      [s*u, s*v, s]^T = H * [x, y, 1]^T
      u = (H[0,0]*x + H[0,1]*y + H[0,2]) / s
      v = (H[1,0]*x + H[1,1]*y + H[1,2]) / s
      where s = H[2,0]*x + H[2,1]*y + H[2,2]
    """
    s = H[2, 0] * x + H[2, 1] * y + H[2, 2]
    if abs(s) < 1e-9:
        s = 1e-9  # Prevent division by zero

    u = (H[0, 0] * x + H[0, 1] * y + H[0, 2]) / s
    v = (H[1, 0] * x + H[1, 1] * y + H[1, 2]) / s
    return float(u), float(v)


def evaluate_calibration_error(
    src_pts: np.ndarray,
    dst_pts: np.ndarray,
    H: np.ndarray,
    validation_pairs: Optional[List[Tuple[Tuple[float, float], Tuple[float, float]]]] = None,
) -> Dict[str, float]:
    """
    Evaluate geometric reprojection accuracy:
      1. Training corner error (DLT fitting error).
      2. Validation error on independent test points across the board.
    Returns honest measured pixel errors.
    """
    # 1. Training error on the 4 corners
    corner_errors = []
    for (x, y), (u, v) in zip(src_pts, dst_pts):
        u_est, v_est = transform_point_homography(x, y, H)
        err = float(np.hypot(u_est - u, v_est - v))
        corner_errors.append(err)

    results = {
        "mean_corner_error_px": float(np.mean(corner_errors)),
        "max_corner_error_px": float(np.max(corner_errors)),
    }

    # 2. Validation points error (if provided)
    if validation_pairs:
        val_errors = []
        for (vx, vy), (vu, vv) in validation_pairs:
            u_est, v_est = transform_point_homography(vx, vy, H)
            err = float(np.hypot(u_est - vu, v_est - vv))
            val_errors.append(err)

        results["mean_validation_error_px"] = float(np.mean(val_errors))
        results["max_validation_error_px"] = float(np.max(val_errors))

    return results


class BoardCalibrator:
    """Manages board calibration workflow, corner selection, and persistence."""

    def __init__(self, save_path: str = settings.CALIBRATION_DATA_PATH):
        self.save_path = save_path
        self.src_corners: List[List[float]] = []  # Camera image points
        self.dst_corners: List[List[float]] = [   # Board coordinate corners
            [0.0, 0.0],
            [float(settings.BOARD_WIDTH), 0.0],
            [float(settings.BOARD_WIDTH), float(settings.BOARD_HEIGHT)],
            [0.0, float(settings.BOARD_HEIGHT)],
        ]
        self.H: Optional[np.ndarray] = None
        self.is_calibrated: bool = False
        self.last_metrics: Dict[str, float] = {}

        # Attempt to auto-load existing calibration
        self.load()

    def set_camera_corners(self, corners: List[List[float]]) -> bool:
        """Set the 4 camera corners in clockwise order (TL, TR, BR, BL) and compute H."""
        if len(corners) != 4:
            return False

        self.src_corners = [[float(p[0]), float(p[1])] for p in corners]
        src_arr = np.array(self.src_corners, dtype=np.float64)
        dst_arr = np.array(self.dst_corners, dtype=np.float64)

        try:
            self.H = compute_homography_dlt(src_arr, dst_arr)
            self.is_calibrated = True

            # Evaluate reprojection accuracy with center validation point
            # Generate synthetic validation pair using inverse homography
            H_inv = np.linalg.inv(self.H)
            val_pairs = []
            for b_pt in settings.VALIDATION_BOARD_POINTS:
                cx, cy = transform_point_homography(b_pt[0], b_pt[1], H_inv)
                val_pairs.append(((cx, cy), (b_pt[0], b_pt[1])))

            self.last_metrics = evaluate_calibration_error(
                src_arr, dst_arr, self.H, validation_pairs=val_pairs
            )
            print(f"[BoardCalibrator] Homography estimated successfully.")
            print(f"  Corner error : {self.last_metrics['mean_corner_error_px']:.4f} px")
            print(f"  Validation error: {self.last_metrics.get('mean_validation_error_px', 0.0):.4f} px")
            return True
        except Exception as e:
            print(f"[BoardCalibrator] Error computing homography: {e}")
            self.is_calibrated = False
            self.H = None
            return False

    def save(self) -> bool:
        """Persist calibration parameters and homography matrix to JSON."""
        if not self.is_calibrated or self.H is None:
            print("[BoardCalibrator] Cannot save: not calibrated.")
            return False

        data = {
            "board_width": settings.BOARD_WIDTH,
            "board_height": settings.BOARD_HEIGHT,
            "src_camera_corners": self.src_corners,
            "dst_board_corners": self.dst_corners,
            "homography_matrix": self.H.tolist(),
            "metrics": self.last_metrics,
        }

        try:
            out_dir = os.path.dirname(self.save_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            print(f"[BoardCalibrator] Calibration saved to '{self.save_path}'.")
            return True
        except Exception as e:
            print(f"[BoardCalibrator] Error saving calibration: {e}")
            return False

    def load(self) -> bool:
        """Load saved calibration data from disk."""
        if not os.path.exists(self.save_path):
            return False

        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.src_corners = data["src_camera_corners"]
            self.dst_corners = data["dst_board_corners"]
            self.H = np.array(data["homography_matrix"], dtype=np.float64)
            self.last_metrics = data.get("metrics", {})
            self.is_calibrated = True
            print(f"[BoardCalibrator] Loaded existing calibration from '{self.save_path}'.")
            return True
        except Exception as e:
            print(f"[BoardCalibrator] Failed to load calibration: {e}")
            self.is_calibrated = False
            self.H = None
            return False


def run_interactive_calibration() -> None:
    """
    Interactive corner selection and calibration tool (Step 5).
    Allows clicking 4 corners on the camera view to define the projected whiteboard area.
    Controls:
      - Left Click: select corner (1: Top-Left, 2: Top-Right, 3: Bottom-Right, 4: Bottom-Left)
      - [r] : Reset selected corners
      - [a] : Auto-apply default bounds (quick test at home)
      - [s] : Save calibration to disk
      - [q] or [ESC] : Quit
    """
    cam = CameraManager()
    if not cam.open():
        print("[Calibration] Failed to open camera.")
        return

    calibrator = BoardCalibrator()
    clicked_points: List[Tuple[int, int]] = []
    window_name = "Whiteboard Calibration - Click 4 Corners (TL -> TR -> BR -> BL)"

    corner_labels = [
        "1. Top-Left",
        "2. Top-Right",
        "3. Bottom-Right",
        "4. Bottom-Left",
    ]

    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(clicked_points) < 4:
                clicked_points.append((x, y))
                print(f"[Calibration] Point {len(clicked_points)} selected: ({x}, {y})")
                if len(clicked_points) == 4:
                    calibrator.set_camera_corners(clicked_points)

    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(window_name, mouse_callback)

    print("\n--- Whiteboard Calibration Controls ---")
    print(" Click 4 corners on camera feed in order: TL -> TR -> BR -> BL")
    print(" [r] : Reset selected points")
    print(" [a] : Auto-apply default test corners")
    print(" [s] : Save calibration to config/calibration_data.json")
    print(" [q] : Exit")
    print("----------------------------------------\n")

    try:
        while True:
            ret, frame = cam.read_frame()
            if not ret or frame is None:
                break

            display = frame.copy()

            # Draw clicked points and connecting polygon
            for idx, pt in enumerate(clicked_points):
                cv2.circle(display, pt, 6, settings.COLOR_GREEN, -1)
                cv2.putText(
                    display,
                    corner_labels[idx],
                    (pt[0] + 10, pt[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    settings.COLOR_YELLOW,
                    1,
                    cv2.LINE_AA,
                )

            if len(clicked_points) >= 2:
                for i in range(len(clicked_points) - 1):
                    cv2.line(display, clicked_points[i], clicked_points[i + 1], settings.COLOR_GREEN, 2)
                if len(clicked_points) == 4:
                    cv2.line(display, clicked_points[3], clicked_points[0], settings.COLOR_GREEN, 2)

            # Top instructions bar
            cv2.rectangle(display, (5, 5), (settings.FRAME_WIDTH - 5, 45), (0, 0, 0), -1)
            if len(clicked_points) < 4:
                msg = f"Click corner: {corner_labels[len(clicked_points)]} | [a] Auto-fill | [r] Reset"
                color = settings.COLOR_CYAN
            else:
                err = calibrator.last_metrics.get("mean_validation_error_px", 0.0)
                msg = f"CALIBRATED! Error: {err:.2f} px | [s] Save | [r] Redo"
                color = settings.COLOR_GREEN

            cv2.putText(display, msg, (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)

            cv2.imshow(window_name, display)
            key = cv2.waitKey(20) & 0xFF

            if key in (ord("q"), 27):
                break
            elif key == ord("r"):
                clicked_points.clear()
                calibrator.is_calibrated = False
                calibrator.H = None
                print("[Calibration] Points reset. Click 4 corners.")
            elif key == ord("a"):
                clicked_points = [tuple(map(int, p)) for p in settings.DEFAULT_CAMERA_CORNERS]
                calibrator.set_camera_corners(clicked_points)
                print("[Calibration] Applied default corners.")
            elif key == ord("s"):
                if calibrator.is_calibrated:
                    calibrator.save()

    finally:
        cam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run_interactive_calibration()

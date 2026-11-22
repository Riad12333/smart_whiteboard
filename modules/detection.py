"""
Pointer and skin detection module (Steps 2, 3 & 4).
Includes custom color conversion, skin calibration, morphological operations,
connected component labeling, centroid, fingertip tracking, exponential smoothing,
tremor deadzone, and tracking loss/recovery stabilization.
Part of the Smart Interactive Whiteboard project (USTHB 2026-2027).

NOTE: All computer vision algorithms (color conversion, thresholding, erosion,
dilation, opening, connected components, centroid, distance, and filtering) are
implemented from scratch using NumPy vectorization without OpenCV image processing.
OpenCV is strictly restricted to video I/O and debug GUI windows.
"""

import os
import sys
import time
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Add project root to sys.path to allow direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from config import settings
from modules.camera import CameraManager


# ==============================================================================
# 1. Color Space Conversions (from scratch using NumPy)
# ==============================================================================

def bgr_to_ycrcb_custom(bgr: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Convert BGR image to YCrCb color space from scratch using vectorized NumPy.
    Standard ITU-R BT.601 digital conversion:
      Y  =  0.2990 * R + 0.5870 * G + 0.1140 * B
      Cr =  0.5000 * R - 0.4187 * G - 0.0813 * B + 128
      Cb = -0.1687 * R - 0.3313 * G + 0.5000 * B + 128
    """
    b = bgr[:, :, 0].astype(np.float32)
    g = bgr[:, :, 1].astype(np.float32)
    r = bgr[:, :, 2].astype(np.float32)

    y = 0.2990 * r + 0.5870 * g + 0.1140 * b
    cr = 0.5000 * r - 0.4187 * g - 0.0813 * b + 128.0
    cb = -0.1687 * r - 0.3313 * g + 0.5000 * b + 128.0

    y_uint8 = np.clip(np.round(y), 0, 255).astype(np.uint8)
    cr_uint8 = np.clip(np.round(cr), 0, 255).astype(np.uint8)
    cb_uint8 = np.clip(np.round(cb), 0, 255).astype(np.uint8)

    return y_uint8, cr_uint8, cb_uint8


def bgr_to_hsv_custom(bgr: np.ndarray) -> np.ndarray:
    """
    Convert BGR image to HSV color space from scratch using vectorized NumPy.
    Output conforms to OpenCV standard ranges: H in [0, 179], S in [0, 255], V in [0, 255].
    """
    b = bgr[:, :, 0].astype(np.float32) / 255.0
    g = bgr[:, :, 1].astype(np.float32) / 255.0
    r = bgr[:, :, 2].astype(np.float32) / 255.0

    v = np.maximum(np.maximum(r, g), b)
    m = np.minimum(np.minimum(r, g), b)
    delta = v - m

    s = np.where(v > 0.0, (delta / np.where(v > 0.0, v, 1.0)) * 255.0, 0.0)

    h = np.zeros_like(v)
    mask_delta = delta > 1e-6

    mask_r = mask_delta & (v == r)
    mask_g = mask_delta & (v == g) & (~mask_r)
    mask_b = mask_delta & (v == b) & (~mask_r) & (~mask_g)

    h[mask_r] = (60.0 * ((g[mask_r] - b[mask_r]) / delta[mask_r])) % 360.0
    h[mask_g] = 60.0 * ((b[mask_g] - r[mask_g]) / delta[mask_g] + 2.0)
    h[mask_b] = 60.0 * ((r[mask_b] - g[mask_b]) / delta[mask_b] + 4.0)

    h_scaled = np.round(h / 2.0)

    hsv = np.stack(
        [
            np.clip(h_scaled, 0, 179).astype(np.uint8),
            np.clip(np.round(s), 0, 255).astype(np.uint8),
            np.clip(np.round(v * 255.0), 0, 255).astype(np.uint8),
        ],
        axis=-1,
    )
    return hsv


# ==============================================================================
# 2. Color Segmentation & Adaptive Calibration
# ==============================================================================

def segment_skin_custom(
    bgr: np.ndarray,
    cr_min: int = settings.SKIN_CR_MIN,
    cr_max: int = settings.SKIN_CR_MAX,
    cb_min: int = settings.SKIN_CB_MIN,
    cb_max: int = settings.SKIN_CB_MAX,
) -> np.ndarray:
    """Threshold skin pixels in YCrCb color space using pure NumPy logical indexing."""
    _, cr, cb = bgr_to_ycrcb_custom(bgr)
    skin_mask = (cr >= cr_min) & (cr <= cr_max) & (cb >= cb_min) & (cb <= cb_max)
    return (skin_mask * 255).astype(np.uint8)


def segment_marker_custom(
    bgr: np.ndarray,
    h_min: int = settings.MARKER_H_MIN,
    h_max: int = settings.MARKER_H_MAX,
    s_min: int = settings.MARKER_S_MIN,
    s_max: int = settings.MARKER_S_MAX,
    v_min: int = settings.MARKER_V_MIN,
    v_max: int = settings.MARKER_V_MAX,
) -> np.ndarray:
    """Threshold colored marker pixels in HSV color space using pure NumPy."""
    hsv = bgr_to_hsv_custom(bgr)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

    if h_min <= h_max:
        h_mask = (h >= h_min) & (h <= h_max)
    else:
        h_mask = (h >= h_min) | (h <= h_max)

    marker_mask = h_mask & (s >= s_min) & (s <= s_max) & (v >= v_min) & (v <= v_max)
    return (marker_mask * 255).astype(np.uint8)


class SkinColorCalibrator:
    """Adaptive skin calibrator using Gaussian confidence bounds (mean +- k*std)."""

    def __init__(self, k_std: float = settings.CALIB_K_STD):
        self.k_std = k_std
        self.is_calibrated: bool = False
        self.cr_min: int = settings.SKIN_CR_MIN
        self.cr_max: int = settings.SKIN_CR_MAX
        self.cb_min: int = settings.SKIN_CB_MIN
        self.cb_max: int = settings.SKIN_CB_MAX
        self.mean_cr = self.std_cr = self.mean_cb = self.std_cb = 0.0

    def calibrate_from_roi(self, roi_bgr: np.ndarray) -> Dict[str, float]:
        if roi_bgr.size == 0:
            return {}

        _, cr, cb = bgr_to_ycrcb_custom(roi_bgr)
        self.mean_cr = float(np.mean(cr))
        self.std_cr = float(np.std(cr))
        self.mean_cb = float(np.mean(cb))
        self.std_cb = float(np.std(cb))

        margin_cr = max(self.k_std * self.std_cr, 8.0)
        margin_cb = max(self.k_std * self.std_cb, 8.0)

        self.cr_min = int(max(0, np.floor(self.mean_cr - margin_cr)))
        self.cr_max = int(min(255, np.ceil(self.mean_cr + margin_cr)))
        self.cb_min = int(max(0, np.floor(self.mean_cb - margin_cb)))
        self.cb_max = int(min(255, np.ceil(self.mean_cb + margin_cb)))
        self.is_calibrated = True

        stats = {
            "mean_cr": self.mean_cr, "std_cr": self.std_cr,
            "mean_cb": self.mean_cb, "std_cb": self.std_cb,
            "cr_min": self.cr_min, "cr_max": self.cr_max,
            "cb_min": self.cb_min, "cb_max": self.cb_max,
        }
        print(f"[SkinCalibrator] Calibrated: Cr=[{self.cr_min}, {self.cr_max}] Cb=[{self.cb_min}, {self.cb_max}]")
        return stats

    def reset_to_defaults(self) -> None:
        self.cr_min = settings.SKIN_CR_MIN
        self.cr_max = settings.SKIN_CR_MAX
        self.cb_min = settings.SKIN_CB_MIN
        self.cb_max = settings.SKIN_CB_MAX
        self.is_calibrated = False

    def get_thresholds(self) -> Tuple[int, int, int, int]:
        return self.cr_min, self.cr_max, self.cb_min, self.cb_max


# ==============================================================================
# 3. Custom Mathematical Morphology (Erosion, Dilation, Opening)
# ==============================================================================

def erode_custom(binary_mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    """
    Binary erosion implemented from scratch using vectorized NumPy sliding slices.
    Erosion with a 3x3 square structuring element:
      output[y, x] = 255 iff ALL 8-connected neighbors are 255.
    """
    res = binary_mask
    h, w = binary_mask.shape[:2]
    for _ in range(iterations):
        pad = np.pad(res, 1, mode="constant", constant_values=0)
        shifted = [pad[1 + dy : h + 1 + dy, 1 + dx : w + 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
        res = np.bitwise_and.reduce(shifted)
    return res


def dilate_custom(binary_mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    """
    Binary dilation implemented from scratch using vectorized NumPy sliding slices.
    Dilation with a 3x3 square structuring element:
      output[y, x] = 255 iff AT LEAST ONE 8-connected neighbor is 255.
    """
    res = binary_mask
    h, w = binary_mask.shape[:2]
    for _ in range(iterations):
        pad = np.pad(res, 1, mode="constant", constant_values=0)
        shifted = [pad[1 + dy : h + 1 + dy, 1 + dx : w + 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
        res = np.bitwise_or.reduce(shifted)
    return res


def morph_open_custom(binary_mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    """
    Morphological Opening: Erosion followed by Dilation.
    Eliminates small noisy speckles while preserving the shape and size of large objects.
    """
    return dilate_custom(erode_custom(binary_mask, iterations=iterations), iterations=iterations)


# ==============================================================================
# 4. Connected Component Labeling & Fingertip Extraction
# ==============================================================================

def find_largest_connected_component(
    binary_mask: np.ndarray,
    downscale: int = settings.CCL_DOWNSCALE,
) -> Tuple[np.ndarray, np.ndarray, int]:
    """
    Extract the largest connected component from scratch using BFS flood-fill
    executed on a downscaled grid for high-speed real-time performance (> 100 FPS).
    """
    sub_mask = binary_mask[::downscale, ::downscale]
    sh, sw = sub_mask.shape

    visited = np.zeros((sh, sw), dtype=bool)
    active_indices = np.argwhere(sub_mask > 0)

    if len(active_indices) == 0:
        return np.array([], dtype=int), np.array([], dtype=int), 0

    largest_points: List[Tuple[int, int]] = []

    for r, c in active_indices:
        if not visited[r, c]:
            component = []
            queue = [(r, c)]
            visited[r, c] = True

            while queue:
                cr, cc = queue.pop()
                component.append((cr, cc))

                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < sh and 0 <= nc < sw and not visited[nr, nc] and sub_mask[nr, nc] > 0:
                        visited[nr, nc] = True
                        queue.append((nr, nc))

            if len(component) > len(largest_points):
                largest_points = component

    if not largest_points:
        return np.array([], dtype=int), np.array([], dtype=int), 0

    sub_pts = np.array(largest_points, dtype=np.int32)
    y_full = sub_pts[:, 0] * downscale
    x_full = sub_pts[:, 1] * downscale
    estimated_area = int(len(largest_points) * (downscale**2))

    return y_full, x_full, estimated_area


def compute_centroid(x_coords: np.ndarray, y_coords: np.ndarray) -> Tuple[float, float]:
    """Compute the centroid (arithmetic mean) of the component pixels."""
    if len(x_coords) == 0:
        return 0.0, 0.0
    return float(np.mean(x_coords)), float(np.mean(y_coords))


def find_fingertip(
    x_coords: np.ndarray,
    y_coords: np.ndarray,
    cx: float,
    cy: float,
    method: str = settings.FINGERTIP_METHOD,
) -> Tuple[float, float]:
    """
    Locate the tip of the pointing index finger within the segmented hand region.
    Methods: "FARTHEST" (arg max dist^2 from centroid) or "HIGHEST" (min Y).
    """
    if len(x_coords) == 0:
        return 0.0, 0.0

    if method == "HIGHEST":
        idx = int(np.argmin(y_coords))
        return float(x_coords[idx]), float(y_coords[idx])

    dist_sq = (x_coords - cx) ** 2 + (y_coords - cy) ** 2
    idx = int(np.argmax(dist_sq))
    return float(x_coords[idx]), float(y_coords[idx])


# ==============================================================================
# 5. Pointer Stabilizer (Step 4: EMA, Deadzone, Loss & Reacquisition)
# ==============================================================================

class PointerStabilizer:
    """
    Temporal stabilization filter for pointer tracking.
    Applies:
      1. Deadzone thresholding to completely suppress physiological hand tremor.
      2. Exponential Moving Average (EMA): P = alpha * P_new + (1 - alpha) * P_prev.
      3. Multi-frame loss detection and instant reacquisition upon reappearance.
      4. Numerical metrics tracking for experimental report validation.
    """

    def __init__(
        self,
        alpha: float = settings.SMOOTHING_ALPHA,
        deadzone: float = settings.DEADZONE_RADIUS,
        max_lost_frames: int = settings.MAX_LOST_FRAMES,
    ):
        self.alpha = alpha
        self.deadzone = deadzone
        self.max_lost_frames = max_lost_frames

        # Current stabilized coordinates
        self.smooth_x: float = 0.0
        self.smooth_y: float = 0.0
        self.is_active: bool = False
        self.consecutive_lost_frames: int = 0

        # Performance and jitter metrics history
        self.raw_history_x: deque = deque(maxlen=100)
        self.raw_history_y: deque = deque(maxlen=100)
        self.smooth_history_x: deque = deque(maxlen=100)
        self.smooth_history_y: deque = deque(maxlen=100)

        self.total_frames: int = 0
        self.detected_frames: int = 0

    def update(
        self, raw_pointer: Dict[str, Union[bool, float, int]]
    ) -> Dict[str, Union[bool, float, int]]:
        """
        Process raw detection through stabilization filters and return standard format.
        """
        self.total_frames += 1

        if not raw_pointer["detected"]:
            self.consecutive_lost_frames += 1
            if self.consecutive_lost_frames >= self.max_lost_frames:
                self.is_active = False

            return {
                "detected": False,
                "x": self.smooth_x if self.is_active else 0.0,
                "y": self.smooth_y if self.is_active else 0.0,
                "raw_x": 0.0,
                "raw_y": 0.0,
                "area": 0,
            }

        # Pointer is detected in this frame
        self.detected_frames += 1
        rx = float(raw_pointer["raw_x"])
        ry = float(raw_pointer["raw_y"])
        area = int(raw_pointer["area"])

        if not self.is_active:
            # Immediate reacquisition: initialize smoothed point to raw point (no dead-space drag)
            self.smooth_x = rx
            self.smooth_y = ry
            self.is_active = True
            self.consecutive_lost_frames = 0
        else:
            self.consecutive_lost_frames = 0
            # Calculate displacement from previous stabilized position
            displacement = float(np.hypot(rx - self.smooth_x, ry - self.smooth_y))

            # Deadzone check: suppress small tremors
            if displacement < self.deadzone:
                # Keep previous position; jitter ignored
                pass
            else:
                # Exponential Moving Average (EMA)
                self.smooth_x = self.alpha * rx + (1.0 - self.alpha) * self.smooth_x
                self.smooth_y = self.alpha * ry + (1.0 - self.alpha) * self.smooth_y

        # Log histories for metric calculation
        self.raw_history_x.append(rx)
        self.raw_history_y.append(ry)
        self.smooth_history_x.append(self.smooth_x)
        self.smooth_history_y.append(self.smooth_y)

        # Standard output exchange dictionary
        result: Dict[str, Union[bool, float, int]] = {
            "detected": True,
            "x": float(self.smooth_x),
            "y": float(self.smooth_y),
            "raw_x": float(rx),
            "raw_y": float(ry),
            "area": area,
        }

        # Preserve centroid for visualization if available
        if "cx" in raw_pointer and "cy" in raw_pointer:
            result["cx"] = float(raw_pointer["cx"])
            result["cy"] = float(raw_pointer["cy"])

        return result

    def get_stability_metrics(self) -> Dict[str, float]:
        """
        Compute empirical stability metrics over recent history:
          - std_raw: raw jitter standard deviation (pixels)
          - std_smooth: smoothed jitter standard deviation (pixels)
          - jitter_reduction_pct: percentage jitter attenuation
          - detection_rate_pct: percentage of frames successfully tracked
        """
        if len(self.raw_history_x) < 5:
            return {
                "std_raw": 0.0,
                "std_smooth": 0.0,
                "jitter_reduction_pct": 0.0,
                "detection_rate_pct": (
                    (self.detected_frames / self.total_frames * 100.0)
                    if self.total_frames > 0
                    else 0.0
                ),
            }

        # Compute Euclidean distance standard deviation around empirical mean
        rx_arr = np.array(self.raw_history_x)
        ry_arr = np.array(self.raw_history_y)
        sx_arr = np.array(self.smooth_history_x)
        sy_arr = np.array(self.smooth_history_y)

        std_raw = float(np.hypot(np.std(rx_arr), np.std(ry_arr)))
        std_smooth = float(np.hypot(np.std(sx_arr), np.std(sy_arr)))

        reduction = (
            ((std_raw - std_smooth) / std_raw * 100.0) if std_raw > 1e-4 else 0.0
        )
        det_rate = (
            (self.detected_frames / self.total_frames * 100.0)
            if self.total_frames > 0
            else 0.0
        )

        return {
            "std_raw": std_raw,
            "std_smooth": std_smooth,
            "jitter_reduction_pct": max(0.0, reduction),
            "detection_rate_pct": det_rate,
        }

    def reset(self) -> None:
        """Reset internal filter state."""
        self.smooth_x = 0.0
        self.smooth_y = 0.0
        self.is_active = False
        self.consecutive_lost_frames = 0
        self.raw_history_x.clear()
        self.raw_history_y.clear()
        self.smooth_history_x.clear()
        self.smooth_history_y.clear()


# ==============================================================================
# 6. High-Level Detection Pipeline Function
# ==============================================================================

def detect_pointer(
    frame_bgr: np.ndarray,
    calibrator: Optional[SkinColorCalibrator] = None,
    mode: str = "SKIN",
    fingertip_method: str = settings.FINGERTIP_METHOD,
    stabilizer: Optional[PointerStabilizer] = None,
) -> Tuple[Dict[str, Union[bool, float, int]], np.ndarray]:
    """
    End-to-end pointer detection and stabilization pipeline:
      1. Color segmentation (YCrCb skin or HSV marker).
      2. Custom morphological opening.
      3. Connected components on decimated grid.
      4. Centroid & fingertip extraction.
      5. Temporal stabilization (EMA + Deadzone) if stabilizer is provided.

    Returns: (pointer_dict, clean_mask)
    """
    # 1. Color thresholding
    if mode == "SKIN":
        if calibrator is not None:
            cr_min, cr_max, cb_min, cb_max = calibrator.get_thresholds()
        else:
            cr_min, cr_max, cb_min, cb_max = (
                settings.SKIN_CR_MIN,
                settings.SKIN_CR_MAX,
                settings.SKIN_CB_MIN,
                settings.SKIN_CB_MAX,
            )
        raw_mask = segment_skin_custom(frame_bgr, cr_min, cr_max, cb_min, cb_max)
    else:
        raw_mask = segment_marker_custom(frame_bgr)

    # 2. Morphological opening
    clean_mask = morph_open_custom(raw_mask, iterations=settings.MORPH_ITERATIONS)

    # 3. Connected components
    y_pts, x_pts, area = find_largest_connected_component(
        clean_mask, downscale=settings.CCL_DOWNSCALE
    )

    # 4. Area check
    if area < settings.MIN_CONTOUR_AREA or len(x_pts) == 0:
        raw_pointer = {
            "detected": False,
            "x": 0.0,
            "y": 0.0,
            "raw_x": 0.0,
            "raw_y": 0.0,
            "area": area,
        }
    else:
        cx, cy = compute_centroid(x_pts, y_pts)
        fx, fy = find_fingertip(x_pts, y_pts, cx, cy, method=fingertip_method)

        raw_pointer = {
            "detected": True,
            "x": float(fx),
            "y": float(fy),
            "raw_x": float(fx),
            "raw_y": float(fy),
            "area": int(area),
            "cx": float(cx),
            "cy": float(cy),
        }

    # 5. Temporal stabilization
    if stabilizer is not None:
        pointer = stabilizer.update(raw_pointer)
    else:
        pointer = raw_pointer

    return pointer, clean_mask


# ==============================================================================
# 7. Interactive Test & Preview Execution (Step 4)
# ==============================================================================

def run_detection_step4() -> None:
    """
    Interactive test preview for Step 4.
    Displays real-time tracking, dual-pointer visualization (raw vs stabilized),
    and live quantitative stability metrics for the project report.
    """
    cam = CameraManager()
    if not cam.open():
        print("[Step 4] Error: Unable to open camera source.")
        return

    calibrator = SkinColorCalibrator(k_std=settings.CALIB_K_STD)
    stabilizer = PointerStabilizer(
        alpha=settings.SMOOTHING_ALPHA,
        deadzone=settings.DEADZONE_RADIUS,
        max_lost_frames=settings.MAX_LOST_FRAMES,
    )

    mode = settings.DETECTION_MODE_DEFAULT
    fingertip_method = settings.FINGERTIP_METHOD

    roi_size = settings.CALIB_ROI_SIZE
    roi_x = (settings.FRAME_WIDTH - roi_size) // 2
    roi_y = (settings.FRAME_HEIGHT - roi_size) // 2

    window_preview = "Step 4: Stabilized Pointer Tracking"
    window_mask = "Morphologically Cleaned Mask"

    cv2.namedWindow(window_preview, cv2.WINDOW_AUTOSIZE)
    cv2.namedWindow(window_mask, cv2.WINDOW_AUTOSIZE)

    print("\n================ Step 4 Controls ================")
    print(" [c] : Calibrate skin color from center square ROI")
    print(" [d] : Reset skin thresholds to default fallback")
    print(" [m] : Toggle mode (SKIN YCrCb <-> MARKER HSV)")
    print(" [f] : Toggle fingertip method (FARTHEST <-> HIGHEST)")
    print(" [s] : Print stability metrics report to console")
    print(" [q] or [ESC] : Quit")
    print("==================================================\n")

    fps_list = []

    try:
        while True:
            ret, frame = cam.read_frame()
            if not ret or frame is None:
                break

            fps = cam.get_fps()
            if fps > 0:
                fps_list.append(fps)

            roi = frame[roi_y : roi_y + roi_size, roi_x : roi_x + roi_size]

            pointer, mask = detect_pointer(
                frame,
                calibrator=calibrator,
                mode=mode,
                fingertip_method=fingertip_method,
                stabilizer=stabilizer,
            )

            metrics = stabilizer.get_stability_metrics()

            # Draw calibration square if uncalibrated
            if not calibrator.is_calibrated and mode == "SKIN":
                cv2.rectangle(
                    frame,
                    (roi_x, roi_y),
                    (roi_x + roi_size, roi_y + roi_size),
                    settings.COLOR_CYAN,
                    1,
                )
                cv2.putText(
                    frame,
                    "Calib: press 'c'",
                    (roi_x - 30, roi_y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    settings.COLOR_CYAN,
                    1,
                )

            # Visual overlay
            if pointer["detected"]:
                # Raw point (faint gray)
                rx, ry = int(pointer["raw_x"]), int(pointer["raw_y"])
                cv2.circle(frame, (rx, ry), 5, settings.COLOR_GRAY, 1)

                # Centroid (blue)
                if "cx" in pointer and "cy" in pointer:
                    cx, cy = int(pointer["cx"]), int(pointer["cy"])
                    cv2.circle(frame, (cx, cy), 6, settings.COLOR_BLUE, -1)
                    cv2.line(frame, (cx, cy), (rx, ry), settings.COLOR_YELLOW, 1)

                # Stabilized pointer (bold Red with green target ring)
                sx, sy = int(pointer["x"]), int(pointer["y"])
                cv2.circle(frame, (sx, sy), 8, settings.COLOR_RED, -1)
                cv2.circle(frame, (sx, sy), 16, settings.COLOR_GREEN, 2)
                cv2.drawMarker(
                    frame, (sx, sy), settings.COLOR_RED, cv2.MARKER_CROSS, 20, 2
                )

                hud_tracking = (
                    f"STABILIZED: ({sx:3d}, {sy:3d}) | Raw: ({rx:3d}, {ry:3d})"
                )
            else:
                hud_tracking = "SEARCHING / LOST"

            # Top HUD bar 1: System info & tracking
            cv2.rectangle(frame, (5, 5), (settings.FRAME_WIDTH - 5, 42), (0, 0, 0), -1)
            cv2.putText(
                frame,
                f"FPS: {fps:4.1f} | Mode: {mode} | {hud_tracking}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                settings.COLOR_GREEN if pointer["detected"] else settings.COLOR_RED,
                1,
                cv2.LINE_AA,
            )

            # Bottom HUD bar 2: Quantitative Stability Metrics for the report
            cv2.rectangle(
                frame, (5, settings.FRAME_HEIGHT - 35), (settings.FRAME_WIDTH - 5, settings.FRAME_HEIGHT - 5), (0, 0, 0), -1
            )
            cv2.putText(
                frame,
                f"Jitter Std: raw={metrics['std_raw']:.2f}px -> smooth={metrics['std_smooth']:.2f}px (-{metrics['jitter_reduction_pct']:.0f}%) | Det: {metrics['detection_rate_pct']:.0f}%",
                (10, settings.FRAME_HEIGHT - 13),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                settings.COLOR_YELLOW,
                1,
                cv2.LINE_AA,
            )

            cv2.imshow(window_preview, frame)
            cv2.imshow(window_mask, mask)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            elif key == ord("c"):
                calibrator.calibrate_from_roi(roi)
            elif key == ord("d"):
                calibrator.reset_to_defaults()
            elif key == ord("m"):
                mode = "MARKER" if mode == "SKIN" else "SKIN"
                print(f"[Step 4] Switched detection mode to: {mode}")
            elif key == ord("f"):
                fingertip_method = "HIGHEST" if fingertip_method == "FARTHEST" else "FARTHEST"
                print(f"[Step 4] Switched fingertip method to: {fingertip_method}")
            elif key == ord("s"):
                print("\n--- Live Stability Metrics Snapshot ---")
                print(f" Raw Jitter Std Dev      : {metrics['std_raw']:.3f} px")
                print(f" Stabilized Jitter Std   : {metrics['std_smooth']:.3f} px")
                print(f" Jitter Noise Reduction  : {metrics['jitter_reduction_pct']:.1f} %")
                print(f" Detection Success Rate  : {metrics['detection_rate_pct']:.1f} %")
                print("----------------------------------------\n")

    finally:
        cam.release()
        cv2.destroyAllWindows()

    if fps_list:
        print("\n================ Step 4 Performance Report ================")
        print(f" Mean FPS               : {np.mean(fps_list):.2f}")
        print(f" FPS Std Dev            : {np.std(fps_list):.2f}")
        final_metrics = stabilizer.get_stability_metrics()
        print(f" Raw Jitter Std Dev     : {final_metrics['std_raw']:.3f} px")
        print(f" Stabilized Jitter Std  : {final_metrics['std_smooth']:.3f} px")
        print(f" Jitter Noise Reduction : {final_metrics['jitter_reduction_pct']:.1f} %")
        print(f" Detection Success Rate : {final_metrics['detection_rate_pct']:.1f} %")
        print("===========================================================\n")


if __name__ == "__main__":
    run_detection_step4()

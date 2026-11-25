"""
Machine Learning Hand Detection Module (Step 4quinquies).
Utilizes lightweight MediaPipe Palm Detection and HandPose Estimation ONNX models
executed via native OpenCV DNN (cv2.dnn.readNet) without external mediapipe package.

Features:
- Palm detection + 21 3D landmarks regression
- Pointing tip tracking at Landmark 8 (Index Finger Tip)
- Multi-hand tracking with spatial continuity or highest confidence arbitration
- Configurable pointing gesture requirement (index extended, other fingers folded)
- Board polygon boundary confinement
- Handcrafted 1€ (One Euro) filter and EMA smoothing with jitter deadzone
- Real model confidence telemetry and execution time profiling (>20 FPS)
"""

import math
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from config import settings
from modules.ml.mp_palmdet import MPPalmDet
from modules.ml.mp_handpose import MPHandPose


# ==============================================================================
# 1. Temporal Smoothing Filters (1€ Filter & EMA from scratch)
# ==============================================================================

class LowPassFilter:
    """Simple first-order exponential low-pass filter."""

    def __init__(self, alpha: float = 1.0):
        self.alpha: float = alpha
        self.y_prev: Optional[float] = None

    def filter(self, x: float, alpha: Optional[float] = None) -> float:
        if alpha is not None:
            self.alpha = alpha
        if self.y_prev is None:
            s = x
        else:
            s = self.alpha * x + (1.0 - self.alpha) * self.y_prev
        self.y_prev = s
        return s

    def reset(self):
        self.y_prev = None


class OneEuroFilter:
    """
    Casiez et al. (CHI 2012) 1€ Filter.
    Adapts cutoff frequency based on movement speed:
    - Low velocity: low cutoff frequency (heavy smoothing, eliminates hand tremor).
    - High velocity: high cutoff frequency (near-zero latency, fast pointer responsiveness).
    """

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ):
        self.min_cutoff: float = min_cutoff
        self.beta: float = beta
        self.d_cutoff: float = d_cutoff

        self.x_filter = LowPassFilter()
        self.dx_filter = LowPassFilter()
        self.t_prev: Optional[float] = None
        self.x_prev: Optional[float] = None

    def _alpha(self, cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filter(self, x: float, t: Optional[float] = None) -> float:
        if t is None:
            t = time.perf_counter()

        if self.t_prev is None or (t - self.t_prev) <= 0.0:
            dt = 1.0 / 60.0
        else:
            dt = max(1e-4, t - self.t_prev)
        self.t_prev = t

        # Estimate derivative (speed of movement)
        if self.x_prev is None:
            dx = 0.0
        else:
            dx = (x - self.x_prev) / dt
        self.x_prev = x

        # Filter derivative
        a_d = self._alpha(self.d_cutoff, dt)
        dx_hat = self.dx_filter.filter(dx, a_d)

        # Compute dynamic cutoff frequency
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self._alpha(cutoff, dt)

        return self.x_filter.filter(x, a)

    def reset(self):
        self.x_filter.reset()
        self.dx_filter.reset()
        self.t_prev = None
        self.x_prev = None


class PointFilter2D:
    """2D coordinator for One Euro Filter or EMA with deadzone jitter suppression."""

    def __init__(
        self,
        filter_type: str = "ONE_EURO",
        deadzone: float = 3.5,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
        ema_alpha: float = 0.35,
    ):
        self.filter_type = filter_type.upper()
        self.deadzone = deadzone
        self.ema_alpha = ema_alpha

        self.fx = OneEuroFilter(min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)
        self.fy = OneEuroFilter(min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)

        self.last_smoothed_x: Optional[float] = None
        self.last_smoothed_y: Optional[float] = None

    def update(self, raw_x: float, raw_y: float, timestamp: Optional[float] = None) -> Tuple[float, float]:
        if self.last_smoothed_x is None or self.last_smoothed_y is None:
            # First acquisition: jump directly to initial measurement
            self.last_smoothed_x = raw_x
            self.last_smoothed_y = raw_y
            self.fx.filter(raw_x, timestamp)
            self.fy.filter(raw_y, timestamp)
            return raw_x, raw_y

        # Deadzone tremor check
        dx = raw_x - self.last_smoothed_x
        dy = raw_y - self.last_smoothed_y
        dist = math.hypot(dx, dy)

        if dist < self.deadzone:
            # Sub-threshold tremor: freeze smoothed coordinate
            return self.last_smoothed_x, self.last_smoothed_y

        if self.filter_type == "ONE_EURO":
            sm_x = self.fx.filter(raw_x, timestamp)
            sm_y = self.fy.filter(raw_y, timestamp)
        else:
            # EMA fallback
            sm_x = self.ema_alpha * raw_x + (1.0 - self.ema_alpha) * self.last_smoothed_x
            sm_y = self.ema_alpha * raw_y + (1.0 - self.ema_alpha) * self.last_smoothed_y

        self.last_smoothed_x = sm_x
        self.last_smoothed_y = sm_y
        return sm_x, sm_y

    def reset(self):
        self.fx.reset()
        self.fy.reset()
        self.last_smoothed_x = None
        self.last_smoothed_y = None


# ==============================================================================
# 2. Hand Gesture & Geometric Validation
# ==============================================================================

def verify_pointing_posture(landmarks: np.ndarray) -> bool:
    """
    Validate whether the detected hand is in an index-pointing posture.
    MediaPipe Hand Landmark topology:
      - 0: WRIST
      - Index: 5 (MCP), 6 (PIP), 7 (DIP), 8 (TIP)
      - Middle: 9 (MCP), 10 (PIP), 11 (DIP), 12 (TIP)
      - Ring: 13 (MCP), 14 (PIP), 15 (DIP), 16 (TIP)
      - Pinky: 17 (MCP), 18 (PIP), 19 (DIP), 20 (TIP)

    Criteria (rotation- and scale-invariant distance ratios to wrist):
      1. Index finger is extended: dist(8, 0) > dist(6, 0)
      2. Middle finger is folded:   dist(12, 0) < dist(10, 0)
      3. Ring finger is folded:     dist(16, 0) < dist(14, 0)
      4. Pinky finger is folded:    dist(20, 0) < dist(18, 0)
    """
    wrist = landmarks[0, :2]

    def d_wrist(idx: int) -> float:
        pt = landmarks[idx, :2]
        return math.hypot(pt[0] - wrist[0], pt[1] - wrist[1])

    # Index must be fully extended
    index_extended = d_wrist(8) > d_wrist(6)

    # Other three primary fingers must be folded
    middle_folded = d_wrist(12) < d_wrist(10)
    ring_folded = d_wrist(16) < d_wrist(14)
    pinky_folded = d_wrist(20) < d_wrist(18)

    return bool(index_extended and middle_folded and ring_folded and pinky_folded)


# ==============================================================================
# 3. HandMLDetector Class
# ==============================================================================

class HandMLDetector:
    """
    OpenCV Zoo DNN Hand Detector.
    Runs MediaPipe Palm Detection + Handpose Estimation pipeline via cv2.dnn.
    Conforms strictly to the exchange format:
      {"detected": bool, "x": float, "y": float, "raw_x": float, "raw_y": float, "area": int}
    along with 'landmarks', 'score', 'box', 'pointing', and 'inference_time_ms'.
    """

    def __init__(
        self,
        palm_model_path: Optional[str] = None,
        hand_model_path: Optional[str] = None,
        palm_score_thresh: Optional[float] = None,
        hand_score_thresh: Optional[float] = None,
        nms_thresh: Optional[float] = None,
        require_pointing: Optional[bool] = None,
        detect_every_n: Optional[int] = None,
        downscale_factor: Optional[float] = None,
        board_margin: Optional[float] = None,
        filter_type: Optional[str] = None,
    ):
        self.palm_model_path = palm_model_path or getattr(settings, "HAND_ML_PALM_MODEL_PATH", "assets/models/palm_detection_mediapipe_2023feb.onnx")
        self.hand_model_path = hand_model_path or getattr(settings, "HAND_ML_HAND_MODEL_PATH", "assets/models/handpose_estimation_mediapipe_2023feb.onnx")

        # Verify model files presence
        if not os.path.exists(self.palm_model_path) or not os.path.exists(self.hand_model_path):
            raise FileNotFoundError(
                f"[HandMLDetector] ONNX models not found!\n"
                f"  Missing: '{self.palm_model_path}' or '{self.hand_model_path}'\n"
                f"  Run 'python tools/download_models.py' to download official OpenCV Zoo models."
            )

        self.palm_score_thresh = palm_score_thresh if palm_score_thresh is not None else getattr(settings, "HAND_ML_PALM_SCORE_THRESH", 0.6)
        self.hand_score_thresh = hand_score_thresh if hand_score_thresh is not None else getattr(settings, "HAND_ML_HAND_SCORE_THRESH", 0.7)
        self.nms_thresh = nms_thresh if nms_thresh is not None else getattr(settings, "HAND_ML_NMS_THRESH", 0.3)

        self.require_pointing = require_pointing if require_pointing is not None else getattr(settings, "HAND_ML_REQUIRE_POINTING", False)
        self.detect_every_n = max(1, detect_every_n if detect_every_n is not None else getattr(settings, "HAND_ML_DETECT_EVERY_N", 1))
        self.downscale_factor = downscale_factor if downscale_factor is not None else getattr(settings, "HAND_ML_DOWNSCALE_FACTOR", 1.0)
        self.board_margin = board_margin if board_margin is not None else getattr(settings, "HAND_ML_BOARD_MARGIN", 30.0)

        # Instantiate OpenCV Zoo wrappers
        self.palm_detector = MPPalmDet(
            modelPath=self.palm_model_path,
            nmsThreshold=self.nms_thresh,
            scoreThreshold=self.palm_score_thresh,
        )
        self.hand_pose = MPHandPose(
            modelPath=self.hand_model_path,
            confThreshold=self.hand_score_thresh,
        )

        # Smoothing & tracking state
        self.filter_type = filter_type or getattr(settings, "HAND_ML_FILTER_TYPE", "ONE_EURO")
        deadzone = getattr(settings, "DEADZONE_RADIUS", 3.5)
        min_cutoff = getattr(settings, "HAND_ML_ONE_EURO_MIN_CUTOFF", 1.0)
        beta = getattr(settings, "HAND_ML_ONE_EURO_BETA", 0.007)
        d_cutoff = getattr(settings, "HAND_ML_ONE_EURO_D_CUTOFF", 1.0)
        ema_alpha = getattr(settings, "SMOOTHING_ALPHA", 0.35)

        self.point_filter = PointFilter2D(
            filter_type=self.filter_type,
            deadzone=deadzone,
            min_cutoff=min_cutoff,
            beta=beta,
            d_cutoff=d_cutoff,
            ema_alpha=ema_alpha,
        )

        self.max_lost_frames = getattr(settings, "MAX_LOST_FRAMES", 5)
        self.lost_frames_count: int = 0
        self.last_pos: Optional[Tuple[float, float]] = None
        self.last_raw_pos: Optional[Tuple[float, float]] = None
        self.last_box: Optional[np.ndarray] = None
        self.frame_count: int = 0
        self.board_polygon: Optional[np.ndarray] = None

    def set_board_polygon(self, polygon: Union[np.ndarray, List[List[float]]]):
        """Set 4 corners of calibrated board in camera coordinates for polygon boundary check."""
        if polygon is not None and len(polygon) >= 3:
            self.board_polygon = np.array(polygon, dtype=np.int32)
        else:
            self.board_polygon = None

    def _is_inside_board(self, x: float, y: float) -> bool:
        """Check if point (x, y) is inside board polygon with configured margin."""
        if self.board_polygon is None:
            return True
        dist = cv2.pointPolygonTest(self.board_polygon, (float(x), float(y)), measureDist=True)
        return dist >= -self.board_margin

    def detect(self, frame_bgr: np.ndarray) -> Dict:
        """
        Process a single BGR camera frame and locate hand/index pointer.
        Returns dictionary conforming strictly to the exchange format.
        """
        t0 = time.perf_counter()
        self.frame_count += 1

        h_orig, w_orig = frame_bgr.shape[:2]

        # Resolution scaling
        scale = self.downscale_factor
        if scale != 1.0 and scale > 0.1:
            frame_input = cv2.resize(frame_bgr, (int(w_orig * scale), int(h_orig * scale)))
        else:
            frame_input = frame_bgr

        # Palm detection
        palms = self.palm_detector.infer(frame_input)

        selected_hand = None
        best_candidate = None

        if len(palms) > 0:
            candidates = []
            for palm in palms:
                # Handpose regression
                hand_res = self.hand_pose.infer(frame_input, palm)
                if hand_res is None:
                    continue

                bbox_coords, landmarks, conf = hand_res

                # Scale coordinates back to original frame size if downscaled
                if scale != 1.0 and scale > 0.1:
                    inv_scale = 1.0 / scale
                    bbox_coords = bbox_coords * inv_scale
                    landmarks[:, :2] = landmarks[:, :2] * inv_scale

                # Landmark 8: Index Finger Tip
                tip_x = float(landmarks[8, 0])
                tip_y = float(landmarks[8, 1])

                is_pointing = verify_pointing_posture(landmarks)

                candidates.append({
                    "tip_x": tip_x,
                    "tip_y": tip_y,
                    "landmarks": landmarks,
                    "bbox": bbox_coords,
                    "conf": float(conf),
                    "pointing": is_pointing
                })

            if len(candidates) > 0:
                # Filter by posture if strictly required
                if self.require_pointing:
                    pointing_candidates = [c for c in candidates if c["pointing"]]
                    if len(pointing_candidates) > 0:
                        candidates = pointing_candidates
                    else:
                        candidates = []

                # Filter by board polygon bounds
                if self.board_polygon is not None and len(candidates) > 0:
                    bounded_candidates = [c for c in candidates if self._is_inside_board(c["tip_x"], c["tip_y"])]
                    if len(bounded_candidates) > 0:
                        candidates = bounded_candidates

                # Arbitrate between multiple hands:
                # If we previously tracked a position, pick hand closest to last position;
                # otherwise pick hand with highest model confidence.
                if len(candidates) > 0:
                    if self.last_pos is not None:
                        lx, ly = self.last_pos
                        candidates.sort(key=lambda c: math.hypot(c["tip_x"] - lx, c["tip_y"] - ly))
                        best_candidate = candidates[0]
                    else:
                        candidates.sort(key=lambda c: c["conf"], reverse=True)
                        best_candidate = candidates[0]

        t_infer = (time.perf_counter() - t0) * 1000.0

        if best_candidate is not None:
            raw_x = best_candidate["tip_x"]
            raw_y = best_candidate["tip_y"]

            # Apply temporal stabilization (1€ Filter / EMA with deadzone)
            sm_x, sm_y = self.point_filter.update(raw_x, raw_y, timestamp=t0)

            bbox = best_candidate["bbox"]
            box_w = max(0.0, bbox[1][0] - bbox[0][0])
            box_h = max(0.0, bbox[1][1] - bbox[0][1])
            area = int(box_w * box_h)

            self.last_pos = (sm_x, sm_y)
            self.last_raw_pos = (raw_x, raw_y)
            self.last_box = bbox
            self.lost_frames_count = 0

            return {
                "detected": True,
                "x": float(sm_x),
                "y": float(sm_y),
                "raw_x": float(raw_x),
                "raw_y": float(raw_y),
                "area": area,
                "landmarks": best_candidate["landmarks"],
                "score": float(best_candidate["conf"]),
                "box": [float(bbox[0][0]), float(bbox[0][1]), float(bbox[1][0]), float(bbox[1][1])],
                "pointing": best_candidate["pointing"],
                "inference_time_ms": float(t_infer),
            }
        else:
            self.lost_frames_count += 1
            if self.lost_frames_count > self.max_lost_frames:
                self.last_pos = None
                self.last_raw_pos = None
                self.last_box = None
                self.point_filter.reset()

            return {
                "detected": False,
                "x": 0.0,
                "y": 0.0,
                "raw_x": 0.0,
                "raw_y": 0.0,
                "area": 0,
                "landmarks": None,
                "score": 0.0,
                "box": None,
                "pointing": False,
                "inference_time_ms": float(t_infer),
            }

    def reset(self):
        """Reset tracking state and temporal filters."""
        self.point_filter.reset()
        self.lost_frames_count = 0
        self.last_pos = None
        self.last_raw_pos = None
        self.last_box = None
        self.frame_count = 0

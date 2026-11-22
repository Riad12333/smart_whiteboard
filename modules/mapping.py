"""
Coordinate mapping module: Camera coordinates -> Whiteboard coordinates (Step 5).
Transforms detected camera pointer coordinates into projected whiteboard pixel coordinates (u, v)
using the validated 3x3 homography matrix.
Part of the Smart Interactive Whiteboard project (USTHB 2026-2027).

NOTE: The projective matrix multiplication, normalization by the third homogeneous
coordinate, and spatial clamping are implemented from scratch using NumPy.
"""

import sys
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from config import settings
from modules.calibration import BoardCalibrator, transform_point_homography


class CoordinateMapper:
    """
    Transforms camera image coordinates (x, y) into board coordinates (u, v).
    Clamps coordinates strictly within projected board bounds [0, BOARD_WIDTH] x [0, BOARD_HEIGHT].
    """

    def __init__(self, calibrator: Optional[BoardCalibrator] = None):
        self.calibrator = BoardCalibrator() if calibrator is None else calibrator

    @property
    def is_calibrated(self) -> bool:
        """Return True if a valid homography transformation is ready."""
        return self.calibrator.is_calibrated and (self.calibrator.H is not None)

    def map_point(self, x: float, y: float) -> Tuple[float, float]:
        """
        Map a single camera point (x, y) to board coordinates (u, v).
        If not calibrated, applies direct proportional scaling as a fallback.
        """
        if self.is_calibrated:
            u, v = transform_point_homography(x, y, self.calibrator.H)
        else:
            # Fallback: direct linear scaling
            u = (x / float(settings.FRAME_WIDTH)) * float(settings.BOARD_WIDTH)
            v = (y / float(settings.FRAME_HEIGHT)) * float(settings.BOARD_HEIGHT)

        # Strict clamping within board canvas boundaries
        u_clamped = max(0.0, min(float(settings.BOARD_WIDTH), float(u)))
        v_clamped = max(0.0, min(float(settings.BOARD_HEIGHT), float(v)))

        return u_clamped, v_clamped

    def map_pointer(
        self, pointer_data: Dict[str, Union[bool, float, int]]
    ) -> Dict[str, Union[bool, float, int]]:
        """
        Enrich pointer exchange dictionary with mapped board coordinates 'u' and 'v'.
        Mandatory format specification:
          {
              "detected": bool,
              "x": float,       # Stabilized camera x
              "y": float,       # Stabilized camera y
              "raw_x": float,   # Raw camera x
              "raw_y": float,   # Raw camera y
              "area": int,      # Pixel area
              "u": float,       # Board coordinate X in [0, BOARD_WIDTH]
              "v": float        # Board coordinate Y in [0, BOARD_HEIGHT]
          }
        """
        result = dict(pointer_data)

        if not pointer_data["detected"]:
            result["u"] = 0.0
            result["v"] = 0.0
            return result

        # Map stabilized coordinates
        u, v = self.map_point(float(pointer_data["x"]), float(pointer_data["y"]))
        result["u"] = round(u, 2)
        result["v"] = round(v, 2)

        return result

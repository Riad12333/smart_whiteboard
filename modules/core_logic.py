"""
Core Pure Logic Module for Smart Interactive Whiteboard (Step 4quinquies - Partie E).
Contains purely mathematical and algorithmic functions without side effects or global state:
  - DLT 8x8 projective homography solver
  - Homogeneous coordinate transformation and bounding
  - Jitter deadzone attenuation
  - 1€ (One Euro) adaptive filtering
  - Integer Bresenham line rasterization
  - Pure stroke history and Undo/Redo state transitions

Designed for straightforward, 1-to-1 portability to JavaScript / TypeScript / WebAssembly.
"""

import math
from typing import Dict, List, Optional, Tuple, Union
import numpy as np


# ==============================================================================
# 1. Direct Linear Transform (DLT) & Coordinate Mapping
# ==============================================================================

def compute_homography_dlt(
    src_points: Union[np.ndarray, List[List[float]]],
    dst_points: Union[np.ndarray, List[List[float]]]
) -> np.ndarray:
    """
    Compute 3x3 projective transformation matrix H such that:
      [u, v, 1]^T ~ H * [x, y, 1]^T
    Using 4 point correspondences via the Direct Linear Transformation (DLT) algorithm.
    Solves Ah = b where A is an 8x8 matrix and h is the first 8 coefficients of H (with H_33 = 1).
    Pure function, zero side effects.
    """
    src = np.array(src_points, dtype=np.float64)
    dst = np.array(dst_points, dtype=np.float64)

    if src.shape != (4, 2) or dst.shape != (4, 2):
        raise ValueError(f"DLT requires exactly 4 point pairs. Got src {src.shape}, dst {dst.shape}.")

    A = np.zeros((8, 8), dtype=np.float64)
    b = np.zeros((8,), dtype=np.float64)

    for i in range(4):
        x, y = src[i, 0], src[i, 1]
        u, v = dst[i, 0], dst[i, 1]

        # Equation for u: h11*x + h12*y + h13 - u*h31*x - u*h32*y = u
        A[2 * i] = [x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y]
        b[2 * i] = u

        # Equation for v: h21*x + h22*y + h23 - v*h31*x - v*h32*y = v
        A[2 * i + 1] = [0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y]
        b[2 * i + 1] = v

    # Solve linear system
    try:
        h = np.linalg.solve(A, b)
    except np.linalg.LinAlgError as e:
        raise ValueError(f"Degenerate point configuration: collinear or overlapping points ({e}).")

    # Construct 3x3 matrix with H_33 = 1.0
    H = np.array([
        [h[0], h[1], h[2]],
        [h[3], h[4], h[5]],
        [h[6], h[7], 1.0]
    ], dtype=np.float64)

    return H


def transform_point_homography(
    x: float, y: float, H: np.ndarray, clamp_bounds: Optional[Tuple[float, float]] = None
) -> Tuple[float, float]:
    """
    Transform single point (x, y) using homography matrix H:
      x' = (H11*x + H12*y + H13) / (H31*x + H32*y + H33)
      y' = (H21*x + H22*y + H23) / (H31*x + H32*y + H33)
    Optional clamp_bounds = (max_u, max_v).
    """
    denom = H[2, 0] * x + H[2, 1] * y + H[2, 2]
    if abs(denom) < 1e-8:
        # Near zero projective denominator: return unprojected or center
        denom = 1e-8

    u = (H[0, 0] * x + H[0, 1] * y + H[0, 2]) / denom
    v = (H[1, 0] * x + H[1, 1] * y + H[1, 2]) / denom

    if clamp_bounds is not None:
        max_u, max_v = clamp_bounds
        u = max(0.0, min(float(max_u), float(u)))
        v = max(0.0, min(float(max_v), float(v)))

    return float(u), float(v)


# ==============================================================================
# 2. Filtering & Signal Stabilization
# ==============================================================================

def apply_deadzone(
    curr_x: float, curr_y: float, prev_x: Optional[float], prev_y: Optional[float], deadzone_radius: float
) -> Tuple[float, float, bool]:
    """
    Apply circular deadzone filter around previous point:
    If distance < deadzone_radius, freezes coordinate to suppress hand tremor.
    Returns (x, y, was_frozen).
    """
    if prev_x is None or prev_y is None:
        return curr_x, curr_y, False

    dist = math.hypot(curr_x - prev_x, curr_y - prev_y)
    if dist < deadzone_radius:
        return prev_x, prev_y, True
    return curr_x, curr_y, False


def compute_one_euro_alpha(cutoff_hz: float, dt_sec: float) -> float:
    """Compute low-pass filter alpha smoothing factor from cutoff frequency."""
    tau = 1.0 / (2.0 * math.pi * cutoff_hz)
    return 1.0 / (1.0 + tau / max(1e-4, dt_sec))


# ==============================================================================
# 3. Rasterization (Bresenham's Integer Line Algorithm)
# ==============================================================================

def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
    """
    Pure integer Bresenham line algorithm.
    Generates contiguous sequence of grid coordinates between (x0, y0) and (x1, y1).
    Zero floating point divisions, fully portable to C/JS.
    """
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    curr_x, curr_y = x0, y0

    while True:
        points.append((curr_x, curr_y))
        if curr_x == x1 and curr_y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            curr_x += sx
        if e2 < dx:
            err += dx
            curr_y += sy

    return points


# ==============================================================================
# 4. Pure Stroke State Transitions (Undo/Redo & Path Management)
# ==============================================================================

def create_stroke(tool: str, color_rgb: Tuple[int, int, int], thickness: int) -> Dict:
    """Create a new stroke record."""
    return {
        "tool": tool,
        "color": list(color_rgb),
        "thickness": int(thickness),
        "points": []
    }


def add_point_to_stroke(stroke: Dict, x: float, y: float) -> Dict:
    """Add a point to a stroke immutably (returns updated stroke dictionary)."""
    updated = dict(stroke)
    updated["points"] = list(stroke.get("points", [])) + [[round(float(x), 2), round(float(y), 2)]]
    return updated


def undo_stroke(
    history: List[Dict], redo_stack: List[Dict]
) -> Tuple[List[Dict], List[Dict]]:
    """
    Pure undo operation:
    Pops the most recent stroke from history and pushes it to redo_stack.
    Returns (new_history, new_redo_stack).
    """
    if not history:
        return history, redo_stack
    new_history = list(history)
    new_redo = list(redo_stack)
    popped = new_history.pop()
    new_redo.append(popped)
    return new_history, new_redo


def redo_stroke(
    history: List[Dict], redo_stack: List[Dict]
) -> Tuple[List[Dict], List[Dict]]:
    """
    Pure redo operation:
    Pops the last undone stroke from redo_stack and appends it to history.
    Returns (new_history, new_redo_stack).
    """
    if not redo_stack:
        return history, redo_stack
    new_history = list(history)
    new_redo = list(redo_stack)
    popped = new_redo.pop()
    new_history.append(popped)
    return new_history, new_redo

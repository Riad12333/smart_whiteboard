/**
 * Pure Mathematical and Algorithmic Core for Smart Interactive Whiteboard (Web Version).
 * 1-to-1 JavaScript ES Module port of modules/core_logic.py:
 *   - Direct Linear Transform (DLT) 8x8 projective homography solver (Gaussian elimination with partial pivoting)
 *   - Homogeneous projective coordinate transformation & clamping
 *   - Circular jitter deadzone filter
 *   - 1€ (One Euro) adaptive smoothing alpha
 *   - Integer Bresenham line algorithm
 *   - Pure stroke state transitions (Undo / Redo)
 *
 * Stateless, zero dependencies, deterministic math.
 */

/**
 * Solve linear system Ax = b using Gaussian elimination with partial pivoting.
 * @param {number[][]} A - n x n matrix
 * @param {number[]} b - length n vector
 * @returns {number[]} solution vector x
 */
export function solveLinearSystem(A, b) {
  const n = b.length;
  // Augmented matrix [A | b]
  const M = A.map((row, i) => [...row, b[i]]);

  for (let i = 0; i < n; i++) {
    // Partial pivoting: find maximum element in column i
    let maxRow = i;
    for (let k = i + 1; k < n; k++) {
      if (Math.abs(M[k][i]) > Math.abs(M[maxRow][i])) {
        maxRow = k;
      }
    }

    // Swap rows
    if (maxRow !== i) {
      const temp = M[i];
      M[i] = M[maxRow];
      M[maxRow] = temp;
    }

    const pivot = M[i][i];
    if (Math.abs(pivot) < 1e-12) {
      throw new Error(`Degenerate matrix: pivot is near-zero at index ${i}.`);
    }

    // Normalize pivot row
    for (let j = i; j <= n; j++) {
      M[i][j] /= pivot;
    }

    // Eliminate other rows (Gauss-Jordan)
    for (let k = 0; k < n; k++) {
      if (k !== i) {
        const factor = M[k][i];
        if (Math.abs(factor) > 1e-15) {
          for (let j = i; j <= n; j++) {
            M[k][j] -= factor * M[i][j];
          }
        }
      }
    }
  }

  return M.map(row => row[n]);
}

/**
 * Compute 3x3 projective homography matrix H using 4 point pairs (DLT).
 * Maps src_points (camera) to dst_points (board): [u, v, 1]^T ~ H * [x, y, 1]^T
 * @param {number[][]} srcPoints - 4 x 2 array of camera points
 * @param {number[][]} dstPoints - 4 x 2 array of board points
 * @returns {number[][]} 3 x 3 projective matrix with H[2][2] = 1.0
 */
export function compute_homography_dlt(srcPoints, dstPoints) {
  if (srcPoints.length !== 4 || dstPoints.length !== 4) {
    throw new Error(`DLT requires exactly 4 point correspondences. Got ${srcPoints.length} and ${dstPoints.length}.`);
  }

  const A = Array.from({ length: 8 }, () => new Array(8).fill(0));
  const b = new Array(8).fill(0);

  for (let i = 0; i < 4; i++) {
    const x = srcPoints[i][0];
    const y = srcPoints[i][1];
    const u = dstPoints[i][0];
    const v = dstPoints[i][1];

    // Equation for u: h11*x + h12*y + h13 - u*h31*x - u*h32*y = u
    A[2 * i] = [x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y];
    b[2 * i] = u;

    // Equation for v: h21*x + h22*y + h23 - v*h31*x - v*h32*y = v
    A[2 * i + 1] = [0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y];
    b[2 * i + 1] = v;
  }

  const h = solveLinearSystem(A, b);

  return [
    [h[0], h[1], h[2]],
    [h[3], h[4], h[5]],
    [h[6], h[7], 1.0]
  ];
}

/**
 * Transform a single camera point (x, y) into projected board coordinates (u, v) using H.
 * @param {number} x - Camera X
 * @param {number} y - Camera Y
 * @param {number[][]} H - 3x3 homography matrix
 * @param {number[]|null} clampBounds - Optional [max_u, max_v]
 * @returns {number[]} [u, v]
 */
export function transform_point_homography(x, y, H, clampBounds = null) {
  let denom = H[2][0] * x + H[2][1] * y + H[2][2];
  if (Math.abs(denom) < 1e-8) {
    denom = 1e-8;
  }

  let u = (H[0][0] * x + H[0][1] * y + H[0][2]) / denom;
  let v = (H[1][0] * x + H[1][1] * y + H[1][2]) / denom;

  if (clampBounds && clampBounds.length === 2) {
    const [maxU, maxV] = clampBounds;
    u = Math.max(0.0, Math.min(Number(maxU), u));
    v = Math.max(0.0, Math.min(Number(maxV), v));
  }

  return [u, v];
}

/**
 * Circular deadzone filter around previous coordinate to suppress hand tremor.
 * @param {number} currX
 * @param {number} currY
 * @param {number|null} prevX
 * @param {number|null} prevY
 * @param {number} deadzoneRadius
 * @returns {[number, number, boolean]} [x, y, wasFrozen]
 */
export function apply_deadzone(currX, currY, prevX, prevY, deadzoneRadius) {
  if (prevX === null || prevY === null || prevX === undefined || prevY === undefined) {
    return [currX, currY, false];
  }

  const dist = Math.hypot(currX - prevX, currY - prevY);
  if (dist < deadzoneRadius) {
    return [prevX, prevY, true];
  }
  return [currX, currY, false];
}

/**
 * Compute low-pass filter alpha smoothing factor from cutoff frequency.
 * @param {number} cutoffHz
 * @param {number} dtSec
 * @returns {number} alpha in (0, 1]
 */
export function compute_one_euro_alpha(cutoffHz, dtSec) {
  const tau = 1.0 / (2.0 * Math.PI * cutoffHz);
  const dt = Math.max(1e-4, dtSec);
  return 1.0 / (1.0 + tau / dt);
}

/**
 * Integer Bresenham line algorithm.
 * Produces contiguous sequence of 8-connected grid coordinates.
 * @param {number} x0
 * @param {number} y0
 * @param {number} x1
 * @param {number} y1
 * @returns {number[][]} Array of [x, y] integer coordinates
 */
export function bresenham_line(x0, y0, x1, y1) {
  const points = [];
  const dx = Math.abs(x1 - x0);
  const dy = Math.abs(y1 - y0);
  const sx = x0 < x1 ? 1 : -1;
  const sy = y0 < y1 ? 1 : -1;
  let err = dx - dy;

  let currX = Math.round(x0);
  let currY = Math.round(y0);
  const targetX = Math.round(x1);
  const targetY = Math.round(y1);

  while (true) {
    points.push([currX, currY]);
    if (currX === targetX && currY === targetY) {
      break;
    }
    const e2 = 2 * err;
    if (e2 > -dy) {
      err -= dy;
      currX += sx;
    }
    if (e2 < dx) {
      err += dx;
      currY += sy;
    }
  }

  return points;
}

/**
 * Create a new stroke record.
 */
export function create_stroke(tool, colorRgb, thickness) {
  return {
    tool: String(tool),
    color: [...colorRgb],
    thickness: Number(thickness),
    points: []
  };
}

/**
 * Immutably append a coordinate [x, y] to a stroke.
 */
export function add_point_to_stroke(stroke, x, y) {
  return {
    ...stroke,
    points: [...stroke.points, [Math.round(x * 100) / 100, Math.round(y * 100) / 100]]
  };
}

/**
 * Pure Undo operation: pops last stroke from history into redoStack.
 */
export function undo_stroke(history, redoStack) {
  if (!history || history.length === 0) {
    return [history, redoStack];
  }
  const newHistory = history.slice(0, -1);
  const popped = history[history.length - 1];
  const newRedo = [...redoStack, popped];
  return [newHistory, newRedo];
}

/**
 * Pure Redo operation: pops last stroke from redoStack into history.
 */
export function redo_stroke(history, redoStack) {
  if (!redoStack || redoStack.length === 0) {
    return [history, redoStack];
  }
  const popped = redoStack[redoStack.length - 1];
  const newRedo = redoStack.slice(0, -1);
  const newHistory = [...history, popped];
  return [newHistory, newRedo];
}

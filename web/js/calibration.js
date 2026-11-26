/**
 * Board Geometric Calibration Module for Smart Interactive Whiteboard (Web Version).
 * 1-to-1 JavaScript port of modules/calibration.py:
 *   - Direct Linear Transform (DLT) 8x8 homography solver
 *   - Error estimation and validation with ground-truth points
 *   - Safe persistent storage using localStorage with try/catch
 */

import { compute_homography_dlt, transform_point_homography } from "./core_logic.js";
import { getSettings } from "./settings.js";

export const LOCAL_STORAGE_KEY = "smart_whiteboard_calibration_data";

export class BoardCalibrator {
  constructor(boardWidth = 1280, boardHeight = 720) {
    const settings = getSettings();
    this.boardWidth = boardWidth || settings.board.board_width;
    this.boardHeight = boardHeight || settings.board.board_height;

    this.srcCorners = settings.calibration.default_camera_corners.map(pt => [...pt]);
    this.dstCorners = [
      [0.0, 0.0],
      [Number(this.boardWidth), 0.0],
      [Number(this.boardWidth), Number(this.boardHeight)],
      [0.0, Number(this.boardHeight)]
    ];

    this.H = null;
    this.isCalibrated = false;
    this.lastMetrics = {
      meanValidationErrorPx: 0.0,
      validationPointsCount: 0,
      timestamp: null
    };

    // Attempt to load previous calibration from localStorage
    this.loadFromLocalStorage();

    if (!this.H) {
      this.computeDefaultHomography();
    }
  }

  /**
   * Compute initial homography using default corner coordinates.
   */
  computeDefaultHomography() {
    try {
      this.H = compute_homography_dlt(this.srcCorners, this.dstCorners);
      this.isCalibrated = true;
    } catch (err) {
      console.warn("[BoardCalibrator] Default homography computation failed:", err.message);
      this.H = null;
      this.isCalibrated = false;
    }
  }

  /**
   * Calibrate using 4 provided camera corners.
   * @param {number[][]} srcCorners - 4 x 2 array of camera pixel coordinates
   * @param {number[][]} [dstCorners] - 4 x 2 array of target board coordinates
   * @returns {boolean} Success status
   */
  calibrate(srcCorners, dstCorners = null) {
    if (!srcCorners || srcCorners.length !== 4) {
      console.error("[BoardCalibrator] Exactly 4 camera corners are required.");
      return false;
    }

    this.srcCorners = srcCorners.map(pt => [Number(pt[0]), Number(pt[1])]);
    if (dstCorners && dstCorners.length === 4) {
      this.dstCorners = dstCorners.map(pt => [Number(pt[0]), Number(pt[1])]);
    }

    try {
      this.H = compute_homography_dlt(this.srcCorners, this.dstCorners);
      this.isCalibrated = true;
      this.saveToLocalStorage();
      return true;
    } catch (err) {
      console.error("[BoardCalibrator] Calibration failed:", err.message);
      this.isCalibrated = false;
      return false;
    }
  }

  /**
   * Validate homography against a set of known ground-truth camera -> board pairs.
   * Computes real Euclidean reprojection error in pixels.
   * @param {Array<{camera: number[], board: number[]}>} validationPairs
   * @returns {{meanErrorPx: number, maxErrorPx: number}}
   */
  validate(validationPairs) {
    if (!this.isCalibrated || !this.H) {
      return { meanErrorPx: Infinity, maxErrorPx: Infinity };
    }

    let totalError = 0.0;
    let maxError = 0.0;

    for (const pair of validationPairs) {
      const [u, v] = transform_point_homography(pair.camera[0], pair.camera[1], this.H);
      const err = Math.hypot(u - pair.board[0], v - pair.board[1]);
      totalError += err;
      if (err > maxError) maxError = err;
    }

    const count = validationPairs.length || 1;
    const meanError = totalError / count;

    this.lastMetrics = {
      meanValidationErrorPx: Math.round(meanError * 100) / 100,
      maxValidationErrorPx: Math.round(maxError * 100) / 100,
      validationPointsCount: count,
      timestamp: Date.now()
    };

    this.saveToLocalStorage();
    return this.lastMetrics;
  }

  /**
   * Save calibration data safely to browser localStorage with try/catch.
   */
  saveToLocalStorage(key = LOCAL_STORAGE_KEY) {
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        const payload = {
          srcCorners: this.srcCorners,
          dstCorners: this.dstCorners,
          H: this.H,
          lastMetrics: this.lastMetrics,
          boardWidth: this.boardWidth,
          boardHeight: this.boardHeight
        };
        window.localStorage.setItem(key, JSON.stringify(payload));
        console.log("[BoardCalibrator] Calibration saved to localStorage.");
      }
    } catch (err) {
      console.warn("[BoardCalibrator] Could not save to localStorage (private browsing or quota):", err.message);
    }
  }

  /**
   * Load previously saved calibration data from browser localStorage.
   */
  loadFromLocalStorage(key = LOCAL_STORAGE_KEY) {
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        const raw = window.localStorage.getItem(key);
        if (raw) {
          const data = JSON.parse(raw);
          if (data && data.srcCorners && data.dstCorners && data.H) {
            this.srcCorners = data.srcCorners;
            this.dstCorners = data.dstCorners;
            this.H = data.H;
            this.lastMetrics = data.lastMetrics || this.lastMetrics;
            this.isCalibrated = true;
            console.log("[BoardCalibrator] Restored calibration from localStorage.");
            return true;
          }
        }
      }
    } catch (err) {
      console.warn("[BoardCalibrator] Could not load from localStorage:", err.message);
    }
    return false;
  }

  /**
   * Clear saved calibration and reset to defaults.
   */
  reset() {
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        window.localStorage.removeItem(LOCAL_STORAGE_KEY);
      }
    } catch (err) {
      // Ignored
    }
    const settings = getSettings();
    this.srcCorners = settings.calibration.default_camera_corners.map(pt => [...pt]);
    this.computeDefaultHomography();
  }
}

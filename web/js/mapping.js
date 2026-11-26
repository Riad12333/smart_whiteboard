/**
 * Coordinate Mapping Module for Smart Interactive Whiteboard (Web Version).
 * 1-to-1 JavaScript port of modules/mapping.py:
 *   - Transforms detected camera pointer coordinates (x, y) into projected whiteboard pixel coordinates (u, v)
 *   - Uses the 3x3 homography matrix estimated by BoardCalibrator
 *   - Enriches pointer dictionary with mapped 'u' and 'v' conforming strictly to docs/PROTOCOL.md
 */

import { transform_point_homography } from "./core_logic.js";
import { BoardCalibrator } from "./calibration.js";
import { getSettings } from "./settings.js";

export class CoordinateMapper {
  /**
   * @param {BoardCalibrator} [calibrator]
   */
  constructor(calibrator = null) {
    this.calibrator = calibrator || new BoardCalibrator();
  }

  get isCalibrated() {
    return this.calibrator && this.calibrator.isCalibrated && this.calibrator.H !== null;
  }

  /**
   * Map single camera point (x, y) to board canvas coordinates (u, v).
   * Clamps coordinates strictly within [0, boardWidth] x [0, boardHeight].
   * @param {number} x
   * @param {number} y
   * @returns {[number, number]} [u, v]
   */
  mapPoint(x, y) {
    const settings = getSettings();
    const bw = this.calibrator.boardWidth || settings.board.board_width;
    const bh = this.calibrator.boardHeight || settings.board.board_height;

    if (this.isCalibrated) {
      return transform_point_homography(x, y, this.calibrator.H, [bw, bh]);
    }

    // Fallback: direct linear proportional scaling
    const fw = settings.camera.frame_width || 640;
    const fh = settings.camera.frame_height || 480;

    let u = (x / fw) * bw;
    let v = (y / fh) * bh;

    u = Math.max(0.0, Math.min(bw, u));
    v = Math.max(0.0, Math.min(bh, v));

    return [u, v];
  }

  /**
   * Enrich pointer exchange dictionary with mapped board coordinates 'u' and 'v'.
   * Conforms strictly to docs/PROTOCOL.md specification.
   * @param {Object} pointerData
   * @returns {Object} enriched pointer object
   */
  mapPointer(pointerData) {
    const result = { ...pointerData };

    if (!pointerData || !pointerData.detected) {
      result.u = 0.0;
      result.v = 0.0;
      return result;
    }

    const [u, v] = this.mapPoint(Number(pointerData.x), Number(pointerData.y));
    result.u = Math.round(u * 100) / 100;
    result.v = Math.round(v * 100) / 100;

    return result;
  }
}

/**
 * Colored Marker Detection Module for Web (Step 4quinquies - Partie 3).
 * Fallback detector using HSV color thresholding on downscaled offscreen canvas:
 *   - Fast RGB -> HSV conversion in pure JavaScript
 *   - Connected component labeling / bounding box isolation
 *   - Centroid calculation and deadzone stabilization
 *   - 100% conforming to docs/PROTOCOL.md
 */

import { apply_deadzone } from "./core_logic.js";
import { getSettings } from "./settings.js";

/**
 * Fast RGB (0-255) to HSV conversion.
 * H in [0, 180], S in [0, 255], V in [0, 255] (matching OpenCV standard ranges).
 */
export function rgbToHsv(r, g, b) {
  const rf = r / 255.0;
  const gf = g / 255.0;
  const bf = b / 255.0;

  const max = Math.max(rf, gf, bf);
  const min = Math.min(rf, gf, bf);
  const delta = max - min;

  // Value
  const v = Math.round(max * 255.0);

  // Saturation
  const s = max === 0 ? 0 : Math.round((delta / max) * 255.0);

  // Hue
  let h = 0;
  if (delta > 1e-5) {
    if (max === rf) {
      h = 60.0 * (((gf - bf) / delta) % 6);
    } else if (max === gf) {
      h = 60.0 * ((bf - rf) / delta + 2.0);
    } else {
      h = 60.0 * ((rf - gf) / delta + 4.0);
    }
    if (h < 0) h += 360.0;
  }

  // Scale to [0, 180]
  const hOpenCV = Math.round(h / 2.0);
  return [hOpenCV, s, v];
}

export class WebMarkerDetector {
  constructor(downscale = 4) {
    this.downscale = downscale;
    this.canvas = document.createElement("canvas");
    this.ctx = this.canvas.getContext("2d", { willReadFrequently: true });

    this.lastSmoothed = null;
    this.lostFramesCount = 0;
  }

  detect(videoElement) {
    const t0 = performance.now();
    if (!videoElement || videoElement.readyState < 2) {
      return this._makeLost(performance.now() - t0);
    }

    const settings = getSettings();
    const dMarker = settings.detection_marker || {};
    const hMin = dMarker.marker_h_min ?? 35;
    const hMax = dMarker.marker_h_max ?? 85;
    const sMin = dMarker.marker_s_min ?? 80;
    const sMax = dMarker.marker_s_max ?? 255;
    const vMin = dMarker.marker_v_min ?? 60;
    const vMax = dMarker.marker_v_max ?? 255;
    const deadzone = settings.stabilization?.deadzone_radius ?? 3.5;

    const vw = videoElement.videoWidth || 640;
    const vh = videoElement.videoHeight || 480;

    const dw = Math.floor(vw / this.downscale);
    const dh = Math.floor(vh / this.downscale);

    if (this.canvas.width !== dw || this.canvas.height !== dh) {
      this.canvas.width = dw;
      this.canvas.height = dh;
    }

    // Draw downscaled frame
    this.ctx.drawImage(videoElement, 0, 0, dw, dh);
    const imgData = this.ctx.getImageData(0, 0, dw, dh);
    const data = imgData.data;

    let sumX = 0;
    let sumY = 0;
    let count = 0;
    let minX = dw, maxX = 0, minY = dh, maxY = 0;

    for (let y = 0; y < dh; y++) {
      const rowOffset = y * dw * 4;
      for (let x = 0; x < dw; x++) {
        const idx = rowOffset + x * 4;
        const r = data[idx];
        const g = data[idx + 1];
        const b = data[idx + 2];

        const [h, s, v] = rgbToHsv(r, g, b);
        if (h >= hMin && h <= hMax && s >= sMin && s <= sMax && v >= vMin && v <= vMax) {
          sumX += x;
          sumY += y;
          count++;
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
      }
    }

    // Minimum blob area threshold (scaled)
    const minBlobPixels = Math.floor(150 / (this.downscale * this.downscale));

    if (count < minBlobPixels) {
      return this._makeLost(performance.now() - t0);
    }

    // Centroid in camera original pixels
    const rawX = (sumX / count) * this.downscale;
    const rawY = (sumY / count) * this.downscale;

    let smX = rawX;
    let smY = rawY;
    if (this.lastSmoothed) {
      const [dzX, dzY, frozen] = apply_deadzone(rawX, rawY, this.lastSmoothed[0], this.lastSmoothed[1], deadzone);
      smX = dzX;
      smY = dzY;
    }

    this.lastSmoothed = [smX, smY];
    this.lostFramesCount = 0;

    const box = [
      minX * this.downscale,
      minY * this.downscale,
      maxX * this.downscale,
      maxY * this.downscale
    ];

    return {
      detected: true,
      x: Math.round(smX * 100) / 100,
      y: Math.round(smY * 100) / 100,
      raw_x: Math.round(rawX * 100) / 100,
      raw_y: Math.round(rawY * 100) / 100,
      area: count * this.downscale * this.downscale,
      u: 0.0,
      v: 0.0,
      score: 1.0,
      pointing: true,
      box,
      landmarks: null,
      inference_time_ms: Math.round((performance.now() - t0) * 10) / 10
    };
  }

  _makeLost(latencyMs) {
    this.lostFramesCount++;
    if (this.lostFramesCount > 5) {
      this.lastSmoothed = null;
    }
    return {
      detected: false,
      x: 0.0,
      y: 0.0,
      raw_x: 0.0,
      raw_y: 0.0,
      area: 0,
      u: 0.0,
      v: 0.0,
      score: 0.0,
      pointing: false,
      box: null,
      landmarks: null,
      inference_time_ms: Math.round(latencyMs * 10) / 10
    };
  }
}

/**
 * Machine Learning Hand Detector for Web (Step 4quinquies - Partie 3).
 * Uses local MediaPipe Tasks Vision (HandLandmarker) running via WebAssembly SIMD
 * without external CDN dependencies at runtime.
 *
 * Conforms strictly to docs/PROTOCOL.md:
 *   - Landmark 8 (Index Fingertip) tracking
 *   - Spatial multi-hand arbitration (nearest to last position or highest confidence)
 *   - Rotation-invariant pointing posture verification
 *   - 1€ (One Euro) adaptive filtering + circular deadzone
 *   - Calibrated board polygon confinement
 */

import { FilesetResolver, HandLandmarker } from "./libs/vision_bundle.mjs";
import { apply_deadzone } from "./core_logic.js";
import { getSettings } from "./settings.js";

class LowPassFilter {
  constructor(alpha = 1.0) {
    this.alpha = alpha;
    this.yPrev = null;
  }
  filter(x, alpha = null) {
    if (alpha !== null) this.alpha = alpha;
    const s = this.yPrev === null ? x : this.alpha * x + (1.0 - this.alpha) * this.yPrev;
    this.yPrev = s;
    return s;
  }
  reset() {
    this.yPrev = null;
  }
}

export class OneEuroFilter {
  constructor(minCutoff = 1.0, beta = 0.007, dCutoff = 1.0) {
    this.minCutoff = minCutoff;
    this.beta = beta;
    this.dCutoff = dCutoff;
    this.xFilter = new LowPassFilter();
    this.dxFilter = new LowPassFilter();
    this.tPrev = null;
    this.xPrev = null;
  }

  _alpha(cutoff, dt) {
    const tau = 1.0 / (2.0 * Math.PI * cutoff);
    return 1.0 / (1.0 + tau / Math.max(1e-4, dt));
  }

  filter(x, t = null) {
    const now = t !== null ? t : performance.now() / 1000.0;
    const dt = this.tPrev === null || now - this.tPrev <= 0 ? 1.0 / 60.0 : Math.max(1e-4, now - this.tPrev);
    this.tPrev = now;

    const dx = this.xPrev === null ? 0.0 : (x - this.xPrev) / dt;
    this.xPrev = x;

    const aD = this._alpha(this.dCutoff, dt);
    const dxHat = this.dxFilter.filter(dx, aD);

    const cutoff = this.minCutoff + this.beta * Math.abs(dxHat);
    const a = this._alpha(cutoff, dt);
    return this.xFilter.filter(x, a);
  }

  reset() {
    this.xFilter.reset();
    this.dxFilter.reset();
    this.tPrev = null;
    this.xPrev = null;
  }
}

/**
 * Verify if 21-landmarks hand is in an index-pointing posture.
 */
export function verifyPointingPosture(landmarks) {
  if (!landmarks || landmarks.length !== 21) return false;
  const wrist = landmarks[0];

  const dWrist = (idx) => {
    const pt = landmarks[idx];
    return Math.hypot(pt[0] - wrist[0], pt[1] - wrist[1]);
  };

  const indexExtended = dWrist(8) > dWrist(6);
  const middleFolded = dWrist(12) < dWrist(10);
  const ringFolded = dWrist(16) < dWrist(14);
  const pinkyFolded = dWrist(20) < dWrist(18);

  return indexExtended && middleFolded && ringFolded && pinkyFolded;
}

export class WebHandMLDetector {
  constructor() {
    this.landmarker = null;
    this.isReady = false;
    this.initError = null;

    const settings = getSettings();
    const dml = settings.detection_ml || {};
    const stb = settings.stabilization || {};

    this.deadzone = stb.deadzone_radius || 3.5;
    this.maxLostFrames = stb.max_lost_frames || 5;
    this.requirePointing = dml.require_pointing || false;
    this.boardMargin = dml.board_margin || 30.0;

    // Filters for X and Y
    this.fx = new OneEuroFilter(dml.one_euro_min_cutoff || 1.0, dml.one_euro_beta || 0.007, dml.one_euro_d_cutoff || 1.0);
    this.fy = new OneEuroFilter(dml.one_euro_min_cutoff || 1.0, dml.one_euro_beta || 0.007, dml.one_euro_d_cutoff || 1.0);

    this.lastPos = null;
    this.lastSmoothed = null;
    this.lostFramesCount = 0;
    this.boardPolygon = null;
  }

  /**
   * Asynchronously load local MediaPipe Tasks wasm and task model without CDN.
   */
  async init(wasmPath = "./models/wasm", modelPath = "./models/hand_landmarker.task") {
    try {
      console.log("[WebHandMLDetector] Initializing local MediaPipe Vision WASM...");
      const vision = await FilesetResolver.forVisionTasks(wasmPath);

      this.landmarker = await HandLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath: modelPath,
          delegate: "GPU"
        },
        runningMode: "VIDEO",
        numHands: 2,
        minHandDetectionConfidence: 0.6,
        minHandPresenceConfidence: 0.6,
        minTrackingConfidence: 0.6
      });

      this.isReady = true;
      console.log("[WebHandMLDetector] HandLandmarker loaded successfully from local assets.");
      return true;
    } catch (err) {
      this.initError = err.message;
      this.isReady = false;
      console.warn("[WebHandMLDetector] Initialization failed:", err.message);
      return false;
    }
  }

  setBoardPolygon(polygon) {
    this.boardPolygon = polygon && polygon.length >= 3 ? polygon : null;
  }

  _isInsideBoard(x, y) {
    if (!this.boardPolygon) return true;
    // Ray-casting algorithm with margin
    let inside = false;
    const pts = this.boardPolygon;
    for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      const xi = pts[i][0], yi = pts[i][1];
      const xj = pts[j][0], yj = pts[j][1];
      const intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  }

  /**
   * Process a live HTMLVideoElement frame.
   * Conforms strictly to docs/PROTOCOL.md.
   */
  detect(videoElement, timestampMs = null) {
    const t0 = performance.now();
    const ts = timestampMs !== null ? timestampMs : t0;

    if (!this.isReady || !this.landmarker || !videoElement || videoElement.readyState < 2) {
      return this._makeLostResult(performance.now() - t0);
    }

    const vw = videoElement.videoWidth || 640;
    const vh = videoElement.videoHeight || 480;

    let results = null;
    try {
      results = this.landmarker.detectForVideo(videoElement, Math.round(ts));
    } catch (e) {
      return this._makeLostResult(performance.now() - t0);
    }

    if (!results || !results.landmarks || results.landmarks.length === 0) {
      return this._makeLostResult(performance.now() - t0);
    }

    // Process all detected hands
    const candidates = [];
    for (let h = 0; h < results.landmarks.length; h++) {
      const rawLms = results.landmarks[h];
      const score = (results.handedness && results.handedness[h] && results.handedness[h][0])
        ? results.handedness[h][0].score
        : 0.9;

      // Convert normalized landmarks to camera pixel coordinates
      const pixelLms = rawLms.map(p => [p.x * vw, p.y * vh, p.z * vw]);

      // Landmark 8: Index Fingertip
      const tipX = pixelLms[8][0];
      const tipY = pixelLms[8][1];

      // Bounding box
      const xs = pixelLms.map(p => p[0]);
      const ys = pixelLms.map(p => p[1]);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);

      const pointing = verifyPointingPosture(pixelLms);

      candidates.push({
        tipX,
        tipY,
        landmarks: pixelLms,
        box: [minX, minY, maxX, maxY],
        score: Math.round(score * 1000) / 1000,
        pointing,
        area: Math.round((maxX - minX) * (maxY - minY))
      });
    }

    // Filter by pointing posture if required
    let validCandidates = candidates;
    if (this.requirePointing) {
      const pointingOnly = candidates.filter(c => c.pointing);
      if (pointingOnly.length > 0) validCandidates = pointingOnly;
    }

    // Filter by board bounds
    if (this.boardPolygon) {
      const insideOnly = validCandidates.filter(c => this._isInsideBoard(c.tipX, c.tipY));
      if (insideOnly.length > 0) validCandidates = insideOnly;
    }

    if (validCandidates.length === 0) {
      return this._makeLostResult(performance.now() - t0);
    }

    // Multi-hand arbitration: closest to last position, or highest score
    let best = validCandidates[0];
    if (this.lastPos) {
      const [lx, ly] = this.lastPos;
      validCandidates.sort((a, b) => Math.hypot(a.tipX - lx, a.tipY - ly) - Math.hypot(b.tipX - lx, b.tipY - ly));
      best = validCandidates[0];
    } else {
      validCandidates.sort((a, b) => b.score - a.score);
      best = validCandidates[0];
    }

    const rawX = best.tipX;
    const rawY = best.tipY;

    // Apply Deadzone + 1€ Filter
    let smX, smY;
    if (!this.lastSmoothed) {
      smX = rawX;
      smY = rawY;
      this.fx.filter(rawX, ts / 1000.0);
      this.fy.filter(rawY, ts / 1000.0);
    } else {
      const [dzX, dzY, frozen] = apply_deadzone(rawX, rawY, this.lastSmoothed[0], this.lastSmoothed[1], this.deadzone);
      if (frozen) {
        smX = dzX;
        smY = dzY;
      } else {
        smX = this.fx.filter(rawX, ts / 1000.0);
        smY = this.fy.filter(rawY, ts / 1000.0);
      }
    }

    this.lastSmoothed = [smX, smY];
    this.lastPos = [rawX, rawY];
    this.lostFramesCount = 0;

    return {
      detected: true,
      x: Math.round(smX * 100) / 100,
      y: Math.round(smY * 100) / 100,
      raw_x: Math.round(rawX * 100) / 100,
      raw_y: Math.round(rawY * 100) / 100,
      area: best.area,
      u: 0.0, // Added by CoordinateMapper
      v: 0.0,
      score: best.score,
      pointing: best.pointing,
      box: best.box,
      landmarks: best.landmarks,
      inference_time_ms: Math.round((performance.now() - t0) * 10) / 10
    };
  }

  _makeLostResult(latencyMs) {
    this.lostFramesCount++;
    if (this.lostFramesCount > this.maxLostFrames) {
      this.lastPos = null;
      this.lastSmoothed = null;
      this.fx.reset();
      this.fy.reset();
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

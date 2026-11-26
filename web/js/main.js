/**
 * Main Web Controller for Smart Interactive Whiteboard (Partie 1, 2 & 3).
 * Integrates:
 *   - Asynchronous settings initialization (config/settings.json)
 *   - getUserMedia camera acquisition with graceful fallback to MOUSE mode
 *   - Pure DLT projective homography & mapping (Gauss-Jordan solver)
 *   - Mode selector: Main (MediaPipe Tasks ML) / Marqueur (HSV) / Souris (Simulation)
 *   - Live MediaPipe 21 3D landmarks skeleton rendering with highlighted index pointer
 *   - requestAnimationFrame loop with real-time FPS profiling
 *   - Responsive canvas scaling and drawing engine with Undo / Redo
 */

import { loadSettings, getSettings } from "./settings.js";
import { WebCamera } from "./camera.js";
import { BoardCalibrator } from "./calibration.js";
import { CoordinateMapper } from "./mapping.js";
import { WebHandMLDetector } from "./detection_ml.js";
import { WebMarkerDetector } from "./detection_marker.js";
import {
  bresenham_line,
  create_stroke,
  add_point_to_stroke,
  undo_stroke,
  redo_stroke,
} from "./core_logic.js";

const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20],
  [0, 17]
];

class WebWhiteboardApplication {
  constructor() {
    this.canvas = document.getElementById("board-canvas");
    this.ctx = this.canvas.getContext("2d");

    this.settings = null;
    this.camera = new WebCamera();
    this.calibrator = null;
    this.mapper = null;

    // Detectors (Partie 3)
    this.mlDetector = new WebHandMLDetector();
    this.markerDetector = new WebMarkerDetector(4);

    // Active mode: "HAND_ML", "MARKER", or "MOUSE"
    this.mode = "MOUSE";

    // Pointer state conforming strictly to docs/PROTOCOL.md
    this.pointer = {
      detected: true,
      x: 640.0,
      y: 360.0,
      raw_x: 640.0,
      raw_y: 360.0,
      area: 1200,
      u: 640.0,
      v: 360.0,
      score: 1.0,
      pointing: true,
      box: null,
      landmarks: null,
      inference_time_ms: 0.0
    };

    // Drawing state
    this.currentTool = "PEN"; // "PEN" or "ERASER"
    this.penColor = [30, 30, 30]; // Black default
    this.penThickness = 7;
    this.eraserThickness = 35;
    this.isDrawing = false;
    this.currentStroke = null;
    this.strokeHistory = [];
    this.redoStack = [];

    // Loop & FPS telemetry
    this.lastLoopTime = performance.now();
    this.loopFps = 60.0;
    this.loopTimes = [];

    // DOM Elements
    this.hudBadgeMode = document.getElementById("hud-badge-mode");
    this.hudLoopFps = document.getElementById("hud-loop-fps");
    this.hudCamStatus = document.getElementById("hud-cam-status");
    this.hudCalibStatus = document.getElementById("hud-calib-status");
    this.hudPointerCoords = document.getElementById("hud-pointer-coords");
    this.selectMode = document.getElementById("select-mode");
    this.privacyToast = document.getElementById("privacy-toast");
  }

  async init() {
    console.log("=== Initialisation Smart Interactive Whiteboard (Web Edition) ===");

    // 1. Load settings JSON
    this.settings = await loadSettings("config/settings.json");

    // 2. Initialize geometry & calibration (Partie 2)
    this.calibrator = new BoardCalibrator(this.settings.board.board_width, this.settings.board.board_height);
    this.mapper = new CoordinateMapper(this.calibrator);

    // 3. Setup canvas responsive sizing
    this.resizeCanvas();
    window.addEventListener("resize", () => this.resizeCanvas());

    // 4. Attach mouse and touch listeners
    this.setupPointerListeners();

    // 5. Attach UI button listeners
    this.setupUIListeners();

    // 6. Asynchronously initialize local MediaPipe Tasks wasm in the background (Partie 3)
    this.mlDetector.init("./models/wasm", "./models/hand_landmarker.task").then((success) => {
      if (success) {
        console.log("[App] ML HandLandmarker ready. Available in mode selector.");
      }
    });

    // 7. Request camera access
    const camRes = await this.camera.open(
      this.settings.camera.frame_width,
      this.settings.camera.frame_height
    );

    if (camRes.success) {
      this.mode = "HAND_ML";
      if (this.selectMode) this.selectMode.value = "HAND_ML";
      this.updateModeUI();
    } else {
      this.mode = "MOUSE";
      if (this.selectMode) this.selectMode.value = "MOUSE";
      this.updateModeUI();
    }

    // 8. Start real-time render loop
    requestAnimationFrame((t) => this.renderLoop(t));
  }

  resizeCanvas() {
    const margin = 40;
    const maxW = window.innerWidth - margin;
    const maxH = window.innerHeight - 100;

    const baseW = this.settings ? this.settings.board.board_width : 1280;
    const baseH = this.settings ? this.settings.board.board_height : 720;
    const aspect = baseW / baseH;

    let targetW = maxW;
    let targetH = targetW / aspect;

    if (targetH > maxH) {
      targetH = maxH;
      targetW = targetH * aspect;
    }

    this.canvas.style.width = `${Math.floor(targetW)}px`;
    this.canvas.style.height = `${Math.floor(targetH)}px`;
  }

  setupPointerListeners() {
    const getCanvasCoords = (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const scaleX = this.canvas.width / rect.width;
      const scaleY = this.canvas.height / rect.height;
      const clientX = e.clientX !== undefined ? e.clientX : (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
      const clientY = e.clientY !== undefined ? e.clientY : (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
      return [
        Math.max(0, Math.min(this.canvas.width, (clientX - rect.left) * scaleX)),
        Math.max(0, Math.min(this.canvas.height, (clientY - rect.top) * scaleY))
      ];
    };

    const onPointerMove = (e) => {
      if (this.mode === "MOUSE") {
        const [u, v] = getCanvasCoords(e);
        this.pointer.detected = true;
        this.pointer.u = u;
        this.pointer.v = v;
        this.pointer.raw_x = u;
        this.pointer.raw_y = v;
        this.pointer.x = u;
        this.pointer.y = v;

        if (this.isDrawing && this.currentStroke) {
          this.currentStroke = add_point_to_stroke(this.currentStroke, u, v);
        }
      }
    };

    const onPointerDown = (e) => {
      const [u, v] = getCanvasCoords(e);
      this.isDrawing = true;
      const thickness = this.currentTool === "PEN" ? this.penThickness : this.eraserThickness;
      this.currentStroke = create_stroke(this.currentTool, this.penColor, thickness);
      this.currentStroke = add_point_to_stroke(this.currentStroke, u, v);
    };

    const onPointerUp = () => {
      if (this.isDrawing && this.currentStroke && this.currentStroke.points.length > 0) {
        this.strokeHistory.push(this.currentStroke);
        this.redoStack = [];
      }
      this.isDrawing = false;
      this.currentStroke = null;
    };

    this.canvas.addEventListener("mousemove", onPointerMove);
    this.canvas.addEventListener("mousedown", onPointerDown);
    window.addEventListener("mouseup", onPointerUp);

    this.canvas.addEventListener("touchmove", (e) => { e.preventDefault(); onPointerMove(e); }, { passive: false });
    this.canvas.addEventListener("touchstart", (e) => { e.preventDefault(); onPointerDown(e); }, { passive: false });
    window.addEventListener("touchend", onPointerUp);
  }

  setupUIListeners() {
    const btnPen = document.getElementById("btn-pen");
    const btnEraser = document.getElementById("btn-eraser");
    const btnClear = document.getElementById("btn-clear");
    const btnUndo = document.getElementById("btn-undo");
    const btnFullscreen = document.getElementById("btn-fullscreen");
    const btnClosePrivacy = document.getElementById("btn-close-privacy");

    btnPen.addEventListener("click", () => {
      this.currentTool = "PEN";
      btnPen.classList.add("active");
      btnEraser.classList.remove("active");
    });

    btnEraser.addEventListener("click", () => {
      this.currentTool = "ERASER";
      btnEraser.classList.add("active");
      btnPen.classList.remove("active");
    });

    btnClear.addEventListener("click", () => {
      this.strokeHistory = [];
      this.redoStack = [];
      this.currentStroke = null;
    });

    btnUndo.addEventListener("click", () => {
      [this.strokeHistory, this.redoStack] = undo_stroke(this.strokeHistory, this.redoStack);
    });

    if (this.selectMode) {
      this.selectMode.addEventListener("change", async (e) => {
        const targetMode = e.target.value;
        if (targetMode === "HAND_ML" || targetMode === "MARKER") {
          if (!this.camera.hasCamera) {
            const res = await this.camera.open();
            if (!res.success) {
              alert(`Impossible d'activer la caméra : ${res.message}`);
              this.selectMode.value = "MOUSE";
              this.mode = "MOUSE";
              this.updateModeUI();
              return;
            }
          }
          this.mode = targetMode;
        } else {
          this.mode = "MOUSE";
        }
        this.updateModeUI();
      });
    }

    btnFullscreen.addEventListener("click", () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
      } else {
        document.exitFullscreen().catch(() => {});
      }
    });

    if (btnClosePrivacy) {
      btnClosePrivacy.addEventListener("click", () => {
        this.privacyToast.style.display = "none";
      });
    }

    // Keyboard shortcuts
    window.addEventListener("keydown", (e) => {
      if (e.key === "m" || e.key === "M") {
        if (this.mode === "HAND_ML") this.mode = "MARKER";
        else if (this.mode === "MARKER") this.mode = "MOUSE";
        else this.mode = "HAND_ML";
        if (this.selectMode) this.selectMode.value = this.mode;
        this.updateModeUI();
      } else if (e.key === "f" || e.key === "F") {
        btnFullscreen.click();
      } else if ((e.ctrlKey || e.metaKey) && (e.key === "z" || e.key === "Z")) {
        e.preventDefault();
        btnUndo.click();
      } else if (e.key === "1") {
        btnPen.click();
      } else if (e.key === "2") {
        btnEraser.click();
      }
    });
  }

  updateModeUI() {
    if (this.mode === "HAND_ML") {
      this.hudBadgeMode.textContent = "MAIN (ML)";
      this.hudBadgeMode.className = "badge badge-green";
      this.hudCamStatus.textContent = this.camera.statusMessage;
    } else if (this.mode === "MARKER") {
      this.hudBadgeMode.textContent = "MARQUEUR (HSV)";
      this.hudBadgeMode.className = "badge badge-green";
      this.hudCamStatus.textContent = this.camera.statusMessage;
    } else {
      this.hudBadgeMode.textContent = "SOURIS";
      this.hudBadgeMode.className = "badge badge-yellow";
      this.hudCamStatus.textContent = this.camera.statusMessage;
    }
  }

  renderLoop(now) {
    // 1. Measure Loop FPS
    const dt = now - this.lastLoopTime;
    this.lastLoopTime = now;
    if (dt > 0) {
      const instantFps = 1000.0 / dt;
      this.loopTimes.push(instantFps);
      if (this.loopTimes.length > 20) {
        this.loopTimes.shift();
      }
      const sum = this.loopTimes.reduce((acc, v) => acc + v, 0);
      this.loopFps = Math.round((sum / this.loopTimes.length) * 10) / 10;
    }

    // 2. Perform Computer Vision Tracking (Partie 3)
    if (this.camera.hasCamera && (this.mode === "HAND_ML" || this.mode === "MARKER")) {
      let rawPtr = null;
      if (this.mode === "HAND_ML" && this.mlDetector.isReady) {
        rawPtr = this.mlDetector.detect(this.camera.video, now);
      } else if (this.mode === "MARKER") {
        rawPtr = this.markerDetector.detect(this.camera.video);
      }

      if (rawPtr && rawPtr.detected) {
        this.pointer = this.mapper.mapPointer(rawPtr);

        // If drawing via pointing hand
        if (this.pointer.pointing && this.isDrawing && this.currentStroke) {
          this.currentStroke = add_point_to_stroke(this.currentStroke, this.pointer.u, this.pointer.v);
        }
      } else if (rawPtr) {
        this.pointer.detected = false;
      }
    }

    // 3. Clear canvas with crisp off-white background
    this.ctx.fillStyle = "#fbfbfc";
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    // 4. Render strokes history
    this.renderStrokes();

    // 5. Render active pointer target & hand skeleton
    if (this.pointer.detected) {
      this.renderPointerCursor();
    }

    // 6. Update HUD telemetry
    this.updateHUD();

    requestAnimationFrame((t) => this.renderLoop(t));
  }

  renderStrokes() {
    const allStrokes = [...this.strokeHistory];
    if (this.currentStroke && this.currentStroke.points.length > 0) {
      allStrokes.push(this.currentStroke);
    }

    for (const stroke of allStrokes) {
      const pts = stroke.points;
      if (!pts || pts.length === 0) continue;

      this.ctx.save();
      this.ctx.lineWidth = stroke.thickness;
      this.ctx.lineCap = "round";
      this.ctx.lineJoin = "round";

      if (stroke.tool === "ERASER") {
        this.ctx.strokeStyle = "#fbfbfc";
      } else {
        const [r, g, b] = stroke.color;
        this.ctx.strokeStyle = `rgb(${r}, ${g}, ${b})`;
      }

      this.ctx.beginPath();
      this.ctx.moveTo(pts[0][0], pts[0][1]);
      for (let i = 1; i < pts.length; i++) {
        this.ctx.lineTo(pts[i][0], pts[i][1]);
      }
      this.ctx.stroke();
      this.ctx.restore();
    }
  }

  renderPointerCursor() {
    const u = this.pointer.u;
    const v = this.pointer.v;

    this.ctx.save();

    // If 21 landmarks are present (HAND_ML mode), render mapped skeleton preview
    if (this.pointer.landmarks && this.pointer.landmarks.length === 21) {
      const mappedLms = this.pointer.landmarks.map(p => this.mapper.mapPoint(p[0], p[1]));

      // Draw bones
      this.ctx.strokeStyle = "rgba(105, 101, 219, 0.45)";
      this.ctx.lineWidth = 3;
      for (const [p1, p2] of HAND_CONNECTIONS) {
        this.ctx.beginPath();
        this.ctx.moveTo(mappedLms[p1][0], mappedLms[p1][1]);
        this.ctx.lineTo(mappedLms[p2][0], mappedLms[p2][1]);
        this.ctx.stroke();
      }

      // Draw joint dots
      for (let i = 0; i < 21; i++) {
        if (i !== 8) {
          this.ctx.fillStyle = "rgba(25, 113, 194, 0.7)";
          this.ctx.beginPath();
          this.ctx.arc(mappedLms[i][0], mappedLms[i][1], 3, 0, Math.PI * 2);
          this.ctx.fill();
        }
      }
    }

    // Active Pointer Tip (Landmark 8 or Marker Centroid)
    this.ctx.fillStyle = "#e03131";
    this.ctx.beginPath();
    this.ctx.arc(u, v, 6, 0, Math.PI * 2);
    this.ctx.fill();

    this.ctx.strokeStyle = "#2f9e44";
    this.ctx.lineWidth = 2.5;
    this.ctx.beginPath();
    this.ctx.arc(u, v, 14, 0, Math.PI * 2);
    this.ctx.stroke();

    this.ctx.restore();
  }

  updateHUD() {
    if (this.hudLoopFps) {
      this.hudLoopFps.textContent = `${this.loopFps.toFixed(1)} FPS`;
    }
    if (this.hudPointerCoords) {
      if (this.pointer.detected) {
        const infStr = this.pointer.inference_time_ms > 0 ? ` (${this.pointer.inference_time_ms}ms)` : "";
        this.hudPointerCoords.textContent = `u: ${this.pointer.u.toFixed(1)}, v: ${this.pointer.v.toFixed(1)}${infStr}`;
      } else {
        this.hudPointerCoords.textContent = "Pointeur : RECHERCHE...";
      }
    }
    if (this.hudCalibStatus && this.calibrator) {
      const err = this.calibrator.lastMetrics.meanValidationErrorPx;
      this.hudCalibStatus.textContent = this.calibrator.isCalibrated ? `DLT Active (Err: ${err}px)` : "Defaut";
    }
  }
}

// Start application once DOM is ready
window.addEventListener("DOMContentLoaded", () => {
  const app = new WebWhiteboardApplication();
  app.init();
});

/**
 * Main Web Controller for Smart Interactive Whiteboard (Partie 1 & 2).
 * Integrates:
 *   - Asynchronous settings initialization (config/settings.json)
 *   - getUserMedia camera acquisition with graceful fallback to MOUSE mode
 *   - Pure DLT projective homography & mapping (Gauss-Jordan solver)
 *   - requestAnimationFrame loop with real-time FPS profiling
 *   - Responsive canvas scaling and mouse pointer interaction
 */

import { loadSettings, getSettings } from "./settings.js";
import { WebCamera } from "./camera.js";
import { BoardCalibrator } from "./calibration.js";
import { CoordinateMapper } from "./mapping.js";
import {
  bresenham_line,
  create_stroke,
  add_point_to_stroke,
  undo_stroke,
  redo_stroke,
} from "./core_logic.js";

class WebWhiteboardApplication {
  constructor() {
    this.canvas = document.getElementById("board-canvas");
    this.ctx = this.canvas.getContext("2d");

    this.settings = null;
    this.camera = new WebCamera();
    this.calibrator = null;
    this.mapper = null;

    // Operational mode: "MOUSE" (default fallback) or "CAMERA"
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
    this.labelMode = document.getElementById("label-mode");
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

    // 6. Attempt camera acquisition with automatic fallback to MOUSE mode
    const camRes = await this.camera.open(
      this.settings.camera.frame_width,
      this.settings.camera.frame_height
    );

    if (camRes.success) {
      this.mode = "CAMERA";
      this.updateModeUI();
    } else {
      this.mode = "MOUSE";
      this.updateModeUI();
    }

    // 7. Start real-time render loop
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
      const [u, v] = getCanvasCoords(e);
      this.pointer.u = u;
      this.pointer.v = v;
      this.pointer.raw_x = u;
      this.pointer.raw_y = v;
      this.pointer.x = u;
      this.pointer.y = v;

      if (this.isDrawing && this.currentStroke) {
        this.currentStroke = add_point_to_stroke(this.currentStroke, u, v);
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
        this.redoStack = []; // Clear redo stack on new action
      }
      this.isDrawing = false;
      this.currentStroke = null;
    };

    this.canvas.addEventListener("mousemove", onPointerMove);
    this.canvas.addEventListener("mousedown", onPointerDown);
    window.addEventListener("mouseup", onPointerUp);

    // Touch support for mobile / tablet
    this.canvas.addEventListener("touchmove", (e) => { e.preventDefault(); onPointerMove(e); }, { passive: false });
    this.canvas.addEventListener("touchstart", (e) => { e.preventDefault(); onPointerDown(e); }, { passive: false });
    window.addEventListener("touchend", onPointerUp);
  }

  setupUIListeners() {
    const btnPen = document.getElementById("btn-pen");
    const btnEraser = document.getElementById("btn-eraser");
    const btnClear = document.getElementById("btn-clear");
    const btnUndo = document.getElementById("btn-undo");
    const btnMode = document.getElementById("btn-mode-toggle");
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

    btnMode.addEventListener("click", async () => {
      if (this.mode === "MOUSE") {
        const res = await this.camera.open();
        if (res.success) {
          this.mode = "CAMERA";
        } else {
          alert(`Impossible d'activer la caméra : ${res.message}`);
        }
      } else {
        this.camera.stop();
        this.mode = "MOUSE";
      }
      this.updateModeUI();
    });

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
        btnMode.click();
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
    if (this.mode === "CAMERA") {
      this.labelMode.textContent = "Mode : Caméra";
      this.hudBadgeMode.textContent = "CAMERA";
      this.hudBadgeMode.className = "badge badge-green";
      this.hudCamStatus.textContent = this.camera.statusMessage;
    } else {
      this.labelMode.textContent = "Mode : Souris";
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

    // 2. Clear canvas with crisp off-white background
    this.ctx.fillStyle = "#fbfbfc";
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    // 3. Render strokes history
    this.renderStrokes();

    // 4. Render active pointer target
    this.renderPointerCursor();

    // 5. Update HUD telemetry
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
        this.ctx.strokeStyle = "#fbfbfc"; // Background color erase
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
    // Inner red dot
    this.ctx.fillStyle = "#e03131";
    this.ctx.beginPath();
    this.ctx.arc(u, v, 5, 0, Math.PI * 2);
    this.ctx.fill();

    // Outer pulsating green ring
    this.ctx.strokeStyle = "#2f9e44";
    this.ctx.lineWidth = 2;
    this.ctx.beginPath();
    this.ctx.arc(u, v, 12, 0, Math.PI * 2);
    this.ctx.stroke();
    this.ctx.restore();
  }

  updateHUD() {
    if (this.hudLoopFps) {
      this.hudLoopFps.textContent = `${this.loopFps.toFixed(1)} FPS`;
    }
    if (this.hudPointerCoords) {
      this.hudPointerCoords.textContent = `u: ${this.pointer.u.toFixed(1)}, v: ${this.pointer.v.toFixed(1)}`;
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

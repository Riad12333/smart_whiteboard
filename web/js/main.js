/**
 * Main Web Controller for Smart Interactive Whiteboard (Parties 1 to 5).
 * Integrates:
 *   - Asynchronous settings initialization (config/settings.json)
 *   - getUserMedia camera acquisition with graceful fallback to MOUSE mode
 *   - Pure DLT projective homography & mapping (Gauss-Jordan solver)
 *   - Mode selector: Main (MediaPipe Tasks ML) / Marqueur (HSV) / Souris (Simulation)
 *   - Presentation Remote listener + Key Inspector modal
 *   - Excalidraw UI: HOME, DRAWING, IMAGES (+ Zoom), LESSON (+ Annotations)
 *   - Magnetic cursor snapping (SNAP_RADIUS = 75px) & visual feedback
 */

import { loadSettings, getSettings } from "./settings.js";
import { WebCamera } from "./camera.js";
import { BoardCalibrator } from "./calibration.js";
import { CoordinateMapper } from "./mapping.js";
import { WebHandMLDetector } from "./detection_ml.js";
import { WebMarkerDetector } from "./detection_marker.js";
import { RemoteHandler } from "./remote.js";
import { DrawingEngine, VISION_SAFE_PALETTE } from "./drawing.js";
import { WhiteboardInterface } from "./interface.js";
import { InteractionManager } from "./interaction.js";

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

    // Detectors & Remote
    this.mlDetector = new WebHandMLDetector();
    this.markerDetector = new WebMarkerDetector(4);
    this.remote = new RemoteHandler();

    // Drawing, Interface & Interaction (Partie 5)
    this.drawing = new DrawingEngine();
    this.ui = new WhiteboardInterface(this.canvas, this.drawing);
    this.interaction = null;

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
      snapped_u: 640.0,
      snapped_v: 360.0,
      score: 1.0,
      pointing: true,
      box: null,
      landmarks: null,
      inference_time_ms: 0.0
    };

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

    // 2. Initialize geometry & calibration
    this.calibrator = new BoardCalibrator(this.settings.board.board_width, this.settings.board.board_height);
    this.mapper = new CoordinateMapper(this.calibrator);
    this.interaction = new InteractionManager(
      this.canvas,
      this.ui,
      this.drawing,
      this.settings.interaction?.snap_radius ?? 75.0
    );

    // 3. Setup canvas responsive sizing
    this.resizeCanvas();
    window.addEventListener("resize", () => this.resizeCanvas());

    // 4. Attach mouse, touch, and UI listeners
    this.setupPointerListeners();
    this.setupUIListeners();

    // 5. Asynchronously initialize local MediaPipe Tasks wasm
    this.mlDetector.init("./models/wasm", "./models/hand_landmarker.task").then((success) => {
      if (success) {
        console.log("[App] ML HandLandmarker ready.");
      }
    });

    // 6. Request camera access
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

    // 7. Start real-time render loop
    requestAnimationFrame((t) => this.renderLoop(t));
  }

  resizeCanvas() {
    const margin = window.innerWidth <= 768 ? 12 : 40;
    const maxW = window.innerWidth - margin;
    const maxH = window.innerHeight - (window.innerWidth <= 768 ? 90 : 100);

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

        if (this.ui.activeView !== "HOME") {
          this.drawing.continueStroke(u, v);
        }
      }
    };

    const onPointerDown = (e) => {
      if (this.mode === "MOUSE" && this.ui.activeView !== "HOME") {
        const [u, v] = getCanvasCoords(e);
        this.ui.addRipple(u, v);
        this.drawing.startStroke(u, v);
      }
    };

    const onPointerUp = () => {
      if (this.mode === "MOUSE") {
        this.drawing.endStroke();
      }
    };

    this.canvas.addEventListener("mousemove", onPointerMove);
    this.canvas.addEventListener("mousedown", onPointerDown);
    window.addEventListener("mouseup", onPointerUp);

    this.canvas.addEventListener("touchmove", (e) => { e.preventDefault(); onPointerMove(e); }, { passive: false });
    this.canvas.addEventListener("touchstart", (e) => { e.preventDefault(); onPointerDown(e); }, { passive: false });
    window.addEventListener("touchend", onPointerUp);
  }

  setupUIListeners() {
    // Top Navigation Buttons
    const navHome = document.getElementById("btn-nav-home");
    const navDraw = document.getElementById("btn-nav-draw");
    const navImages = document.getElementById("btn-nav-images");
    const navLesson = document.getElementById("btn-nav-lesson");
    const navBtns = [navHome, navDraw, navImages, navLesson];

    const sidePanel = document.getElementById("side-panel");
    const subImages = document.getElementById("sub-images");
    const subLesson = document.getElementById("sub-lesson");

    const switchView = (viewName, activeBtn) => {
      this.ui.setView(viewName);
      navBtns.forEach(b => b && b.classList.remove("active"));
      if (activeBtn) activeBtn.classList.add("active");

      // Show drawing side panel in all active annotation views
      if (viewName === "HOME") {
        sidePanel.classList.remove("visible");
      } else {
        sidePanel.classList.add("visible");
      }

      subImages.classList.toggle("visible", viewName === "IMAGES");
      subLesson.classList.toggle("visible", viewName === "LESSON");
    };

    if (navHome) navHome.addEventListener("click", () => switchView("HOME", navHome));
    if (navDraw) navDraw.addEventListener("click", () => switchView("DRAWING", navDraw));
    if (navImages) navImages.addEventListener("click", () => switchView("IMAGES", navImages));
    if (navLesson) navLesson.addEventListener("click", () => switchView("LESSON", navLesson));

    // Side Panel: Colors
    const swatches = document.querySelectorAll(".color-swatch");
    swatches.forEach(sw => {
      sw.addEventListener("click", () => {
        swatches.forEach(s => s.classList.remove("active"));
        sw.classList.add("active");
        const colorKey = sw.dataset.color;
        if (VISION_SAFE_PALETTE[colorKey]) {
          this.drawing.setColor(VISION_SAFE_PALETTE[colorKey]);
          document.getElementById("btn-tool-pen")?.classList.add("active");
          document.getElementById("btn-tool-eraser")?.classList.remove("active");
        }
      });
    });

    // Side Panel: Thickness
    const thickBtns = document.querySelectorAll("[data-thickness]");
    thickBtns.forEach(tb => {
      tb.addEventListener("click", () => {
        thickBtns.forEach(b => b.classList.remove("active"));
        tb.classList.add("active");
        this.drawing.setThickness(Number(tb.dataset.thickness));
      });
    });

    // Side Panel: Pen, Eraser, Undo, Redo, Clear
    const btnPen = document.getElementById("btn-tool-pen");
    const btnEraser = document.getElementById("btn-tool-eraser");
    const btnUndo = document.getElementById("btn-tool-undo");
    const btnRedo = document.getElementById("btn-tool-redo");
    const btnClear = document.getElementById("btn-tool-clear");

    if (btnPen) btnPen.addEventListener("click", () => {
      this.drawing.setTool("PEN");
      btnPen.classList.add("active");
      btnEraser?.classList.remove("active");
    });

    if (btnEraser) btnEraser.addEventListener("click", () => {
      this.drawing.setTool("ERASER");
      btnEraser.classList.add("active");
      btnPen?.classList.remove("active");
    });

    if (btnUndo) btnUndo.addEventListener("click", () => this.drawing.undo());
    if (btnRedo) btnRedo.addEventListener("click", () => this.drawing.redo());
    if (btnClear) btnClear.addEventListener("click", () => {
      this.drawing.clear();
      this.ui.showToast("Tableau effacé");
    });

    // Images Zoom Controls
    document.getElementById("btn-zoom-in")?.addEventListener("click", () => this.ui.zoomIn());
    document.getElementById("btn-zoom-out")?.addEventListener("click", () => this.ui.zoomOut());
    document.getElementById("btn-zoom-reset")?.addEventListener("click", () => this.ui.resetZoom());

    // Lesson Navigation Controls
    document.getElementById("btn-lesson-prev")?.addEventListener("click", () => this.ui.prevLessonSlide());
    document.getElementById("btn-lesson-next")?.addEventListener("click", () => this.ui.nextLessonSlide());

    // Global Reset
    document.getElementById("btn-reset-all")?.addEventListener("click", () => {
      this.ui.resetAll();
      switchView("HOME", navHome);
    });

    // Detection Mode Selector
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

    // Fullscreen Toggle
    const btnFullscreen = document.getElementById("btn-fullscreen");
    if (btnFullscreen) {
      btnFullscreen.addEventListener("click", () => {
        if (!document.fullscreenElement) {
          document.documentElement.requestFullscreen().catch(() => {});
        } else {
          document.exitFullscreen().catch(() => {});
        }
      });
    }

    // Key Inspector Modal (Partie 4)
    const btnRemoteInspect = document.getElementById("btn-remote-inspect");
    const inspectorModal = document.getElementById("inspector-modal");
    const btnCloseInspector = document.getElementById("btn-close-inspector");
    const inspKey = document.getElementById("insp-key");
    const inspCode = document.getElementById("insp-code");
    const inspEvent = document.getElementById("insp-event");

    const toggleInspector = () => {
      const isVisible = inspectorModal.style.display === "block";
      inspectorModal.style.display = isVisible ? "none" : "block";
    };

    if (btnRemoteInspect) btnRemoteInspect.addEventListener("click", toggleInspector);
    if (btnCloseInspector) btnCloseInspector.addEventListener("click", () => { inspectorModal.style.display = "none"; });

    document.getElementById("btn-close-privacy")?.addEventListener("click", () => {
      this.privacyToast.style.display = "none";
    });

    // Keyboard & Presentation Remote Listener
    window.addEventListener("keydown", (e) => {
      const remoteRes = this.remote.processKeyEvent(e);

      // Update Key Inspector
      if (inspKey) inspKey.textContent = `"${e.key}"`;
      if (inspCode) inspCode.textContent = `"${e.code}"`;
      if (inspEvent) {
        if (remoteRes && remoteRes.event === "LEFT_CLICK") {
          inspEvent.textContent = "LEFT_CLICK (Clic Gauche)";
          inspEvent.className = "badge badge-green";
        } else if (remoteRes && remoteRes.event === "RIGHT_CLICK") {
          inspEvent.textContent = "RIGHT_CLICK (Clic Droit)";
          inspEvent.className = "badge badge-blue";
        } else {
          inspEvent.textContent = "AUTRE TOUCHE";
          inspEvent.className = "badge badge-yellow";
        }
      }

      if (remoteRes && remoteRes.event && this.interaction) {
        this.interaction.handleRemoteEvent(remoteRes.event, this.pointer.snapped_u, this.pointer.snapped_v);
      }

      if (e.key === "m" || e.key === "M") {
        if (this.mode === "HAND_ML") this.mode = "MARKER";
        else if (this.mode === "MARKER") this.mode = "MOUSE";
        else this.mode = "HAND_ML";
        if (this.selectMode) this.selectMode.value = this.mode;
        this.updateModeUI();
      } else if (e.key === "t" || e.key === "T") {
        toggleInspector();
      } else if (e.key === "f" || e.key === "F") {
        btnFullscreen?.click();
      } else if ((e.ctrlKey || e.metaKey) && (e.key === "z" || e.key === "Z")) {
        e.preventDefault();
        this.drawing.undo();
      } else if ((e.ctrlKey || e.metaKey) && (e.key === "y" || e.key === "Y")) {
        e.preventDefault();
        this.drawing.redo();
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
      if (this.loopTimes.length > 20) this.loopTimes.shift();
      this.loopFps = Math.round((this.loopTimes.reduce((a, b) => a + b, 0) / this.loopTimes.length) * 10) / 10;
    }

    // 2. Computer Vision Tracking
    if (this.camera.hasCamera && (this.mode === "HAND_ML" || this.mode === "MARKER")) {
      let rawPtr = null;
      if (this.mode === "HAND_ML" && this.mlDetector.isReady) {
        rawPtr = this.mlDetector.detect(this.camera.video, now);
      } else if (this.mode === "MARKER") {
        rawPtr = this.markerDetector.detect(this.camera.video);
      }

      if (rawPtr && rawPtr.detected) {
        this.pointer = this.mapper.mapPointer(rawPtr);

        // Apply magnetic cursor snapping
        const snap = this.interaction.applyMagneticSnap(this.pointer.u, this.pointer.v);
        this.pointer.snapped_u = snap.u;
        this.pointer.snapped_v = snap.v;

        // If pen is down via remote click, draw at snapped position
        if (this.ui.activeView !== "HOME" && this.drawing.isDrawing) {
          this.drawing.continueStroke(this.pointer.snapped_u, this.pointer.snapped_v);
        }
      } else if (rawPtr) {
        this.pointer.detected = false;
      }
    } else {
      // Mouse mode magnetic snap
      const snap = this.interaction.applyMagneticSnap(this.pointer.u, this.pointer.v);
      this.pointer.snapped_u = snap.u;
      this.pointer.snapped_v = snap.v;
    }

    // 3. Render UI & Drawing Strokes
    this.ui.render(this.ctx);

    // 4. Render Active Pointer & Hand Skeleton
    if (this.pointer.detected) {
      this.renderPointerCursor();
    }

    // 5. Update HUD telemetry
    this.updateHUD();

    requestAnimationFrame((t) => this.renderLoop(t));
  }

  renderPointerCursor() {
    const u = this.pointer.snapped_u;
    const v = this.pointer.snapped_v;

    this.ctx.save();

    if (this.pointer.landmarks && this.pointer.landmarks.length === 21) {
      const mappedLms = this.pointer.landmarks.map(p => this.mapper.mapPoint(p[0], p[1]));

      this.ctx.strokeStyle = "rgba(105, 101, 219, 0.45)";
      this.ctx.lineWidth = 3;
      for (const [p1, p2] of HAND_CONNECTIONS) {
        this.ctx.beginPath();
        this.ctx.moveTo(mappedLms[p1][0], mappedLms[p1][1]);
        this.ctx.lineTo(mappedLms[p2][0], mappedLms[p2][1]);
        this.ctx.stroke();
      }

      for (let i = 0; i < 21; i++) {
        if (i !== 8) {
          this.ctx.fillStyle = "rgba(25, 113, 194, 0.7)";
          this.ctx.beginPath();
          this.ctx.arc(mappedLms[i][0], mappedLms[i][1], 3, 0, Math.PI * 2);
          this.ctx.fill();
        }
      }
    }

    // Active pointer tip
    this.ctx.fillStyle = this.drawing.isDrawing ? "#1971c2" : "#e03131";
    this.ctx.beginPath();
    this.ctx.arc(u, v, 6, 0, Math.PI * 2);
    this.ctx.fill();

    this.ctx.strokeStyle = this.drawing.isDrawing ? "#1971c2" : "#2f9e44";
    this.ctx.lineWidth = 2.5;
    this.ctx.beginPath();
    this.ctx.arc(u, v, 14, 0, Math.PI * 2);
    this.ctx.stroke();

    this.ctx.restore();
  }

  updateHUD() {
    if (this.hudLoopFps) this.hudLoopFps.textContent = `${this.loopFps.toFixed(1)} FPS`;
    if (this.hudPointerCoords) {
      if (this.pointer.detected) {
        const infStr = this.pointer.inference_time_ms > 0 ? ` (${this.pointer.inference_time_ms}ms)` : "";
        this.hudPointerCoords.textContent = `u: ${this.pointer.snapped_u.toFixed(1)}, v: ${this.pointer.snapped_v.toFixed(1)}${infStr}`;
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

window.addEventListener("DOMContentLoaded", () => {
  const app = new WebWhiteboardApplication();
  app.init();
});

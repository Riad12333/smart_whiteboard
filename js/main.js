/**
 * Main Web Controller for Smart Interactive Whiteboard (Partie 5bis).
 * Integrates:
 *   - Global viewport #hand-cursor overlay (reaches toolbars & full screen)
 *   - Camera-to-viewport mapping with mirror & safety edge margin
 *   - Pure hitTest (elementFromPoint) + MAGNET_RADIUS_PX magnetic snapping
 *   - Mode buttons (Main / Marqueur / Souris) + .hand-mode enlarged targets
 *   - Live Picture-in-Picture #camera-preview screen with skeleton/marker overlay
 */

import { loadSettings } from "./settings.js";
import { WebCamera } from "./camera.js";
import { BoardCalibrator } from "./calibration.js";
import { CoordinateMapper } from "./mapping.js";
import { WebHandMLDetector } from "./detection_ml.js";
import { WebMarkerDetector } from "./detection_marker.js";
import { RemoteHandler } from "./remote.js";
import { DrawingEngine, VISION_SAFE_PALETTE } from "./drawing.js";
import { WhiteboardInterface } from "./interface.js";
import {
  InteractionManager,
  cameraToViewport,
  viewportToCanvas,
} from "./interaction.js";

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

    // Global viewport cursor overlay
    this.cursorCanvas = document.getElementById("hand-cursor");
    this.cursorCtx = this.cursorCanvas.getContext("2d");

    // Small camera preview PiP
    this.camPreviewCard = document.getElementById("camera-preview-card");
    this.camPreviewCanvas = document.getElementById("camera-preview");
    this.camPreviewCtx = this.camPreviewCanvas.getContext("2d");

    this.settings = null;
    this.camera = new WebCamera();
    this.calibrator = null;
    this.mapper = null;

    // Detectors & Remote
    this.mlDetector = new WebHandMLDetector();
    this.markerDetector = new WebMarkerDetector(4);
    this.remote = new RemoteHandler();

    // Drawing, Interface & Interaction
    this.drawing = new DrawingEngine();
    this.ui = new WhiteboardInterface(this.canvas, this.drawing);
    this.interaction = null;

    // Active mode: "HAND_ML", "MARKER", or "MOUSE"
    this.mode = "MOUSE";

    // Global pointer state
    this.pointer = {
      detected: false,
      x: 0.0,
      y: 0.0,
      clientX: 0.0,
      clientY: 0.0,
      insideCanvas: false,
      u: 640.0,
      v: 360.0,
      snapped: false,
      score: 0.0,
      pointing: false,
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
    this.privacyToast = document.getElementById("privacy-toast");
  }

  async init() {
    console.log("=== Initialisation Smart Interactive Whiteboard (Web Edition) ===");

    this.settings = await loadSettings("config/settings.json");

    this.calibrator = new BoardCalibrator(this.settings.board.board_width, this.settings.board.board_height);
    this.mapper = new CoordinateMapper(this.calibrator);

    const magnetRadius = this.settings.interaction?.magnet_radius_px ?? this.settings.interaction?.snap_radius ?? 75.0;
    const dwellMs = this.settings.interaction?.dwell_click_ms ?? 900;
    this.interaction = new InteractionManager(this.canvas, this.ui, this.drawing, magnetRadius, dwellMs);

    this.resizeCanvases();
    window.addEventListener("resize", () => this.resizeCanvases());

    this.setupPointerListeners();
    this.setupUIListeners();

    const camPreviewBadge = document.getElementById("cam-preview-badge");
    if (camPreviewBadge) {
      camPreviewBadge.textContent = "ML CHARGEMENT...";
      camPreviewBadge.className = "badge badge-yellow";
    }

    this.mlDetector.init("./models/wasm", "./models/hand_landmarker.task").then((success) => {
      if (success) {
        console.log("[App] ML HandLandmarker ready.");
        if (camPreviewBadge) {
          camPreviewBadge.textContent = "ML PRET";
          camPreviewBadge.className = "badge badge-green";
        }
      } else {
        if (camPreviewBadge) {
          camPreviewBadge.textContent = "ML ERREUR";
          camPreviewBadge.className = "badge badge-red";
        }
      }
    });

    const camRes = await this.camera.open(
      this.settings.camera.frame_width,
      this.settings.camera.frame_height
    );

    if (camRes.success) {
      this.setMode("HAND_ML");
    } else {
      this.setMode("MOUSE");
    }

    requestAnimationFrame((t) => this.renderLoop(t));
  }

  resizeCanvases() {
    // 1. Resize global viewport cursor overlay
    if (this.cursorCanvas) {
      this.cursorCanvas.width = window.innerWidth;
      this.cursorCanvas.height = window.innerHeight;
    }

    // 2. Resize board canvas keeping 16:9 aspect ratio with margin for toolbar
    const margin = window.innerWidth <= 768 ? 12 : 40;
    const maxW = window.innerWidth - margin;
    const maxH = window.innerHeight - (window.innerWidth <= 768 ? 96 : 112);

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

  async setMode(targetMode) {
    if (targetMode === "HAND_ML" || targetMode === "MARKER") {
      if (!this.camera.hasCamera) {
        const res = await this.camera.open(
          this.settings.camera.frame_width,
          this.settings.camera.frame_height
        );
        if (!res.success) {
          alert(`Impossible d'activer la caméra : ${res.message}`);
          this.setMode("MOUSE");
          return;
        }
      }
      this.mode = targetMode;
      document.body.classList.add("hand-mode");
      this.camPreviewCard?.classList.add("visible");
    } else {
      this.mode = "MOUSE";
      document.body.classList.remove("hand-mode");
      this.camPreviewCard?.classList.remove("visible");
      this.interaction?.clearHover();
      this.pointer.landmarks = null;
      this.pointer.detected = true;
    }

    // Update mode buttons UI
    document.getElementById("btn-mode-hand")?.classList.toggle("active", this.mode === "HAND_ML");
    document.getElementById("btn-mode-marker")?.classList.toggle("active", this.mode === "MARKER");
    document.getElementById("btn-mode-mouse")?.classList.toggle("active", this.mode === "MOUSE");

    this.updateModeUI();
  }

  setupPointerListeners() {
    const getCanvasCoords = (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const clientX = e.clientX !== undefined ? e.clientX : (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
      const clientY = e.clientY !== undefined ? e.clientY : (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
      const pos = viewportToCanvas(clientX, clientY, rect, this.canvas.width, this.canvas.height);
      return [pos.u, pos.v, clientX, clientY, pos.insideCanvas];
    };

    const onPointerMove = (e) => {
      if (this.mode !== "MOUSE") return;
      const [u, v, cx, cy, inside] = getCanvasCoords(e);
      this.pointer.detected = true;
      this.pointer.u = u;
      this.pointer.v = v;
      this.pointer.clientX = cx;
      this.pointer.clientY = cy;
      this.pointer.insideCanvas = inside;

      if (this.ui.activeView !== "HOME") {
        this.drawing.continueStroke(u, v);
      }
    };

    const onPointerDown = (e) => {
      if (this.mode !== "MOUSE" || this.ui.activeView === "HOME") return;
      const [u, v] = getCanvasCoords(e);
      this.ui.addRipple(u, v);
      this.drawing.startStroke(u, v);
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

      sidePanel.classList.toggle("visible", viewName !== "HOME");
      subImages.classList.toggle("visible", viewName === "IMAGES");
      subLesson.classList.toggle("visible", viewName === "LESSON");
    };

    navHome?.addEventListener("click", () => switchView("HOME", navHome));
    navDraw?.addEventListener("click", () => switchView("DRAWING", navDraw));
    navImages?.addEventListener("click", () => switchView("IMAGES", navImages));
    navLesson?.addEventListener("click", () => switchView("LESSON", navLesson));

    // Mode buttons
    document.getElementById("btn-mode-hand")?.addEventListener("click", () => this.setMode("HAND_ML"));
    document.getElementById("btn-mode-marker")?.addEventListener("click", () => this.setMode("MARKER"));
    document.getElementById("btn-mode-mouse")?.addEventListener("click", () => this.setMode("MOUSE"));

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

    // Side Panel: Pen, Eraser, Hold-to-Draw, Undo, Redo, Clear
    const btnPenHold = document.getElementById("btn-pen-hold");
    const btnPen = document.getElementById("btn-tool-pen");
    const btnEraser = document.getElementById("btn-tool-eraser");

    const syncHoldBtn = () => {
      if (!btnPenHold) return;
      btnPenHold.textContent = this.drawing.isDrawing ? "✍️ Tracer : ON" : "✍️ Tracer : OFF";
      btnPenHold.classList.toggle("active", this.drawing.isDrawing);
    };

    btnPenHold?.addEventListener("click", () => {
      if (!this.drawing.isDrawing) {
        this.drawing.startEmptyStroke();
        this.ui.showToast("Stylo posé : bougez la main sur le tableau !");
      } else {
        this.drawing.endStroke();
        this.ui.showToast("Stylo levé");
      }
      syncHoldBtn();
    });

    btnPen?.addEventListener("click", () => {
      this.drawing.setTool("PEN");
      btnPen.classList.add("active");
      btnEraser?.classList.remove("active");
    });

    btnEraser?.addEventListener("click", () => {
      this.drawing.setTool("ERASER");
      btnEraser.classList.add("active");
      btnPen?.classList.remove("active");
    });

    document.getElementById("btn-tool-undo")?.addEventListener("click", () => this.drawing.undo());
    document.getElementById("btn-tool-redo")?.addEventListener("click", () => this.drawing.redo());
    document.getElementById("btn-tool-clear")?.addEventListener("click", () => {
      this.drawing.clear();
      this.ui.showToast("Tableau effacé");
    });

    // Images Zoom & Lesson Controls
    document.getElementById("btn-zoom-in")?.addEventListener("click", () => this.ui.zoomIn());
    document.getElementById("btn-zoom-out")?.addEventListener("click", () => this.ui.zoomOut());
    document.getElementById("btn-zoom-reset")?.addEventListener("click", () => this.ui.resetZoom());
    document.getElementById("btn-lesson-prev")?.addEventListener("click", () => this.ui.prevLessonSlide());
    document.getElementById("btn-lesson-next")?.addEventListener("click", () => this.ui.nextLessonSlide());

    document.getElementById("btn-reset-all")?.addEventListener("click", () => {
      this.ui.resetAll();
      switchView("HOME", navHome);
    });

    const btnFullscreen = document.getElementById("btn-fullscreen");
    btnFullscreen?.addEventListener("click", () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
      } else {
        document.exitFullscreen().catch(() => {});
      }
    });

    // Key Inspector Modal
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

    btnRemoteInspect?.addEventListener("click", toggleInspector);
    btnCloseInspector?.addEventListener("click", () => { inspectorModal.style.display = "none"; });
    document.getElementById("btn-close-privacy")?.addEventListener("click", () => {
      this.privacyToast.style.display = "none";
    });

    // Keyboard & Presentation Remote Listener
    window.addEventListener("keydown", (e) => {
      const remoteRes = this.remote.processKeyEvent(e);

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
        this.interaction.handleRemoteEvent(remoteRes.event, this.pointer);
      }

      if (e.key === "m" || e.key === "M") {
        if (this.mode === "HAND_ML") this.setMode("MARKER");
        else if (this.mode === "MARKER") this.setMode("MOUSE");
        else this.setMode("HAND_ML");
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

    // 2. Computer Vision Tracking & Global Viewport Mapping
    if (this.camera.hasCamera && (this.mode === "HAND_ML" || this.mode === "MARKER")) {
      let rawPtr = null;
      if (this.mode === "HAND_ML" && this.mlDetector.isReady) {
        rawPtr = this.mlDetector.detect(this.camera.video, now);
      } else if (this.mode === "MARKER") {
        rawPtr = this.markerDetector.detect(this.camera.video);
      }

      if (rawPtr && rawPtr.detected) {
        const camW = this.camera.video.videoWidth || 640;
        const camH = this.camera.video.videoHeight || 480;
        const mirror = this.settings.camera?.mirror ?? true;
        const marginPct = this.settings.camera?.edge_margin_pct ?? 0.08;

        const [rawClientX, rawClientY] = cameraToViewport(
          rawPtr.x,
          rawPtr.y,
          camW,
          camH,
          window.innerWidth,
          window.innerHeight,
          mirror,
          marginPct
        );

        const resolved = this.interaction.updateGlobalPointer(
          rawClientX,
          rawClientY,
          Boolean(rawPtr.pinching),
          now
        );

        this.pointer = {
          ...rawPtr,
          clientX: resolved.clientX,
          clientY: resolved.clientY,
          insideCanvas: resolved.insideCanvas,
          u: resolved.u,
          v: resolved.v,
          snapped: resolved.snapped,
          dwellProgress: resolved.dwellProgress,
          pinching: resolved.pinching
        };

        // Support remote-toggled drawing when not using pinch
        if (this.ui.activeView !== "HOME" && this.drawing.isDrawing && !this.interaction.pinchDrawing && resolved.insideCanvas) {
          this.drawing.continueStroke(resolved.u, resolved.v);
        }
      } else {
        this.pointer.detected = false;
        this.pointer.landmarks = null;
        this.pointer.box = null;
        this.interaction.clearHover();
      }

      // Render small camera preview screen
      this.renderCameraPreview(camWOrDefault(this.camera), mirrorOrDefault(this.settings));
    }

    // 3. Render Main Board Canvas
    this.ui.render(this.ctx);

    // 4. Render Global #hand-cursor Overlay (over toolbars & canvas)
    this.renderGlobalCursor();

    // 5. Update HUD telemetry
    this.updateHUD();

    requestAnimationFrame((t) => this.renderLoop(t));
  }

  renderCameraPreview(camDims, mirror) {
    if (!this.camPreviewCtx || !this.camera.hasCamera || this.camera.video.readyState < 2) return;
    const pw = this.camPreviewCanvas.width;
    const ph = this.camPreviewCanvas.height;
    const [vw, vh] = camDims;

    const ctx = this.camPreviewCtx;
    ctx.save();
    ctx.clearRect(0, 0, pw, ph);

    if (mirror) {
      ctx.translate(pw, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(this.camera.video, 0, 0, pw, ph);

    // Draw detected skeleton or box on miniature preview
    const sx = pw / vw;
    const sy = ph / vh;

    if (this.pointer.detected && this.pointer.landmarks && this.pointer.landmarks.length === 21) {
      ctx.strokeStyle = "#74c0fc";
      ctx.lineWidth = 1.5;
      for (const [p1, p2] of HAND_CONNECTIONS) {
        ctx.beginPath();
        ctx.moveTo(this.pointer.landmarks[p1][0] * sx, this.pointer.landmarks[p1][1] * sy);
        ctx.lineTo(this.pointer.landmarks[p2][0] * sx, this.pointer.landmarks[p2][1] * sy);
        ctx.stroke();
      }
      const tip = this.pointer.landmarks[8];
      ctx.fillStyle = "#ff6b6b";
      ctx.beginPath();
      ctx.arc(tip[0] * sx, tip[1] * sy, 4, 0, Math.PI * 2);
      ctx.fill();
    } else if (this.pointer.detected && this.pointer.box) {
      const [bx1, by1, bx2, by2] = this.pointer.box;
      ctx.strokeStyle = "#51cf66";
      ctx.lineWidth = 2;
      ctx.strokeRect(bx1 * sx, by1 * sy, (bx2 - bx1) * sx, (by2 - by1) * sy);
    }
    ctx.restore();
  }

  renderGlobalCursor() {
    if (!this.cursorCtx) return;
    const ctx = this.cursorCtx;
    ctx.clearRect(0, 0, this.cursorCanvas.width, this.cursorCanvas.height);

    // In MOUSE mode, we only draw the cursor if over canvas (OS cursor handles toolbars)
    if (this.mode === "MOUSE") {
      if (!this.pointer.insideCanvas) return;
    } else {
      if (!this.pointer.detected) return;
    }

    const cx = this.pointer.clientX;
    const cy = this.pointer.clientY;

    ctx.save();

    // Inner dot (blue when pen is down / pinching, red when hovering)
    const isPenActive = this.drawing.isDrawing || this.pointer.pinching;
    ctx.fillStyle = isPenActive ? "#1971c2" : "#e03131";
    ctx.beginPath();
    ctx.arc(cx, cy, isPenActive ? 8 : 6, 0, Math.PI * 2);
    ctx.fill();

    // Outer ring (purple when snapped to button, green when free)
    const ringRadius = this.pointer.snapped ? 20 : 14;
    ctx.strokeStyle = this.pointer.snapped ? "#6965db" : (isPenActive ? "#1971c2" : "#2f9e44");
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(cx, cy, ringRadius, 0, Math.PI * 2);
    ctx.stroke();

    // Dwell-Click progress arc (fills up over 0.9s when hovering a button)
    if (this.pointer.dwellProgress > 0.02) {
      ctx.strokeStyle = "#6741d9";
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(cx, cy, ringRadius + 5, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * this.pointer.dwellProgress);
      ctx.stroke();
    }

    ctx.restore();
  }

  updateHUD() {
    if (this.hudLoopFps) this.hudLoopFps.textContent = `${this.loopFps.toFixed(1)} FPS`;
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

function camWOrDefault(cam) {
  return [cam.video?.videoWidth || 640, cam.video?.videoHeight || 480];
}

function mirrorOrDefault(settings) {
  return settings?.camera?.mirror ?? true;
}

window.addEventListener("DOMContentLoaded", () => {
  const app = new WebWhiteboardApplication();
  app.init();
});

/**
 * Global Viewport Interaction, Hit-Testing & Magnetic Snapping (Partie 5bis).
 * Decouples hand/marker pointer from canvas bounds so it can reach the entire window
 * (including HTML toolbars) while keeping canvas (u, v) mapping for drawing.
 */

/**
 * Convert smoothed camera coordinates (camX, camY) into full-window viewport coordinates (clientX, clientY).
 * Applies horizontal mirroring (for selfie webcams) and an edge safety margin so the user
 * can comfortably reach top toolbars and screen edges.
 */
export function cameraToViewport(
  camX,
  camY,
  camW,
  camH,
  viewW,
  viewH,
  mirror = true,
  edgeMarginPct = 0.08
) {
  let nx = camX / Math.max(1, camW);
  let ny = camY / Math.max(1, camH);

  if (mirror) {
    nx = 1.0 - nx;
  }

  // Remap [edgeMarginPct, 1 - edgeMarginPct] -> [0, 1]
  const m = Math.max(0.0, Math.min(0.4, edgeMarginPct));
  const span = 1.0 - 2.0 * m;
  const rx = (nx - m) / span;
  const ry = (ny - m) / span;

  const clientX = Math.max(0, Math.min(viewW, rx * viewW));
  const clientY = Math.max(0, Math.min(viewH, ry * viewH));

  return [clientX, clientY];
}

/**
 * Convert viewport coordinates (clientX, clientY) into canvas coordinates (u, v)
 * when the pointer is over the canvas.
 */
export function viewportToCanvas(clientX, clientY, canvasRect, canvasWidth, canvasHeight) {
  if (!canvasRect || canvasRect.width <= 0 || canvasRect.height <= 0) {
    return { insideCanvas: false, u: 0, v: 0 };
  }

  const insideCanvas =
    clientX >= canvasRect.left &&
    clientX <= canvasRect.right &&
    clientY >= canvasRect.top &&
    clientY <= canvasRect.bottom;

  const u = ((clientX - canvasRect.left) / canvasRect.width) * canvasWidth;
  const v = ((clientY - canvasRect.top) / canvasRect.height) * canvasHeight;

  return {
    insideCanvas,
    u: Math.max(0, Math.min(canvasWidth, u)),
    v: Math.max(0, Math.min(canvasHeight, v))
  };
}

/**
 * Pure hit-test using document.elementFromPoint (or injected function for Node tests).
 * Returns the interactive target element ([data-hand-target] or [data-action]) under (clientX, clientY), or null.
 */
export function hitTest(clientX, clientY, elementFromPointFn = null) {
  const fn = elementFromPointFn || (typeof document !== "undefined" ? (x, y) => document.elementFromPoint(x, y) : null);
  if (!fn) return null;

  const el = fn(clientX, clientY);
  if (!el) return null;

  if (typeof el.closest === "function") {
    return el.closest("[data-hand-target], [data-action]");
  }
  // Support lightweight mock elements in Node unit tests
  if (el.dataset && (el.dataset.handTarget !== undefined || el.dataset.action !== undefined)) {
    return el;
  }
  return null;
}

/**
 * Find the nearest interactive target within magnetRadiusPx of (clientX, clientY).
 * Computes distance to the element's bounding box edge and snaps to its center.
 */
export function findMagneticTarget(clientX, clientY, targets, magnetRadiusPx = 75.0) {
  let bestTarget = null;
  let bestEdgeDist = magnetRadiusPx;
  let bestCenterDist = Infinity;
  let snapX = clientX;
  let snapY = clientY;

  for (const el of targets) {
    // Skip hidden elements in browser
    if (typeof window !== "undefined" && el.offsetParent === null) continue;

    const rect = el.getBoundingClientRect();
    if (!rect || rect.width === 0 || rect.height === 0) continue;

    const dx = Math.max(rect.left - clientX, 0, clientX - rect.right);
    const dy = Math.max(rect.top - clientY, 0, clientY - rect.bottom);
    const edgeDist = Math.hypot(dx, dy);

    if (edgeDist <= magnetRadiusPx) {
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const centerDist = Math.hypot(clientX - cx, clientY - cy);

      if (edgeDist < bestEdgeDist || (edgeDist === bestEdgeDist && centerDist < bestCenterDist)) {
        bestEdgeDist = edgeDist;
        bestCenterDist = centerDist;
        bestTarget = el;
        snapX = cx;
        snapY = cy;
      }
    }
  }

  if (!bestTarget) return null;
  return {
    target: bestTarget,
    snapX,
    snapY,
    distance: bestEdgeDist
  };
}

/**
 * Resolve final global pointer coordinates, hover target, and magnetic snap state.
 */
export function resolveHandPointer(clientX, clientY, options = {}) {
  const {
    elementFromPointFn = null,
    targets = null,
    magnetRadiusPx = 75.0
  } = options;

  // 1. Direct hit test under cursor
  const directHit = hitTest(clientX, clientY, elementFromPointFn);
  if (directHit) {
    return {
      clientX,
      clientY,
      hoveredTarget: directHit,
      snapped: false
    };
  }

  // 2. Magnetic attraction if no direct hit
  const targetList = targets || (typeof document !== "undefined" ? document.querySelectorAll("[data-hand-target]") : []);
  const magnet = findMagneticTarget(clientX, clientY, targetList, magnetRadiusPx);
  if (magnet) {
    return {
      clientX: magnet.snapX,
      clientY: magnet.snapY,
      hoveredTarget: magnet.target,
      snapped: true
    };
  }

  // 3. Free space
  return {
    clientX,
    clientY,
    hoveredTarget: null,
    snapped: false
  };
}

export class InteractionManager {
  constructor(canvas, uiInterface, drawingEngine, magnetRadiusPx = 75.0) {
    this.canvas = canvas;
    this.ui = uiInterface;
    this.drawing = drawingEngine;
    this.magnetRadiusPx = magnetRadiusPx;
    this.hoveredTarget = null;
  }

  /**
   * Resolve global viewport position, update .hand-hover CSS state, and return canvas (u, v).
   */
  updateGlobalPointer(rawClientX, rawClientY) {
    const resolved = resolveHandPointer(rawClientX, rawClientY, {
      magnetRadiusPx: this.magnetRadiusPx
    });

    // Update .hand-hover class
    if (this.hoveredTarget && this.hoveredTarget !== resolved.hoveredTarget) {
      this.hoveredTarget.classList.remove("hand-hover");
    }
    if (resolved.hoveredTarget) {
      resolved.hoveredTarget.classList.add("hand-hover");
    }
    this.hoveredTarget = resolved.hoveredTarget;

    // Map viewport coordinates to canvas coordinates
    const rect = this.canvas.getBoundingClientRect();
    const canvasPos = viewportToCanvas(
      resolved.clientX,
      resolved.clientY,
      rect,
      this.canvas.width,
      this.canvas.height
    );

    return {
      clientX: resolved.clientX,
      clientY: resolved.clientY,
      hoveredTarget: resolved.hoveredTarget,
      snapped: resolved.snapped,
      insideCanvas: canvasPos.insideCanvas,
      u: canvasPos.u,
      v: canvasPos.v
    };
  }

  clearHover() {
    if (this.hoveredTarget) {
      this.hoveredTarget.classList.remove("hand-hover");
      this.hoveredTarget = null;
    }
  }

  /**
   * Handle discrete remote click (LEFT_CLICK / RIGHT_CLICK) at current global pointer state.
   */
  handleRemoteEvent(eventName, pointerState) {
    if (!eventName) return;

    if (eventName === "LEFT_CLICK") {
      // 1. If hovering a UI button, trigger its click!
      if (this.hoveredTarget) {
        this.hoveredTarget.click();
        return;
      }

      // 2. If over the canvas (and not on HOME screen), toggle pen down/up
      if (pointerState.insideCanvas && this.ui.activeView !== "HOME") {
        this.ui.addRipple(pointerState.u, pointerState.v);
        if (!this.drawing.isDrawing) {
          this.drawing.startStroke(pointerState.u, pointerState.v);
        } else {
          this.drawing.endStroke();
        }
      }
    } else if (eventName === "RIGHT_CLICK") {
      if (this.drawing.isDrawing) {
        this.drawing.endStroke();
      }
      if (this.ui.activeView !== "HOME" && this.drawing.strokeHistory.length > 0) {
        this.drawing.undo();
        this.ui.showToast("Trait annulé (Undo)");
      } else {
        const homeBtn = document.getElementById("btn-nav-home");
        if (homeBtn) homeBtn.click();
        else this.ui.setView("HOME");
      }
    }
  }
}

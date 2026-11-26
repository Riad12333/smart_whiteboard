/**
 * Interaction & Magnetic Snapping Manager for Web Edition (Partie 5).
 * Features:
 *   - Magnetic cursor snapping within SNAP_RADIUS (75px) to DOM toolbar buttons
 *   - Routes pointer + remote click events (LEFT_CLICK / RIGHT_CLICK) to UI actions
 *   - Prevents physiological hand jitter when hovering interactive controls
 */

export class InteractionManager {
  constructor(canvas, uiInterface, drawingEngine, snapRadiusPx = 75.0) {
    this.canvas = canvas;
    this.ui = uiInterface;
    this.drawing = drawingEngine;
    this.snapRadius = snapRadiusPx;
    this.hoveredButton = null;
  }

  /**
   * Apply magnetic snapping against visible interactive buttons (>= 90px targets).
   * Converts DOM button client rects into canvas (u, v) coordinates.
   * @param {number} u - Raw board X
   * @param {number} v - Raw board Y
   * @returns {{u: number, v: number, snappedButton: HTMLElement|null}}
   */
  applyMagneticSnap(u, v) {
    const rect = this.canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) {
      return { u, v, snappedButton: null };
    }

    const scaleX = this.canvas.width / rect.width;
    const scaleY = this.canvas.height / rect.height;

    const buttons = document.querySelectorAll(".snap-target");
    let closestBtn = null;
    let minDist = this.snapRadius;
    let snapU = u;
    let snapV = v;

    for (const btn of buttons) {
      // Skip hidden elements
      if (btn.offsetParent === null) continue;

      const bRect = btn.getBoundingClientRect();
      const centerU = ((bRect.left + bRect.width / 2) - rect.left) * scaleX;
      const centerV = ((bRect.top + bRect.height / 2) - rect.top) * scaleY;

      const dist = Math.hypot(u - centerU, v - centerV);
      if (dist < minDist) {
        minDist = dist;
        closestBtn = btn;
        snapU = centerU;
        snapV = centerV;
      }

      btn.classList.remove("snap-hover");
    }

    if (closestBtn) {
      closestBtn.classList.add("snap-hover");
    }
    this.hoveredButton = closestBtn;

    return { u: snapU, v: snapV, snappedButton: closestBtn };
  }

  /**
   * Handle discrete remote click at current snapped position.
   */
  handleRemoteEvent(eventName, u, v) {
    if (!eventName) return;

    if (eventName === "LEFT_CLICK") {
      this.ui.addRipple(u, v);

      // If snapped on a UI button, click it!
      if (this.hoveredButton) {
        this.hoveredButton.click();
        return;
      }

      // Otherwise, in Drawing/Lesson/Images views, toggle pen down/up
      if (this.ui.activeView !== "HOME") {
        if (!this.drawing.isDrawing) {
          this.drawing.startStroke(u, v);
        } else {
          this.drawing.endStroke();
        }
      }
    } else if (eventName === "RIGHT_CLICK") {
      if (this.ui.activeView !== "HOME" && this.drawing.strokeHistory.length > 0) {
        this.drawing.undo();
        this.ui.showToast("Trait annulé (Undo)");
      } else {
        this.ui.setView("HOME");
      }
    }
  }
}

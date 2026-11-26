/**
 * Drawing Engine for Smart Interactive Whiteboard (Web Edition - Partie 5).
 * Manages vector strokes, colors, thickness, Undo/Redo, Eraser, and Canvas rendering
 * using pure stateless transitions from core_logic.js.
 */

import {
  create_stroke,
  add_point_to_stroke,
  undo_stroke,
  redo_stroke,
} from "./core_logic.js";

export const VISION_SAFE_PALETTE = {
  BLACK: [30, 30, 30],     // #1e1e1e
  BLUE: [25, 113, 194],    // #1971c2
  RED: [224, 49, 49],      // #e03131
  PURPLE: [103, 65, 217],  // #6741d9
};

export class DrawingEngine {
  constructor() {
    this.strokeHistory = [];
    this.redoStack = [];
    this.currentStroke = null;
    this.isDrawing = false;

    this.tool = "PEN"; // "PEN" | "ERASER"
    this.color = [...VISION_SAFE_PALETTE.BLACK];
    this.penThickness = 7;
    this.eraserThickness = 35;
  }

  setTool(toolName) {
    this.tool = toolName === "ERASER" ? "ERASER" : "PEN";
  }

  setColor(rgbArray) {
    this.color = [...rgbArray];
    this.tool = "PEN";
  }

  setThickness(px) {
    this.penThickness = Number(px);
  }

  startEmptyStroke() {
    this.isDrawing = true;
    const thickness = this.tool === "ERASER" ? this.eraserThickness : this.penThickness;
    this.currentStroke = create_stroke(this.tool, this.color, thickness);
  }

  startStroke(u, v) {
    this.isDrawing = true;
    const thickness = this.tool === "ERASER" ? this.eraserThickness : this.penThickness;
    this.currentStroke = create_stroke(this.tool, this.color, thickness);
    this.currentStroke = add_point_to_stroke(this.currentStroke, u, v);
  }

  continueStroke(u, v) {
    if (!this.isDrawing || !this.currentStroke) return;
    const pts = this.currentStroke.points;
    if (pts.length > 0) {
      const last = pts[pts.length - 1];
      if (Math.hypot(u - last[0], v - last[1]) < 2.0) return; // avoid duplicate micro-points
    }
    this.currentStroke = add_point_to_stroke(this.currentStroke, u, v);
  }

  endStroke() {
    if (this.isDrawing && this.currentStroke && this.currentStroke.points.length > 0) {
      this.strokeHistory.push(this.currentStroke);
      this.redoStack = [];
    }
    this.isDrawing = false;
    this.currentStroke = null;
  }

  undo() {
    if (this.isDrawing) this.endStroke();
    [this.strokeHistory, this.redoStack] = undo_stroke(this.strokeHistory, this.redoStack);
  }

  redo() {
    if (this.isDrawing) this.endStroke();
    [this.strokeHistory, this.redoStack] = redo_stroke(this.strokeHistory, this.redoStack);
  }

  clear() {
    this.strokeHistory = [];
    this.redoStack = [];
    this.currentStroke = null;
    this.isDrawing = false;
  }

  render(ctx) {
    const allStrokes = [...this.strokeHistory];
    if (this.currentStroke && this.currentStroke.points.length > 0) {
      allStrokes.push(this.currentStroke);
    }

    for (const stroke of allStrokes) {
      const pts = stroke.points;
      if (!pts || pts.length === 0) continue;

      ctx.save();
      ctx.lineWidth = stroke.thickness;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";

      if (stroke.tool === "ERASER") {
        ctx.strokeStyle = "#fbfbfc";
      } else {
        const [r, g, b] = stroke.color;
        ctx.strokeStyle = `rgb(${r}, ${g}, ${b})`;
      }

      ctx.beginPath();
      if (pts.length === 1) {
        ctx.fillStyle = ctx.strokeStyle;
        ctx.arc(pts[0][0], pts[0][1], stroke.thickness / 2, 0, Math.PI * 2);
        ctx.fill();
      } else {
        ctx.moveTo(pts[0][0], pts[0][1]);
        for (let i = 1; i < pts.length; i++) {
          ctx.lineTo(pts[i][0], pts[i][1]);
        }
        ctx.stroke();
      }
      ctx.restore();
    }
  }
}

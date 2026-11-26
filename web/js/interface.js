/**
 * Interface & Views Controller for Smart Interactive Whiteboard (Web Edition - Partie 5).
 * Manages:
 *   - Multi-view navigation: HOME, DRAWING, IMAGES (+ Zoom), LESSON (Interactive Mini-Lesson)
 *   - Excalidraw-inspired rendering, local Caveat font, and visual click ripples
 *   - Lesson slides with live drawing annotation support
 *   - Image viewer with smooth Zoom In / Out / Reset
 */

const LESSON_SLIDES = [
  {
    title: "1. Détection & Espace Couleur (YCrCb vs ML)",
    subtitle: "Pourquoi passer du seuillage chromatique aux réseaux de neurones",
    bullets: [
      "• YCrCb (ITU-R BT.601) isole la chrominance (Cr, Cb) de la luminance (Y).",
      "• Limite sous projecteur : la lumière projetée modifie Cr/Cb et fait chuter la détection.",
      "• Solution ML : Palm Detection + 21 Landmarks restent stables malgré les ombres.",
      "• Point de pointage unique : Landmark 8 (extrémité de l'index)."
    ],
    formula: "Cr = 0.5R - 0.4187G - 0.0813B + 128"
  },
  {
    title: "2. Calibration Géométrique (Homographie DLT)",
    subtitle: "Projeter la caméra (640x480) vers le tableau (1280x720)",
    bullets: [
      "• 4 correspondances de coins suffisent pour estimer la matrice projective H (3x3).",
      "• Chaque paire génère 2 équations linéaires -> Système Ah = b (8x8).",
      "• Résolution maison par élimination de Gauss-Jordan avec pivot partiel.",
      "• Validation continue par mesure de l'erreur moyenne de reprojection en pixels."
    ],
    formula: "[u, v, 1]^T  ~  H · [x, y, 1]^T"
  },
  {
    title: "3. Stabilisation Temporelle (Filtre 1€ & Deadzone)",
    subtitle: "Supprimer le tremblement sans introduire de latence",
    bullets: [
      "• Un filtre EMA statique crée un compromis entre stabilité et retard (lag).",
      "• Le filtre 1€ (Casiez et al.) adapte sa fréquence de coupure fc selon la vitesse.",
      "• À l'arrêt (v ≈ 0) : fc = 1.0 Hz -> lissage maximal contre le tremblement.",
      "• En mouvement rapide : fc augmente -> le curseur suit instantanément."
    ],
    formula: "fc = fc_min + β · |dx/dt|"
  }
];

export class WhiteboardInterface {
  constructor(canvas, drawingEngine) {
    this.canvas = canvas;
    this.drawing = drawingEngine;

    this.activeView = "HOME"; // "HOME" | "DRAWING" | "IMAGES" | "LESSON"
    this.zoomLevel = 1.0;
    this.lessonIndex = 0;

    // Lesson diagram image
    this.lessonImage = new Image();
    this.lessonImageLoaded = false;
    this.lessonImage.onload = () => {
      this.lessonImageLoaded = true;
    };
    this.lessonImage.src = "assets/lesson_diagram.png";

    // Click ripple visual feedback
    this.ripples = [];
    this.toastMessage = "";
    this.toastUntil = 0;
  }

  setView(viewName) {
    const valid = ["HOME", "DRAWING", "IMAGES", "LESSON"];
    if (valid.includes(viewName)) {
      this.activeView = viewName;
      this.showToast(`Vue active : ${viewName}`);
    }
  }

  zoomIn() {
    this.zoomLevel = Math.min(3.5, Math.round((this.zoomLevel + 0.3) * 10) / 10);
    this.showToast(`Zoom : ${Math.round(this.zoomLevel * 100)}%`);
  }

  zoomOut() {
    this.zoomLevel = Math.max(0.5, Math.round((this.zoomLevel - 0.3) * 10) / 10);
    this.showToast(`Zoom : ${Math.round(this.zoomLevel * 100)}%`);
  }

  resetZoom() {
    this.zoomLevel = 1.0;
    this.showToast("Zoom réinitialisé (100%)");
  }

  nextLessonSlide() {
    this.lessonIndex = (this.lessonIndex + 1) % LESSON_SLIDES.length;
  }

  prevLessonSlide() {
    this.lessonIndex = (this.lessonIndex - 1 + LESSON_SLIDES.length) % LESSON_SLIDES.length;
  }

  addRipple(u, v) {
    this.ripples.push({ u, v, startTime: performance.now() });
  }

  showToast(msg, durationMs = 2000) {
    this.toastMessage = msg;
    this.toastUntil = performance.now() + durationMs;
  }

  resetAll() {
    this.drawing.clear();
    this.zoomLevel = 1.0;
    this.lessonIndex = 0;
    this.activeView = "HOME";
    this.showToast("Système réinitialisé");
  }

  /**
   * Render active view background + annotations + ripples + toast onto Canvas 2D.
   */
  render(ctx) {
    const w = this.canvas.width;
    const h = this.canvas.height;

    // 1. Crisp Excalidraw off-white background
    ctx.fillStyle = "#fbfbfc";
    ctx.fillRect(0, 0, w, h);

    // Subtle dot grid
    ctx.fillStyle = "#dadee5";
    for (let gx = 24; gx < w; gx += 32) {
      for (let gy = 24; gy < h; gy += 32) {
        ctx.fillRect(gx, gy, 2, 2);
      }
    }

    // 2. View-specific content
    if (this.activeView === "HOME") {
      this._renderHome(ctx, w, h);
    } else if (this.activeView === "IMAGES") {
      this._renderImages(ctx, w, h);
    } else if (this.activeView === "LESSON") {
      this._renderLesson(ctx, w, h);
    }

    // 3. Always render drawing strokes on top (allows annotating images and lessons!)
    if (this.activeView !== "HOME") {
      this.drawing.render(ctx);
    }

    // 4. Render click ripples
    const now = performance.now();
    this.ripples = this.ripples.filter(r => now - r.startTime < 350);
    for (const r of this.ripples) {
      const progress = (now - r.startTime) / 350;
      const radius = 10 + progress * 35;
      const alpha = 1.0 - progress;
      ctx.save();
      ctx.strokeStyle = `rgba(105, 101, 219, ${alpha})`;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(r.u, r.v, radius, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }

    // 5. Render contextual toast pill
    if (now < this.toastUntil && this.toastMessage) {
      ctx.save();
      ctx.font = "600 15px system-ui, sans-serif";
      const textW = ctx.measureText(this.toastMessage).width;
      const boxW = textW + 32;
      const boxX = (w - boxW) / 2;
      const boxY = h - 62;
      ctx.fillStyle = "rgba(30, 30, 30, 0.88)";
      ctx.beginPath();
      ctx.roundRect(boxX, boxY, boxW, 34, 17);
      ctx.fill();
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(this.toastMessage, w / 2, boxY + 17);
      ctx.restore();
    }
  }

  _renderHome(ctx, w, h) {
    ctx.save();
    ctx.textAlign = "center";
    ctx.fillStyle = "#1e1e1e";
    ctx.font = "700 54px 'Caveat', cursive, system-ui";
    ctx.fillText("Smart Interactive Whiteboard", w / 2, h / 2 - 70);

    ctx.fillStyle = "#6965db";
    ctx.font = "600 24px system-ui, sans-serif";
    ctx.fillText("USTHB Master Informatique — Vision par Ordinateur (2026-2027)", w / 2, h / 2 - 20);

    ctx.fillStyle = "#73737d";
    ctx.font = "400 18px system-ui, sans-serif";
    ctx.fillText("Utilisez la barre d'outils ci-dessus pour Dessiner, Explorer les Images ou Lancer la Mini-Leçon.", w / 2, h / 2 + 35);
    ctx.fillText("Astuce : Approchez le pointeur d'un bouton pour activer le magnétisme anti-tremblement (75 px).", w / 2, h / 2 + 70);
    ctx.restore();
  }

  _renderImages(ctx, w, h) {
    ctx.save();
    if (this.lessonImageLoaded) {
      const baseScale = Math.min((w * 0.7) / this.lessonImage.width, (h * 0.65) / this.lessonImage.height);
      const drawW = this.lessonImage.width * baseScale * this.zoomLevel;
      const drawH = this.lessonImage.height * baseScale * this.zoomLevel;
      const dx = (w - drawW) / 2;
      const dy = (h - drawH) / 2 + 20;

      ctx.strokeStyle = "#282828";
      ctx.lineWidth = 2;
      ctx.strokeRect(dx - 2, dy - 2, drawW + 4, drawH + 4);
      ctx.drawImage(this.lessonImage, dx, dy, drawW, drawH);
    } else {
      ctx.fillStyle = "#73737d";
      ctx.textAlign = "center";
      ctx.font = "600 20px system-ui, sans-serif";
      ctx.fillText("Chargement du diagramme pédagogique...", w / 2, h / 2);
    }
    ctx.restore();
  }

  _renderLesson(ctx, w, h) {
    const slide = LESSON_SLIDES[this.lessonIndex];
    ctx.save();

    // Card container
    const cardW = 940;
    const cardH = 440;
    const cardX = (w - cardW) / 2;
    const cardY = 140;

    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = "#282828";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(cardX, cardY, cardW, cardH, 16);
    ctx.fill();
    ctx.stroke();

    // Slide header
    ctx.fillStyle = "#6965db";
    ctx.font = "700 36px 'Caveat', cursive, system-ui";
    ctx.fillText(slide.title, cardX + 40, cardY + 58);

    ctx.fillStyle = "#73737d";
    ctx.font = "500 18px system-ui, sans-serif";
    ctx.fillText(slide.subtitle, cardX + 40, cardY + 92);

    // Divider
    ctx.strokeStyle = "#eeedfe";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cardX + 40, cardY + 112);
    ctx.lineTo(cardX + cardW - 40, cardY + 112);
    ctx.stroke();

    // Bullet points
    ctx.fillStyle = "#1e1e1e";
    ctx.font = "400 20px system-ui, sans-serif";
    slide.bullets.forEach((line, idx) => {
      ctx.fillText(line, cardX + 40, cardY + 160 + idx * 48);
    });

    // Formula box
    ctx.fillStyle = "#eeedfe";
    ctx.beginPath();
    ctx.roundRect(cardX + 40, cardY + 355, cardW - 80, 52, 10);
    ctx.fill();
    ctx.fillStyle = "#5c56df";
    ctx.font = "700 20px monospace";
    ctx.textAlign = "center";
    ctx.fillText(slide.formula, cardX + cardW / 2, cardY + 388);

    // Slide counter
    ctx.textAlign = "right";
    ctx.fillStyle = "#73737d";
    ctx.font = "600 14px system-ui, sans-serif";
    ctx.fillText(`Diapositive ${this.lessonIndex + 1} / ${LESSON_SLIDES.length}`, cardX + cardW - 30, cardY + 36);

    ctx.restore();
  }
}

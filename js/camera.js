/**
 * Camera Acquisition Module for Smart Interactive Whiteboard (Web Version).
 * Handles getUserMedia on localhost / HTTPS, graceful fallback to MOUSE mode
 * when camera is unavailable or permission is denied, and explicit privacy guarantees.
 */

import { getSettings } from "./settings.js";

export class WebCamera {
  constructor() {
    this.video = document.createElement("video");
    this.video.setAttribute("autoplay", "");
    this.video.setAttribute("muted", "");
    this.video.setAttribute("playsinline", "");
    this.video.style.display = "none";
    document.body.appendChild(this.video);

    this.stream = null;
    this.hasCamera = false;
    this.statusMessage = "Non initialisé";
    this.errorReason = null;

    // Measurement & FPS
    this.lastFrameTime = performance.now();
    this.fps = 0.0;
    this.fpsHistory = [];
  }

  /**
   * Check if current origin supports getUserMedia (secure context: https or localhost).
   */
  isSecureContext() {
    if (typeof window === "undefined") return false;
    const isLocal = window.location.hostname === "localhost" ||
                    window.location.hostname === "127.0.0.1" ||
                    window.location.hostname === "[::1]";
    return window.isSecureContext || isLocal;
  }

  /**
   * Request webcam stream with graceful fallback to MOUSE mode.
   * @param {number} [targetWidth=640]
   * @param {number} [targetHeight=480]
   * @returns {Promise<{success: boolean, mode: string, message: string}>}
   */
  async open(targetWidth = 640, targetHeight = 480) {
    const settings = getSettings();
    const w = targetWidth || settings.camera.frame_width || 640;
    const h = targetHeight || settings.camera.frame_height || 480;

    if (!this.isSecureContext()) {
      this.hasCamera = false;
      this.errorReason = "INSECURE_CONTEXT";
      this.statusMessage = "Caméra désactivée : contexte non sécurisé (HTTPS ou localhost requis). Mode SOURIS activé.";
      console.warn(`[WebCamera] ${this.statusMessage}`);
      return { success: false, mode: "MOUSE", message: this.statusMessage };
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      this.hasCamera = false;
      this.errorReason = "API_UNSUPPORTED";
      this.statusMessage = "L'API MediaDevices n'est pas supportée par ce navigateur. Mode SOURIS activé.";
      console.warn(`[WebCamera] ${this.statusMessage}`);
      return { success: false, mode: "MOUSE", message: this.statusMessage };
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: w },
          height: { ideal: h },
          facingMode: "user"
        },
        audio: false
      });

      this.video.srcObject = this.stream;
      await this.video.play();

      this.hasCamera = true;
      this.statusMessage = `Caméra active (${this.video.videoWidth}x${this.video.videoHeight})`;
      console.log(`[WebCamera] ${this.statusMessage}`);
      return { success: true, mode: "CAMERA", message: this.statusMessage };
    } catch (err) {
      this.hasCamera = false;
      this.errorReason = err.name || "UNKNOWN_ERROR";

      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        this.statusMessage = "Accès caméra refusé par l'utilisateur. Mode SOURIS activé par défaut.";
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        this.statusMessage = "Aucune caméra détectée sur cet appareil. Mode SOURIS activé par défaut.";
      } else {
        this.statusMessage = `Impossible d'ouvrir la caméra (${err.message}). Mode SOURIS activé.`;
      }

      console.warn(`[WebCamera] ${this.statusMessage}`);
      return { success: false, mode: "MOUSE", message: this.statusMessage };
    }
  }

  /**
   * Stop webcam tracks cleanly.
   */
  stop() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    this.hasCamera = false;
    this.statusMessage = "Caméra arrêtée.";
  }

  /**
   * Update and return video acquisition FPS.
   */
  updateFps() {
    const now = performance.now();
    const dt = now - this.lastFrameTime;
    this.lastFrameTime = now;

    if (dt > 0) {
      const instantFps = 1000.0 / dt;
      this.fpsHistory.push(instantFps);
      if (this.fpsHistory.length > 15) {
        this.fpsHistory.shift();
      }
      const sum = this.fpsHistory.reduce((acc, v) => acc + v, 0);
      this.fps = Math.round((sum / this.fpsHistory.length) * 10) / 10;
    }
    return this.fps;
  }
}

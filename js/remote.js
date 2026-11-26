/**
 * Presentation Remote Controller Module for Web (Step 4quinquies - Partie 4).
 * Handles HID presentation clicker and keyboard events:
 *   - Configurable key tables loaded from settings.json
 *   - Debouncing (debounce_sec) and key repeat suppression
 *   - Conforms strictly to docs/PROTOCOL.md
 *   - Interactive "Key Inspector" panel for hardware debugging
 */

import { getSettings } from "./settings.js";

export class RemoteHandler {
  constructor(debounceSec = 0.25) {
    this.debounceMs = debounceSec * 1000.0;
    this.lastEventTime = -Infinity;
    this.lastEvent = null;
    this.lastRawKey = null;
    this.lastRawCode = null;

    // Callbacks for live event dispatching
    this.listeners = [];
  }

  /**
   * Process a KeyboardEvent and map to discrete presentation click event.
   * Conforms strictly to docs/PROTOCOL.md.
   * @param {KeyboardEvent} e
   * @returns {Object|null} { event: "LEFT_CLICK" | "RIGHT_CLICK" | null, ... }
   */
  processKeyEvent(e) {
    // 1. Ignore hardware key hold repetition
    if (e.repeat) {
      return null;
    }

    const now = performance.now();
    this.lastRawKey = e.key;
    this.lastRawCode = e.code;

    const settings = getSettings();
    const rem = settings.remote || {};
    const nextKeys = rem.next_keys || ["PageDown", "ArrowRight", "n", "N", "d", "D", " "];
    const prevKeys = rem.prev_keys || ["PageUp", "ArrowLeft", "p", "P", "g", "G", "Backspace"];

    let detectedEvent = null;

    if (nextKeys.includes(e.key) || nextKeys.includes(e.code)) {
      detectedEvent = "LEFT_CLICK";
    } else if (prevKeys.includes(e.key) || prevKeys.includes(e.code)) {
      detectedEvent = "RIGHT_CLICK";
    }

    // 2. Debounce temporal filter
    if (detectedEvent !== null) {
      if (now - this.lastEventTime < this.debounceMs) {
        // Discard bounced signal
        return null;
      }
      this.lastEventTime = now;
      this.lastEvent = detectedEvent;
    }

    const payload = {
      event: detectedEvent,
      timestamp: Date.now() / 1000.0,
      source: "KEYBOARD_REMOTE",
      raw_key: e.key,
      raw_code: e.code
    };

    if (detectedEvent !== null) {
      this.notify(payload);
    }

    return payload;
  }

  addListener(callback) {
    if (typeof callback === "function") {
      this.listeners.push(callback);
    }
  }

  notify(eventPayload) {
    for (const cb of this.listeners) {
      try {
        cb(eventPayload);
      } catch (err) {
        console.error("[RemoteHandler] Error in listener:", err);
      }
    }
  }
}

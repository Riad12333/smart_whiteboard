import test from "node:test";
import assert from "node:assert/strict";

import { OneEuroFilter, verifyPointingPosture } from "../js/detection_ml.js";
import { rgbToHsv } from "../js/detection_marker.js";

test("OneEuroFilter reduces static high-frequency noise", () => {
  const f = new OneEuroFilter(1.0, 0.01);
  const dt = 1.0 / 60.0;
  let t = 0.0;
  const rawValues = [];
  const filteredValues = [];

  for (let i = 0; i < 30; i++) {
    t += dt;
    const noisy = 100.0 + (i % 2 === 0 ? 0.5 : -0.5);
    rawValues.push(noisy);
    filteredValues.push(f.filter(noisy, t));
  }

  // Calculate variance of last 15 filtered values
  const last15 = filteredValues.slice(-15);
  const mean = last15.reduce((a, b) => a + b, 0) / 15;
  const variance = last15.reduce((a, b) => a + (b - mean) ** 2, 0) / 15;
  const std = Math.sqrt(variance);

  assert.ok(std < 0.45, `Filtered std (${std}) must be lower than input noise (0.5).`);
});

test("verifyPointingPosture validates index extended and other fingers folded", () => {
  // Construct synthetic 21 landmarks
  const landmarks = Array.from({ length: 21 }, () => [0.0, 0.0, 0.0]);
  const wrist = [100.0, 300.0, 0.0];
  landmarks[0] = wrist;

  // Index: MCP 5, PIP 6, DIP 7, TIP 8 (extended up)
  landmarks[5] = [100.0, 250.0, 0.0];
  landmarks[6] = [100.0, 200.0, 0.0];
  landmarks[7] = [100.0, 150.0, 0.0];
  landmarks[8] = [100.0, 100.0, 0.0]; // Extended far from wrist

  // Middle: MCP 9, PIP 10, DIP 11, TIP 12 (folded)
  landmarks[9] = [120.0, 250.0, 0.0];
  landmarks[10] = [120.0, 200.0, 0.0];
  landmarks[11] = [120.0, 230.0, 0.0];
  landmarks[12] = [120.0, 260.0, 0.0]; // Folded closer to wrist than PIP

  // Ring: MCP 13, PIP 14, DIP 15, TIP 16 (folded)
  landmarks[13] = [140.0, 250.0, 0.0];
  landmarks[14] = [140.0, 200.0, 0.0];
  landmarks[15] = [140.0, 230.0, 0.0];
  landmarks[16] = [140.0, 260.0, 0.0];

  // Pinky: MCP 17, PIP 18, DIP 19, TIP 20 (folded)
  landmarks[17] = [160.0, 250.0, 0.0];
  landmarks[18] = [160.0, 200.0, 0.0];
  landmarks[19] = [160.0, 230.0, 0.0];
  landmarks[20] = [160.0, 260.0, 0.0];

  assert.equal(verifyPointingPosture(landmarks), true, "Valid pointing posture must be true.");

  // Open hand: middle finger also extended
  landmarks[12] = [120.0, 90.0, 0.0];
  assert.equal(verifyPointingPosture(landmarks), false, "Open hand must be rejected.");
});

test("rgbToHsv correctly computes OpenCV standard H in [0, 180], S, V in [0, 255]", () => {
  // Pure Green: RGB (0, 255, 0) -> H=120 deg -> OpenCV H=60, S=255, V=255
  const [hGreen, sGreen, vGreen] = rgbToHsv(0, 255, 0);
  assert.equal(hGreen, 60);
  assert.equal(sGreen, 255);
  assert.equal(vGreen, 255);

  // Pure Red: RGB (255, 0, 0) -> H=0, S=255, V=255
  const [hRed, sRed, vRed] = rgbToHsv(255, 0, 0);
  assert.equal(hRed, 0);
  assert.equal(sRed, 255);
  assert.equal(vRed, 255);

  // Pure Blue: RGB (0, 0, 255) -> H=240 deg -> OpenCV H=120, S=255, V=255
  const [hBlue, sBlue, vBlue] = rgbToHsv(0, 0, 255);
  assert.equal(hBlue, 120);
  assert.equal(sBlue, 255);
  assert.equal(vBlue, 255);
});

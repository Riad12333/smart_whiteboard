import test from "node:test";
import assert from "node:assert/strict";

import {
  cameraToViewport,
  viewportToCanvas,
  hitTest,
  findMagneticTarget,
  resolveHandPointer,
} from "../js/interaction.js";

function makeMockButton(id, left, top, width, height) {
  return {
    id,
    dataset: { handTarget: "" },
    getBoundingClientRect() {
      return { left, top, width, height, right: left + width, bottom: top + height };
    }
  };
}

test("hitTest & resolveHandPointer: 1) directly on a button", () => {
  const btnHome = makeMockButton("btn-nav-home", 100, 20, 100, 44);
  const mockElementFromPoint = (x, y) => {
    if (x >= 100 && x <= 200 && y >= 20 && y <= 64) return btnHome;
    return null;
  };

  const hit = hitTest(150, 40, mockElementFromPoint);
  assert.equal(hit, btnHome);

  const resolved = resolveHandPointer(150, 40, {
    elementFromPointFn: mockElementFromPoint,
    targets: [btnHome],
    magnetRadiusPx: 75
  });
  assert.equal(resolved.hoveredTarget, btnHome);
  assert.equal(resolved.snapped, false);
  assert.equal(resolved.clientX, 150);
  assert.equal(resolved.clientY, 40);
});

test("resolveHandPointer: 2) between two buttons chooses nearest within MAGNET_RADIUS_PX", () => {
  const btnA = makeMockButton("btn-a", 100, 20, 100, 44); // right edge = 200, center = (150, 42)
  const btnB = makeMockButton("btn-b", 260, 20, 100, 44); // left edge = 260, center = (310, 42)
  const mockNull = () => null;

  // Point at x=220, y=42 -> 20px from btnA right edge, 40px from btnB left edge
  const resolved = resolveHandPointer(220, 42, {
    elementFromPointFn: mockNull,
    targets: [btnA, btnB],
    magnetRadiusPx: 75
  });

  assert.equal(resolved.hoveredTarget, btnA);
  assert.equal(resolved.snapped, true);
  assert.equal(resolved.clientX, 150);
  assert.equal(resolved.clientY, 42);
});

test("resolveHandPointer: 3) far from everything (> MAGNET_RADIUS_PX) returns no target", () => {
  const btnA = makeMockButton("btn-a", 100, 20, 100, 44);
  const mockNull = () => null;

  // Point at (500, 400) -> well outside 75px radius
  const resolved = resolveHandPointer(500, 400, {
    elementFromPointFn: mockNull,
    targets: [btnA],
    magnetRadiusPx: 75
  });

  assert.equal(resolved.hoveredTarget, null);
  assert.equal(resolved.snapped, false);
  assert.equal(resolved.clientX, 500);
  assert.equal(resolved.clientY, 400);
});

test("cameraToViewport: 4) handles screen edges cleanly with mirror and safety margin", () => {
  // Camera 640x480, Viewport 1280x800, mirror=true, margin=0.08
  // Near top-right of raw camera (x=620, y=10) with mirror -> maps to top-left of viewport (0, 0)
  const [cx1, cy1] = cameraToViewport(620, 10, 640, 480, 1280, 800, true, 0.08);
  assert.equal(cx1, 0);
  assert.equal(cy1, 0);

  // Near bottom-left of raw camera (x=20, y=470) with mirror -> maps to bottom-right (1280, 800)
  const [cx2, cy2] = cameraToViewport(20, 470, 640, 480, 1280, 800, true, 0.08);
  assert.equal(cx2, 1280);
  assert.equal(cy2, 800);

  // Center of camera (320, 240) -> exact center of viewport (640, 400)
  const [cx3, cy3] = cameraToViewport(320, 240, 640, 480, 1280, 800, true, 0.08);
  assert.ok(Math.abs(cx3 - 640) < 1e-6);
  assert.ok(Math.abs(cy3 - 400) < 1e-6);
});

test("viewportToCanvas: distinguishes toolbar region from board canvas", () => {
  const canvasRect = { left: 100, top: 80, width: 1000, height: 562.5, right: 1100, bottom: 642.5 };

  // Over top toolbar (y=30 < 80) -> outside canvas
  const toolbarPos = viewportToCanvas(500, 30, canvasRect, 1280, 720);
  assert.equal(toolbarPos.insideCanvas, false);

  // Over center of canvas (x=600, y=361.25) -> inside canvas, (u=640, v=360)
  const boardPos = viewportToCanvas(600, 361.25, canvasRect, 1280, 720);
  assert.equal(boardPos.insideCanvas, true);
  assert.ok(Math.abs(boardPos.u - 640) < 0.01);
  assert.ok(Math.abs(boardPos.v - 360) < 0.01);
});

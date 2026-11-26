import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  compute_homography_dlt,
  transform_point_homography,
  apply_deadzone,
  bresenham_line,
  create_stroke,
  add_point_to_stroke,
  undo_stroke,
  redo_stroke,
} from "../js/core_logic.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixturePath = path.resolve(__dirname, "../../tests/fixtures/homography_cases.json");
const fixture = JSON.parse(fs.readFileSync(fixturePath, "utf-8"));

test("compute_homography_dlt reproduces identical Python matrix within 1e-4 tolerance", () => {
  const src = fixture.calibration_pairs.camera_src_corners;
  const dst = fixture.calibration_pairs.board_dst_corners;
  const expectedH = fixture.expected_homography_matrix_3x3;

  const computedH = compute_homography_dlt(src, dst);

  assert.equal(computedH.length, 3);
  assert.equal(computedH[0].length, 3);
  assert.equal(computedH[2][2], 1.0);

  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 3; c++) {
      const diff = Math.abs(computedH[r][c] - expectedH[r][c]);
      assert.ok(
        diff < 1e-4,
        `Matrix mismatch at [${r}][${c}]: computed ${computedH[r][c]} vs expected ${expectedH[r][c]} (diff: ${diff})`
      );
    }
  }
});

test("transform_point_homography maps camera points to expected board coordinates within 0.05px", () => {
  const H = fixture.expected_homography_matrix_3x3;

  for (const caseItem of fixture.test_points) {
    const [camX, camY] = caseItem.camera_point;
    const [expU, expV] = caseItem.expected_board_point;

    const [u, v] = transform_point_homography(camX, camY, H);

    assert.ok(
      Math.abs(u - expU) < 0.05,
      `U coordinate mismatch: got ${u}, expected ${expU}`
    );
    assert.ok(
      Math.abs(v - expV) < 0.05,
      `V coordinate mismatch: got ${v}, expected ${expV}`
    );
  }
});

test("apply_deadzone suppresses sub-radius tremor and updates on larger displacement", () => {
  // Small displacement of 1.414 < 3.5 px
  const [x1, y1, frozen1] = apply_deadzone(101.0, 101.0, 100.0, 100.0, 3.5);
  assert.equal(frozen1, true);
  assert.equal(x1, 100.0);
  assert.equal(y1, 100.0);

  // Large displacement of 20 px > 3.5 px
  const [x2, y2, frozen2] = apply_deadzone(120.0, 100.0, 100.0, 100.0, 3.5);
  assert.equal(frozen2, false);
  assert.equal(x2, 120.0);
  assert.equal(y2, 100.0);
});

test("bresenham_line generates contiguous 8-connected path", () => {
  const line = bresenham_line(5, 5, 12, 18);
  assert.deepEqual(line[0], [5, 5]);
  assert.deepEqual(line[line.length - 1], [12, 18]);

  for (let i = 0; i < line.length - 1; i++) {
    const dx = Math.abs(line[i + 1][0] - line[i][0]);
    const dy = Math.abs(line[i + 1][1] - line[i][1]);
    assert.ok(Math.max(dx, dy) <= 1, "Bresenham points must be 8-connected.");
  }
});

test("stroke state transitions (undo and redo) are pure and symmetric", () => {
  let s1 = create_stroke("PEN", [30, 30, 30], 7);
  s1 = add_point_to_stroke(s1, 100, 150);
  const s2 = create_stroke("PEN", [25, 113, 194], 3);

  let history = [s1, s2];
  let redoStack = [];

  // Undo s2
  [history, redoStack] = undo_stroke(history, redoStack);
  assert.equal(history.length, 1);
  assert.equal(redoStack.length, 1);
  assert.deepEqual(redoStack[0].color, [25, 113, 194]);

  // Redo s2
  [history, redoStack] = redo_stroke(history, redoStack);
  assert.equal(history.length, 2);
  assert.equal(redoStack.length, 0);
  assert.deepEqual(history[1].color, [25, 113, 194]);
});

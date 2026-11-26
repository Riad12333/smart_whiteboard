import test from "node:test";
import assert from "node:assert/strict";

import { RemoteHandler } from "../js/remote.js";

test("RemoteHandler maps PageDown and ArrowRight to LEFT_CLICK", () => {
  const remote = new RemoteHandler(0.01); // 10ms debounce for tests

  const eNext1 = { key: "PageDown", code: "PageDown", repeat: false };
  const res1 = remote.processKeyEvent(eNext1);
  assert.ok(res1 !== null);
  assert.equal(res1.event, "LEFT_CLICK");

  // Wait 15ms
  const start = performance.now();
  while (performance.now() - start < 15) {}

  const eNext2 = { key: "ArrowRight", code: "ArrowRight", repeat: false };
  const res2 = remote.processKeyEvent(eNext2);
  assert.ok(res2 !== null);
  assert.equal(res2.event, "LEFT_CLICK");
});

test("RemoteHandler maps PageUp and ArrowLeft to RIGHT_CLICK", () => {
  const remote = new RemoteHandler(0.01);

  const ePrev = { key: "PageUp", code: "PageUp", repeat: false };
  const res = remote.processKeyEvent(ePrev);
  assert.ok(res !== null);
  assert.equal(res.event, "RIGHT_CLICK");
});

test("RemoteHandler ignores key hold repeat and debounces rapid presses", () => {
  const remote = new RemoteHandler(0.25); // 250ms debounce

  // 1. Initial click
  const e1 = { key: "PageDown", code: "PageDown", repeat: false };
  const res1 = remote.processKeyEvent(e1);
  assert.ok(res1 !== null);
  assert.equal(res1.event, "LEFT_CLICK");

  // 2. Hardware key hold repetition
  const eRepeat = { key: "PageDown", code: "PageDown", repeat: true };
  const resRepeat = remote.processKeyEvent(eRepeat);
  assert.equal(resRepeat, null, "Repeated keys must be ignored.");

  // 3. Immediate subsequent click within 50ms (debounced)
  const e2 = { key: "PageDown", code: "PageDown", repeat: false };
  const res2 = remote.processKeyEvent(e2);
  assert.equal(res2, null, "Clicks within debounce window must be suppressed.");
});

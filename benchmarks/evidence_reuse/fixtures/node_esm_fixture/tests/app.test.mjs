import assert from "node:assert/strict";
import test from "node:test";

import { compute, message, modeLabel } from "../src/app.mjs";

test("compute", () => {
  assert.equal(compute(7), 12);
});

test("message", () => {
  assert.equal(message("  Ada "), "Welcome, Ada!");
});

test("mode", () => {
  assert.equal(modeLabel(), "test");
});

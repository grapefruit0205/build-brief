const test = require("node:test");
const assert = require("node:assert/strict");

const { compute, message, modeLabel } = require("../lib/app.cjs");

test("compute", () => {
  assert.equal(compute(4), 12);
});

test("message", () => {
  assert.equal(message("  Ada "), "Hello Ada");
});

test("mode", () => {
  assert.equal(modeLabel(), "test");
});

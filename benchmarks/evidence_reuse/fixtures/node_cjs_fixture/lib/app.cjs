const fs = require("node:fs");
const path = require("node:path");

const { FACTOR } = require("./config.cjs");
const { normalize } = require("./shared.cjs");

const data = JSON.parse(
  fs.readFileSync(path.join(__dirname, "data.json"), "utf8"),
);

function compute(value) {
  return value * FACTOR;
}

function message(name) {
  return `${data.prefix} ${normalize(name)}`;
}

function modeLabel() {
  return process.env.CLICK_BENCH_MODE || "test";
}

module.exports = { compute, message, modeLabel };

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { OFFSET } from "./config.mjs";
import { normalize } from "./shared.mjs";

const directory = path.dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(
  fs.readFileSync(path.join(directory, "data.json"), "utf8"),
);

export function compute(value) {
  return value + OFFSET;
}

export function message(name) {
  return `${data.prefix}, ${normalize(name)}!`;
}

export function modeLabel() {
  return process.env.CLICK_BENCH_MODE || "test";
}

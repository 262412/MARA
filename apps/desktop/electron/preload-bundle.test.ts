import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

test("sandboxed preload is emitted as one self-contained file", async () => {
  const preloadPath = path.join(__dirname, "preload.js");
  const source = await readFile(preloadPath, "utf8");
  const requiredModules = Array.from(
    source.matchAll(/require\(["']([^"']+)["']\)/g),
    (match) => match[1],
  );

  assert.match(source, /contextBridge/);
  assert.doesNotMatch(source, /require\(["']\.\//);
  assert.deepEqual(requiredModules, ["electron"]);
});

test("desktop window keeps the sandbox security boundary enabled", async () => {
  const mainPath = path.join(__dirname, "main.js");
  const source = await readFile(mainPath, "utf8");

  assert.match(source, /contextIsolation: true/);
  assert.match(source, /nodeIntegration: false/);
  assert.match(source, /sandbox: true/);
});

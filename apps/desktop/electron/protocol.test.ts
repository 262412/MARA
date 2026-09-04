import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import { resolveAppAsset } from "./protocol";

test("resolves an application asset beneath the renderer root", () => {
  const root = path.resolve("/opt/mara/renderer");

  assert.equal(
    resolveAppAsset(root, "mara://app/assets/index.js"),
    path.join(root, "assets", "index.js"),
  );
});

test("maps the application root to index.html", () => {
  const root = path.resolve("/opt/mara/renderer");

  assert.equal(resolveAppAsset(root, "mara://app/"), path.join(root, "index.html"));
});

test("rejects unexpected hosts and directory traversal", () => {
  const root = path.resolve("/opt/mara/renderer");

  assert.throws(() => resolveAppAsset(root, "mara://other/index.html"));
  assert.throws(() =>
    resolveAppAsset(root, "mara://app/%2e%2e/secrets.json"),
  );
});

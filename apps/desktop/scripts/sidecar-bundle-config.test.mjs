import assert from "node:assert/strict";
import test from "node:test";

import { excludedSidecarModules } from "./sidecar-bundle-config.mjs";

test("excludes optional python-magic from the native Sidecar bundle", () => {
  assert.ok(excludedSidecarModules.includes("magic"));
});

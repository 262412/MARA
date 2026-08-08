import assert from "node:assert/strict";
import test from "node:test";

import { runDesktopSmoke } from "./smoke-runner";

test("packaged smoke preserves failures after orderly Sidecar shutdown", async () => {
  let stops = 0;
  const errors: unknown[] = [];
  const failed = await runDesktopSmoke(
    async () => {
      throw new Error("smoke failed");
    },
    async () => {
      stops += 1;
    },
    (error) => errors.push(error),
  );

  assert.equal(failed, 1);
  assert.equal(stops, 1);
  assert.equal(errors.length, 1);
  assert.equal(
    await runDesktopSmoke(async () => undefined, async () => undefined),
    0,
  );
});

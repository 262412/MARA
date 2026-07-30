import assert from "node:assert/strict";
import test from "node:test";

import { createTrustedIpcHandler } from "./ipc";

test("trusted desktop IPC accepts only the packaged renderer and no arguments", async () => {
  const handler = createTrustedIpcHandler(async () => "ok");

  assert.equal(
    await handler({ senderFrame: { url: "mara://app/" } }),
    "ok",
  );
  await assert.rejects(
    handler({ senderFrame: { url: "https://attacker.invalid/" } }),
    /Untrusted IPC sender/,
  );
  await assert.rejects(
    handler({ senderFrame: { url: "mara://app/" } }, { path: "/etc/passwd" }),
    /does not accept arguments/,
  );
});

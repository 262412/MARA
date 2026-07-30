import assert from "node:assert/strict";
import test from "node:test";

import { parseReadyMessage } from "./sidecar-manager";

test("accepts the versioned sidecar ready message", () => {
  assert.deepEqual(
    parseReadyMessage('{"type":"ready","protocol":1,"port":43127,"pid":1234}'),
    {
      type: "ready",
      protocol: 1,
      port: 43127,
      pid: 1234,
    },
  );
});

test("rejects incompatible, privileged, and malformed ready messages", () => {
  assert.throws(() =>
    parseReadyMessage('{"type":"ready","protocol":2,"port":43127,"pid":1234}'),
  );
  assert.throws(() =>
    parseReadyMessage('{"type":"ready","protocol":1,"port":80,"pid":1234}'),
  );
  assert.throws(() => parseReadyMessage("not-json"));
});

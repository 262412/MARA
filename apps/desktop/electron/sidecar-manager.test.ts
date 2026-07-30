import assert from "node:assert/strict";
import test from "node:test";

import {
  parseReadyMessage,
  waitForRequestReadiness,
} from "./sidecar-manager";

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

test("data requests wait for a delayed Sidecar startup to become healthy", async () => {
  let resolveStartup: ((status: {
    state: "healthy";
    protocol: number;
    version: string;
    capabilities: string[];
  }) => void) | undefined;
  const startup = new Promise<{
    state: "healthy";
    protocol: number;
    version: string;
    capabilities: string[];
  }>((resolve) => {
    resolveStartup = resolve;
  });
  let state: "starting" | "healthy" = "starting";
  let settled = false;
  const pending = waitForRequestReadiness(
    () => ({
      state,
      protocol: 1,
      version: state === "healthy" ? "0.2.0" : undefined,
      capabilities: state === "healthy" ? ["doctor", "files", "sessions"] : [],
    }),
    startup,
  ).then(() => {
    settled = true;
  });

  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.equal(settled, false);

  state = "healthy";
  resolveStartup?.({
    state: "healthy",
    protocol: 1,
    version: "0.2.0",
    capabilities: ["doctor", "files", "sessions"],
  });
  await pending;
  assert.equal(settled, true);
});

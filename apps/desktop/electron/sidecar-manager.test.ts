import assert from "node:assert/strict";
import test from "node:test";

import {
  parseIndexTaskEvent,
  parseReadyMessage,
  sidecarRequestTimeout,
  sidecarRestartDelay,
  waitForRequestReadiness,
} from "./sidecar-manager";

test("allows bounded long file deletion without relaxing other requests", () => {
  assert.equal(sidecarRequestTimeout("/v1/files/file-1", "DELETE"), 300_000);
  assert.equal(sidecarRequestTimeout("/v1/files", "GET"), 30_000);
  assert.equal(sidecarRequestTimeout("/v1/doctor", "GET"), 30_000);
});

test("bounds automatic Sidecar restarts to three exponential delays", () => {
  assert.deepEqual(
    [0, 1, 2, 3].map((attempt) => sidecarRestartDelay(attempt)),
    [250, 500, 1_000, undefined],
  );
});

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

test("parses typed index task SSE events without accepting arbitrary payloads", () => {
  const task = parseIndexTaskEvent(
    'event: task\ndata: {"request_id":"request-1","task":{"task_id":"task-1","status":"running","stage":"indexing","completed_files":0,"total_files":1,"file_names":["paper.pdf"],"success_count":0,"failure_count":0,"failures":[],"error":null,"retryable":false,"created_at":"2026-08-08T10:00:00Z","updated_at":"2026-08-08T10:00:01Z","version":2}}',
  );

  assert.equal(task.task_id, "task-1");
  assert.equal(task.status, "running");
  assert.equal(
    parseIndexTaskEvent(
      'event: task\ndata: {"request_id":"request-1","task":{"task_id":"task-1","status":"running","stage":"indexing","completed_files":0,"total_files":1,"file_names":["paper.pdf"],"success_count":0,"failure_count":0,"failures":[],"error":null,"retryable":false,"created_at":"2026-08-08T10:00:00Z","updated_at":"2026-08-08T10:00:01Z","version":2}}',
      "request-1",
    ).task_id,
    "task-1",
  );
  assert.throws(() =>
    parseIndexTaskEvent(
      'event: task\ndata: {"request_id":"request-1","task":{"task_id":"task-1","status":"running","stage":"indexing","completed_files":0,"total_files":1,"file_names":["paper.pdf"],"success_count":0,"failure_count":0,"failures":[],"error":null,"retryable":false,"created_at":"2026-08-08T10:00:00Z","updated_at":"2026-08-08T10:00:01Z","version":2}}',
      "request-2",
    ),
  );
  assert.throws(() => parseIndexTaskEvent("event: message\ndata: {}"));
  assert.throws(() =>
    parseIndexTaskEvent(
      'event: task\ndata: {"request_id":"request-1","task":{"path":"/etc/passwd"}}',
    ),
  );
});

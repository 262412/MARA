import assert from "node:assert/strict";
import test from "node:test";

import {
  batchFileDeleteRequest,
  parseIndexTaskEvent,
  parseQueryTaskEvent,
  parseReadyMessage,
  queryWatchRetryDelay,
  queryTaskCreateRequest,
  sessionCreateRequest,
  sessionRenameRequest,
  SidecarManager,
  sidecarRequestTimeout,
  sidecarRestartDelay,
  waitForRequestReadiness,
} from "./sidecar-manager";

test("sends a bounded query scope without model or credential fields", () => {
  assert.deepEqual(
    queryTaskCreateRequest(
      {
        conversation_id: "session-1",
        prompt: "What changed?",
        selected_file_ids: ["file-1", "file-2"],
      },
      "query-request-1",
    ),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": "query-request-1",
      },
      body: JSON.stringify({
        conversation_id: "session-1",
        prompt: "What changed?",
        selected_file_ids: ["file-1", "file-2"],
      }),
    },
  );
});

test("sends session creation as authenticated idempotent JSON", () => {
  assert.deepEqual(sessionCreateRequest("create-request-1"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": "create-request-1",
    },
    body: JSON.stringify({}),
  });
});

test("sends session rename as authenticated idempotent JSON", () => {
  assert.deepEqual(sessionRenameRequest("Renamed session", "rename-request-1"), {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": "rename-request-1",
    },
    body: JSON.stringify({ name: "Renamed session" }),
  });
});

test("sends batch deletion as authenticated idempotent JSON", () => {
  assert.deepEqual(
    batchFileDeleteRequest(["file-1", "file-2"], "delete-request-1"),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": "delete-request-1",
      },
      body: JSON.stringify({ file_ids: ["file-1", "file-2"] }),
    },
  );
});

test("allows bounded long file deletion without relaxing other requests", () => {
  assert.equal(sidecarRequestTimeout("/v1/files/file-1", "DELETE"), 300_000);
  assert.equal(sidecarRequestTimeout("/v1/file-deletions", "POST"), 300_000);
  assert.equal(sidecarRequestTimeout("/v1/files", "GET"), 30_000);
  assert.equal(sidecarRequestTimeout("/v1/doctor", "GET"), 30_000);
});

test("bounds automatic Sidecar restarts to three exponential delays", () => {
  assert.deepEqual(
    [0, 1, 2, 3].map((attempt) => sidecarRestartDelay(attempt)),
    [250, 500, 1_000, undefined],
  );
});

test("controlled restart stops the current Sidecar before starting with refreshed settings", async () => {
  const manager = Object.create(SidecarManager.prototype) as SidecarManager;
  const calls: string[] = [];
  manager.stop = async () => {
    calls.push("stop");
  };
  manager.start = async () => {
    calls.push("start");
    return {
      state: "healthy",
      protocol: 1,
      version: "0.8.0",
      capabilities: [],
    };
  };

  const status = await manager.restart();

  assert.deepEqual(calls, ["stop", "start"]);
  assert.equal(status.state, "healthy");
});

test("bounds query watcher reconnect delays without giving up on transient failures", () => {
  assert.deepEqual(
    [0, 1, 2, 3, 4, 20].map((attempt) => queryWatchRetryDelay(attempt)),
    [250, 500, 1_000, 2_000, 5_000, 5_000],
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

test("parses query SSE events and rejects raw path-shaped payloads", () => {
  const event =
    'event: query\ndata: {"request_id":"request-1","task":{"task_id":"query-1","retry_of_task_id":null,"conversation_id":"session-1","prompt":"Question","selected_file_ids":["file-1"],"qa_scope":"document","status":"success","stage":"completed","answer":"Grounded answer","citations":[{"citation_id":"chunk-1","file_id":"file-1","file_name":"paper.pdf","page_label":"2","element_id":null,"quote":"Evidence"}],"error":null,"retryable":false,"created_at":"2026-08-08T10:00:00Z","updated_at":"2026-08-08T10:00:01Z","version":3}}';
  const task = parseQueryTaskEvent(event, "request-1");

  assert.equal(task.answer, "Grounded answer");
  assert.equal(task.citations[0]?.file_name, "paper.pdf");
  assert.throws(() => parseQueryTaskEvent(event, "request-2"));
  assert.throws(() => parseQueryTaskEvent("event: task\ndata: {}"));
  assert.throws(() =>
    parseQueryTaskEvent(
      'event: query\ndata: {"request_id":"request-1","task":{"path":"/private/paper.pdf"}}',
    ),
  );
});

test("query watcher survives one retryable fallback GET failure", async () => {
  const manager = Object.create(SidecarManager.prototype) as SidecarManager;
  const testable = manager as unknown as {
    status: {
      state: "healthy";
      protocol: number;
      version: string;
      capabilities: string[];
    };
    startup: undefined;
    consumeQueryTaskEvents: () => Promise<boolean>;
  };
  testable.status = {
    state: "healthy",
    protocol: 1,
    version: "0.7.0",
    capabilities: ["query_stream"],
  };
  testable.startup = undefined;
  testable.consumeQueryTaskEvents = async () => {
    throw new Error("temporary disconnect");
  };
  let requests = 0;
  manager.getQueryTask = async () => {
    requests += 1;
    if (requests === 1) {
      return {
        ok: false,
        error: {
          code: "sidecar_request_failed",
          message: "Temporary failure",
          details: null,
          retryable: true,
          request_id: "watch-retry-1",
        },
      };
    }
    return {
      ok: true,
      data: parseQueryTaskEvent(
        'event: query\ndata: {"request_id":"request-2","task":{"task_id":"query-1","retry_of_task_id":null,"conversation_id":"session-1","prompt":"Question","selected_file_ids":["file-1"],"qa_scope":"document","status":"success","stage":"completed","answer":"Recovered","citations":[],"error":null,"retryable":false,"created_at":"2026-08-08T10:00:00Z","updated_at":"2026-08-08T10:00:02Z","version":4}}',
      ),
    };
  };
  const updates: string[] = [];

  await manager.watchQueryTask("query-1", (task) => updates.push(task.answer));

  assert.equal(requests, 2);
  assert.deepEqual(updates, ["Recovered"]);
});

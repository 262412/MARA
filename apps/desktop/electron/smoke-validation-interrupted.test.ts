import assert from "node:assert/strict";
import test from "node:test";

import type { FileRecord } from "../shared/file-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
import type {
  DesktopResult,
  RuntimeStatus,
} from "../shared/runtime-contracts";
import {
  GATE3_INTERRUPTED_INPUT_NAME,
  assertGate3InterruptedRetrySmoke,
  assertGate3InterruptedSmoke,
} from "./smoke-validation";

const created: DesktopResult<IndexTask> = {
  ok: true,
  data: {
    task_id: "interrupted-task",
    status: "running",
    stage: "indexing",
    completed_files: 0,
    total_files: 1,
    file_names: [GATE3_INTERRUPTED_INPUT_NAME],
    success_count: 0,
    failure_count: 0,
    failures: [],
    error: null,
    retryable: false,
    created_at: "2026-08-08T10:00:00Z",
    updated_at: "2026-08-08T10:00:01Z",
    version: 2,
  },
};
const failedRuntime: RuntimeStatus = {
  state: "failed",
  protocol: 1,
  capabilities: [],
  message: "Sidecar exited unexpectedly.",
};
const restartedRuntime: RuntimeStatus = {
  state: "healthy",
  protocol: 1,
  version: "0.2.0",
  capabilities: ["doctor", "files", "sessions", "index-tasks"],
};
const interrupted: DesktopResult<IndexTask | null> = {
  ok: true,
  data: {
    ...created.data,
    status: "failed",
    stage: "interrupted",
    error: {
      code: "index_interrupted",
      message: "Indexing was interrupted when MARA Desktop stopped.",
      retryable: true,
    },
    retryable: true,
    version: 3,
  },
};

test("requires safe interruption state before retrying unfinished work", () => {
  assert.equal(
    assertGate3InterruptedSmoke(
      created,
      failedRuntime,
      restartedRuntime,
      interrupted,
    ),
    "interrupted-task",
  );
  assert.throws(
    () =>
      assertGate3InterruptedSmoke(
        created,
        { ...failedRuntime, state: "healthy" },
        restartedRuntime,
        interrupted,
      ),
    /interruption was not restored safely/,
  );
});

test("retries only the interrupted file after Sidecar restart", () => {
  const retried: DesktopResult<IndexTask> = {
    ok: true,
    data: {
      ...created.data,
      task_id: "interrupted-retry",
      status: "queued",
      stage: "queued",
      version: 1,
    },
  };
  const terminal: DesktopResult<IndexTask> = {
    ok: true,
    data: {
      ...retried.data,
      status: "success",
      stage: "completed",
      completed_files: 1,
      success_count: 1,
      version: 3,
    },
  };
  const indexedFiles: DesktopResult<FileRecord[]> = {
    ok: true,
    data: [
      {
        file_id: "interrupted-file",
        name: GATE3_INTERRUPTED_INPUT_NAME,
        size: 32,
        tokens: 5,
        loader: "TextReader",
        date_created: "2026-08-08T10:00:03Z",
      },
    ],
  };

  assert.deepEqual(
    assertGate3InterruptedRetrySmoke(retried, terminal, indexedFiles),
    ["interrupted-file"],
  );
});

import assert from "node:assert/strict";
import test from "node:test";

import type { DesktopResult } from "../shared/runtime-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
import {
  GATE3_DATABASE_LOCKED_INPUT_NAME,
  assertGate3DatabaseLockedSmoke,
  assertGate3DiskFullSmoke,
} from "./smoke-validation";

function queuedTask(): IndexTask {
  return {
    task_id: "storage-fault-task",
    status: "queued",
    stage: "queued",
    completed_files: 0,
    total_files: 1,
    file_names: [GATE3_DATABASE_LOCKED_INPUT_NAME],
    success_count: 0,
    failure_count: 0,
    failures: [],
    error: null,
    retryable: false,
    created_at: "2026-08-08T10:00:00Z",
    updated_at: "2026-08-08T10:00:00Z",
    version: 1,
  };
}

test("accepts a stable retryable disk-full command error", () => {
  const failed: DesktopResult<IndexTask> = {
    ok: false,
    error: {
      code: "index_storage_full",
      message: "MARA does not have enough free storage to save indexing state.",
      details: null,
      retryable: true,
      request_id: "request-disk-full",
    },
  };

  assert.doesNotThrow(() => assertGate3DiskFullSmoke(failed));
  assert.throws(
    () =>
      assertGate3DiskFullSmoke({
        ...failed,
        error: { ...failed.error, code: "internal_error" },
      }),
    /not reported safely/,
  );
});

test("accepts a path-free database-lock task failure", () => {
  const created: DesktopResult<IndexTask> = {
    ok: true,
    data: queuedTask(),
  };
  const failed: DesktopResult<IndexTask> = {
    ok: true,
    data: {
      ...queuedTask(),
      status: "failed",
      stage: "completed",
      completed_files: 1,
      failure_count: 1,
      failures: [
        {
          name: GATE3_DATABASE_LOCKED_INPUT_NAME,
          code: "index_database_locked",
          message: "MARA data is temporarily busy. Try indexing this file again.",
          retryable: true,
        },
      ],
      error: {
        code: "index_database_locked",
        message: "MARA data is temporarily busy. Try indexing this file again.",
        retryable: true,
      },
      retryable: true,
      version: 3,
    },
  };

  assert.equal(
    assertGate3DatabaseLockedSmoke(created, failed),
    "storage-fault-task",
  );
  assert.throws(
    () =>
      assertGate3DatabaseLockedSmoke(created, {
        ...failed,
        data: {
          ...failed.data,
          error: { ...failed.data.error!, code: "index_failed" },
        },
      }),
    /not reported safely/,
  );
});

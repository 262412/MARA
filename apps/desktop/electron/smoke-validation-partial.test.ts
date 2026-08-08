import assert from "node:assert/strict";
import test from "node:test";

import type { FileRecord } from "../shared/file-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
import type { DesktopResult } from "../shared/runtime-contracts";
import {
  GATE3_PARTIAL_INPUT_NAMES,
  assertGate3PartialRetrySmoke,
  assertGate3PartialSmoke,
} from "./smoke-validation";

const queuedTask: IndexTask = {
  task_id: "partial-task",
  status: "queued",
  stage: "queued",
  completed_files: 0,
  total_files: 2,
  file_names: [...GATE3_PARTIAL_INPUT_NAMES],
  success_count: 0,
  failure_count: 0,
  failures: [],
  error: null,
  retryable: false,
  created_at: "2026-08-08T10:00:00Z",
  updated_at: "2026-08-08T10:00:00Z",
  version: 1,
};
const created: DesktopResult<IndexTask> = { ok: true, data: queuedTask };
const partial: DesktopResult<IndexTask> = {
  ok: true,
  data: {
    ...queuedTask,
    status: "partial",
    stage: "completed",
    completed_files: 2,
    success_count: 1,
    failure_count: 1,
    failures: [
      {
        name: GATE3_PARTIAL_INPUT_NAMES[0],
        code: "index_failed",
        message: "MARA could not index this file.",
        retryable: true,
      },
    ],
    error: {
      code: "index_partial_failure",
      message: "Some files could not be indexed.",
      retryable: true,
    },
    retryable: true,
    version: 4,
  },
};
const successfulRecord: FileRecord = {
  file_id: "partial-success",
  name: GATE3_PARTIAL_INPUT_NAMES[1],
  size: 32,
  tokens: 5,
  loader: "TextReader",
  date_created: "2026-08-08T10:00:02Z",
};
const existingRecord: FileRecord = {
  ...successfulRecord,
  file_id: "partial-existing",
  name: GATE3_PARTIAL_INPUT_NAMES[0],
};

test("locks partial failure to one file and retries only that file", () => {
  assert.equal(
    assertGate3PartialSmoke(created, partial, {
      ok: true,
      data: [existingRecord, successfulRecord],
    }),
    "partial-task",
  );

  const retried: DesktopResult<IndexTask> = {
    ok: true,
    data: {
      ...queuedTask,
      task_id: "partial-retry",
      total_files: 1,
      file_names: [GATE3_PARTIAL_INPUT_NAMES[0]],
    },
  };
  const retryTerminal: DesktopResult<IndexTask> = {
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
  const recoveredRecord: FileRecord = {
    ...successfulRecord,
    file_id: "partial-recovered",
    name: GATE3_PARTIAL_INPUT_NAMES[0],
  };

  assert.deepEqual(
    assertGate3PartialRetrySmoke(retried, retryTerminal, {
      ok: true,
      data: [successfulRecord, recoveredRecord],
    }),
    ["partial-recovered", "partial-success"],
  );
  assert.throws(
    () =>
      assertGate3PartialSmoke(created, {
        ...partial,
        data: { ...partial.data, failures: [] },
      }, { ok: true, data: [existingRecord, successfulRecord] }),
    /partial failure was not reported safely/,
  );
});

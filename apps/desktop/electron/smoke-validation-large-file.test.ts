import assert from "node:assert/strict";
import test from "node:test";

import type { FileRecord } from "../shared/file-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
import type { DesktopResult } from "../shared/runtime-contracts";
import {
  GATE3_LARGE_FILE_BYTES,
  GATE3_LARGE_FILE_INPUT_NAME,
  assertGate3LargeFileSmoke,
} from "./smoke-validation";

const created: DesktopResult<IndexTask> = {
  ok: true,
  data: {
    task_id: "large-file-task",
    status: "queued",
    stage: "queued",
    completed_files: 0,
    total_files: 1,
    file_names: [GATE3_LARGE_FILE_INPUT_NAME],
    success_count: 0,
    failure_count: 0,
    failures: [],
    error: null,
    retryable: false,
    created_at: "2026-08-08T10:00:00Z",
    updated_at: "2026-08-08T10:00:00Z",
    version: 1,
  },
};
const terminal: DesktopResult<IndexTask> = {
  ok: true,
  data: {
    ...created.data,
    status: "success",
    stage: "completed",
    completed_files: 1,
    success_count: 1,
    version: 3,
  },
};

function indexedFile(size: number): DesktopResult<FileRecord[]> {
  return {
    ok: true,
    data: [
      {
        file_id: "large-file",
        name: GATE3_LARGE_FILE_INPUT_NAME,
        size,
        tokens: 100_000,
        loader: "TextReader",
        date_created: "2026-08-08T10:00:05Z",
      },
    ],
  };
}

test("requires the full deterministic large-file canary to be indexed", () => {
  assert.deepEqual(
    assertGate3LargeFileSmoke(
      created,
      terminal,
      indexedFile(GATE3_LARGE_FILE_BYTES),
    ),
    ["large-file"],
  );
  assert.throws(
    () =>
      assertGate3LargeFileSmoke(
        created,
        terminal,
        indexedFile(GATE3_LARGE_FILE_BYTES - 1),
      ),
    /large-file record size changed/,
  );
});

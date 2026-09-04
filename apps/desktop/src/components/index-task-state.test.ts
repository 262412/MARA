import assert from "node:assert/strict";
import test from "node:test";

import type { IndexTask } from "../../shared/index-task-contracts";
import { refreshFilesForTerminalTask } from "../index-task-state";

const task: IndexTask = {
  task_id: "task-1",
  status: "running",
  stage: "indexing",
  completed_files: 0,
  total_files: 1,
  file_names: ["paper.pdf"],
  success_count: 0,
  failure_count: 0,
  failures: [],
  error: null,
  retryable: false,
  created_at: "2026-08-08T10:00:00Z",
  updated_at: "2026-08-08T10:00:01Z",
  version: 2,
};

test("terminal index updates refresh Files exactly once per task version", () => {
  let refreshes = 0;
  let lastRefresh: string | undefined;

  lastRefresh = refreshFilesForTerminalTask(task, lastRefresh, () => {
    refreshes += 1;
  });
  assert.equal(refreshes, 0);

  const success = { ...task, status: "success" as const, version: 3 };
  lastRefresh = refreshFilesForTerminalTask(success, lastRefresh, () => {
    refreshes += 1;
  });
  lastRefresh = refreshFilesForTerminalTask(success, lastRefresh, () => {
    refreshes += 1;
  });
  assert.equal(refreshes, 1);
  assert.equal(lastRefresh, "task-1:3:success");
});

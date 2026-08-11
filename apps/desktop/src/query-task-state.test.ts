import assert from "node:assert/strict";
import test from "node:test";

import type { QueryTask } from "../shared/query-contracts";
import {
  mergeQueryTaskSnapshot,
  submittedPromptTransition,
} from "./query-task-state";

const task: QueryTask = {
  task_id: "query-1",
  retry_of_task_id: null,
  conversation_id: "session-1",
  prompt: "Repeatable question",
  selected_file_ids: ["file-1"],
  qa_scope: "document",
  status: "running",
  stage: "generating",
  answer: "Partial answer",
  citations: [],
  error: null,
  retryable: false,
  created_at: "2026-08-09T10:00:00Z",
  updated_at: "2026-08-09T10:00:01Z",
  version: 4,
};

test("query task snapshots merge monotonically by task id and version", () => {
  assert.equal(
    mergeQueryTaskSnapshot(task, { ...task, version: 3, answer: "Older" }),
    task,
  );
  const terminal = {
    ...task,
    status: "success" as const,
    stage: "completed",
    answer: "Final answer",
    version: 5,
  };
  assert.equal(mergeQueryTaskSnapshot(terminal, task), terminal);
  assert.deepEqual(
    mergeQueryTaskSnapshot(task, terminal),
    terminal,
  );
});

test("a retry replaces its parent while late parent events cannot replace the retry", () => {
  const cancelled = {
    ...task,
    status: "cancelled" as const,
    stage: "completed",
    retryable: true,
    version: 6,
  };
  const retry = {
    ...task,
    task_id: "query-2",
    retry_of_task_id: cancelled.task_id,
    status: "queued" as const,
    stage: "queued",
    version: 1,
  };

  assert.deepEqual(mergeQueryTaskSnapshot(cancelled, retry), retry);
  assert.deepEqual(mergeQueryTaskSnapshot(retry, cancelled), retry);
});

test("a late latest-task response cannot replace a new explicit task", () => {
  const unrelated = { ...task, task_id: "query-other", version: 1 };
  assert.equal(mergeQueryTaskSnapshot(task, unrelated), task);
  assert.deepEqual(mergeQueryTaskSnapshot(task, unrelated, true), unrelated);
});

test("an explicit same-task response cannot roll back a newer streamed version", () => {
  const older = { ...task, version: 3, answer: "Older explicit response" };

  assert.equal(mergeQueryTaskSnapshot(task, older, true), task);
});

test("submitted prompt clears once per new task and can then be asked again", () => {
  const first = submittedPromptTransition("Repeatable question", task, undefined);
  assert.deepEqual(first, { prompt: "", consumedTaskId: "query-1" });

  const typedAgain = submittedPromptTransition(
    "Repeatable question",
    task,
    first.consumedTaskId,
  );
  assert.deepEqual(typedAgain, {
    prompt: "Repeatable question",
    consumedTaskId: "query-1",
  });
});

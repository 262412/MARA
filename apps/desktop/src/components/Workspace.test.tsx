import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import type { SessionDetail } from "../../shared/session-contracts";
import type { QueryTask } from "../../shared/query-contracts";
import type { SidecarError } from "../../shared/runtime-contracts";
import type { ResourceState } from "../resource-state";
import { Workspace } from "./Workspace";

const detail: SessionDetail = {
  conversation_id: "session-1",
  name: "Research session",
  messages: [
    { role: "user", content: "What is MARA?" },
    { role: "assistant", content: "A local research assistant." },
  ],
  graph_source_ids: ["file-1"],
  origin: "desktop",
  is_public: false,
  date_created: "2026-08-08T10:00:00Z",
  date_updated: "2026-08-08T10:05:00Z",
};

const queryTask: QueryTask = {
  task_id: "query-1",
  retry_of_task_id: null,
  conversation_id: "session-1",
  prompt: "What changed?",
  selected_file_ids: ["file-1"],
  qa_scope: "document",
  route_provider: "openai",
  route_model: "gpt-5.6-luna",
  settings_revision: "settings-revision-test",
  sidecar_pid: 4321,
  route_fingerprint: "a".repeat(64),
  status: "success",
  stage: "completed",
  answer: "The evidence changed.",
  answer_saved: true,
  terminal_semantic_commit: {},
  terminal_outcome: "",
  terminal_outcome_reason: "",
  citations: [
    {
      citation_id: "chunk-1",
      file_id: "file-1",
      file_name: "paper.pdf",
      page_label: "2",
      element_id: null,
      quote: "Grounded evidence",
    },
  ],
  error: null,
  retryable: false,
  created_at: "2026-08-08T10:00:00Z",
  updated_at: "2026-08-08T10:00:01Z",
  version: 3,
};

function render(
  session: ResourceState<SessionDetail> | undefined,
  answerTask?: QueryTask,
  selectedSourceCount = 1,
  answerActionError?: SidecarError,
) {
  return renderToStaticMarkup(
    <Workspace
      answerActionPending={false}
      answerActionError={answerActionError}
      answerTask={answerTask}
      modelName="local-model"
      onCancelAnswer={() => undefined}
      onOpenSources={() => undefined}
      onRetrySession={() => undefined}
      onRetryAnswer={() => undefined}
      onSubmitQuestion={() => undefined}
      onToggleInspector={() => undefined}
      selectedSourceCount={selectedSourceCount}
      session={session}
    />,
  );
}

test("Workspace covers unselected, loading, success, empty, and failed sessions", () => {
  assert.match(render(undefined), /Select a task from the left/);
  assert.match(render({ status: "loading" }), /Loading session/);

  const success = render({ status: "success", data: detail });
  assert.match(success, /Research session/);
  assert.match(success, /What is MARA/);
  assert.match(success, /A local research assistant/);
  assert.match(success, /1 sources/);
  assert.doesNotMatch(success, /Agent 研究方向研报/);

  assert.match(
    render({
      status: "success",
      data: { ...detail, messages: [] },
    }),
    /This task has no messages/,
  );

  const failed = render({ status: "failed", message: "Could not read session" });
  assert.match(failed, /Could not read session/);
  assert.match(failed, /Retry/);
});

test("Workspace renders streaming, success, failed, and cancelled answers", () => {
  const session = { status: "success" as const, data: detail };
  const running = render(session, {
    ...queryTask,
    status: "running",
    stage: "generating",
    answer: "Partial answer",
    citations: [],
  });
  assert.match(running, /Generating/);
  assert.match(running, /Partial answer/);
  assert.match(running, /Stop/);

  const success = render(session, queryTask);
  assert.match(success, /The evidence changed/);
  assert.match(success, /paper.pdf/);
  assert.match(success, /Page 2/);
  assert.match(success, /Grounded evidence/);

  const failed = render(session, {
    ...queryTask,
    status: "failed",
    error: {
      code: "query_failed",
      message: "MARA could not complete the answer.",
      retryable: true,
    },
    retryable: true,
  });
  assert.match(failed, /MARA could not complete the answer/);
  assert.match(failed, /Retry answer/);

  const cancelled = render(session, {
    ...queryTask,
    status: "cancelled",
    error: {
      code: "query_cancelled",
      message: "Answer generation was cancelled.",
      retryable: true,
    },
    retryable: true,
  });
  assert.match(cancelled, /Generation stopped/);
  assert.match(cancelled, /Retry answer/);

  const modelMissing = render(session, {
    ...queryTask,
    status: "failed",
    error: {
      code: "llm_model_not_found",
      message: "The selected chat model was not found at the configured provider.",
      retryable: false,
      provider_request_id: "provider-request-404",
      diagnostic: "provider_status=404 provider_code=model_not_found",
    },
    retryable: false,
  });
  assert.match(modelMissing, /Check the model ID/);
  assert.match(modelMissing, /Provider request ID: provider-request-404/);
  assert.match(modelMissing, /Open model settings/);
  assert.doesNotMatch(modelMissing, /Retry answer/);
});

test("all assistant answer states share semantic Markdown rendering", () => {
  const markdown = "# Result\n\n- item\n\n| A | B |\n| - | - |\n| 1 | 2 |";
  const markdownDetail: SessionDetail = {
    ...detail,
    messages: [{ role: "assistant", content: markdown }],
  };
  const history = render({ status: "success", data: markdownDetail });
  assert.match(history, /<h1>Result<\/h1>/);
  assert.match(history, /<table>/);

  for (const status of ["running", "success", "failed", "cancelled"] as const) {
    const current = render(
      { status: "success", data: { ...detail, messages: [] } },
      {
        ...queryTask,
        status,
        answer: markdown,
        error:
          status === "failed"
            ? {
                code: "query_state_permission_denied",
                message: "Answer state cannot be saved.",
                retryable: true,
              }
            : status === "cancelled"
              ? {
                  code: "query_cancelled",
                  message: "Answer generation was cancelled.",
                  retryable: true,
                }
              : null,
        retryable: status === "failed" || status === "cancelled",
      },
    );
    assert.match(current, /<h1>Result<\/h1>/, status);
    assert.match(current, /<table>/, status);
  }
});

test("persistence guidance follows the safe operation diagnostic", () => {
  const session = { status: "success" as const, data: detail };
  const basePersistence = {
    errno: 13,
    winerror: 5,
    retry_count: 4,
    post_failure_probe: "ready" as const,
    smoke_mode: false,
    fingerprint: "qpf-0123456789abcdef",
  };
  const replaceBlocked = render(session, {
    ...queryTask,
    status: "failed",
    answer_saved: false,
    error: {
      code: "query_state_replace_blocked",
      message: "Windows temporarily blocked the state replacement.",
      retryable: true,
      persistence: {
        ...basePersistence,
        operation: "atomic_replace",
      },
    },
    retryable: true,
  });
  assert.match(replaceBlocked, /Windows temporarily blocked the state file update/);
  assert.match(replaceBlocked, /The current partial answer was not safely saved/);
  assert.doesNotMatch(replaceBlocked, /resetting.*AppData|application data write access/);

  const writeBlockedProbe = render(session, {
    ...queryTask,
    status: "failed",
    answer_saved: false,
    error: {
      code: "query_state_permission_denied",
      message: "The post-failure write probe failed.",
      retryable: true,
      persistence: {
        ...basePersistence,
        operation: "atomic_replace",
        post_failure_probe: "write_blocked",
      },
    },
    retryable: true,
  });
  assert.match(writeBlockedProbe, /replacement recovery probe could not create a checkpoint/);
  assert.doesNotMatch(writeBlockedProbe, /Windows temporarily blocked/);

  const smokeFault = render(session, {
    ...queryTask,
    status: "failed",
    answer_saved: false,
    error: {
      code: "query_state_permission_denied",
      message: "Injected smoke fault.",
      retryable: true,
      persistence: {
        ...basePersistence,
        operation: "flush",
        smoke_mode: true,
      },
    },
    retryable: true,
  });
  assert.match(smokeFault, /internal build verification fault/);
  assert.doesNotMatch(smokeFault, /application data write access/);

  const preflightWriteFailure = render(session, undefined, 1, {
    code: "query_state_permission_denied",
    message: "The answer task could not be created.",
    retryable: true,
    request_id: "preflight-request",
    details: {
      persistence: {
        ...basePersistence,
        operation: "write_temp",
      },
    },
  });
  assert.match(preflightWriteFailure, /check application data write access/);
  assert.match(preflightWriteFailure, /preflight-request/);
});

test("Workspace truthfully explains why the composer is unavailable", () => {
  const session = { status: "success" as const, data: detail };
  assert.match(render(undefined), /Select or create a task first/);
  assert.match(render(session, undefined, 0), /Select sources in Sources first/);
  assert.match(
    render(session, {
      ...queryTask,
      conversation_id: "session-2",
      status: "running",
      stage: "generating",
    }),
    /Another task is still generating an answer/,
  );
  assert.match(render(session), /local-model/);
});

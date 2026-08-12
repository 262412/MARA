import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import type { SessionDetail } from "../../shared/session-contracts";
import type { QueryTask } from "../../shared/query-contracts";
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
) {
  return renderToStaticMarkup(
    <Workspace
      answerActionPending={false}
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
  assert.match(render(undefined), /从左侧选择一个任务/);
  assert.match(render({ status: "loading" }), /正在读取会话/);

  const success = render({ status: "success", data: detail });
  assert.match(success, /Research session/);
  assert.match(success, /What is MARA/);
  assert.match(success, /A local research assistant/);
  assert.match(success, /1 个来源/);
  assert.doesNotMatch(success, /Agent 研究方向研报/);

  assert.match(
    render({
      status: "success",
      data: { ...detail, messages: [] },
    }),
    /这个任务还没有消息/,
  );

  const failed = render({ status: "failed", message: "无法读取会话" });
  assert.match(failed, /无法读取会话/);
  assert.match(failed, /重试/);
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
  assert.match(running, /正在生成/);
  assert.match(running, /Partial answer/);
  assert.match(running, /停止/);

  const success = render(session, queryTask);
  assert.match(success, /The evidence changed/);
  assert.match(success, /paper.pdf/);
  assert.match(success, /第 2 页/);
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
  assert.match(failed, /重试回答/);

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
  assert.match(cancelled, /生成已停止/);
  assert.match(cancelled, /重试回答/);

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
  assert.match(modelMissing, /检查模型 ID/);
  assert.match(modelMissing, /提供方请求 ID：provider-request-404/);
  assert.match(modelMissing, /打开模型设置/);
  assert.doesNotMatch(modelMissing, /重试回答/);
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

test("Workspace truthfully explains why the composer is unavailable", () => {
  const session = { status: "success" as const, data: detail };
  assert.match(render(undefined), /先选择或新建任务/);
  assert.match(render(session, undefined, 0), /请先在 Sources 中选择来源/);
  assert.match(
    render(session, {
      ...queryTask,
      conversation_id: "session-2",
      status: "running",
      stage: "generating",
    }),
    /另一个任务的回答仍在生成/,
  );
  assert.match(render(session), /local-model/);
});

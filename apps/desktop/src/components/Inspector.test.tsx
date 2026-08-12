import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import type { DoctorPayload } from "../../shared/doctor-contracts";
import type { FileRecord } from "../../shared/file-contracts";
import type { QueryTask } from "../../shared/query-contracts";
import type { RuntimeStatus } from "../../shared/runtime-contracts";
import type { ResourceState } from "../resource-state";
import { Inspector } from "./Inspector";

const runtime: RuntimeStatus = {
  state: "healthy",
  protocol: 1,
  version: "0.2.0",
  capabilities: ["doctor", "files", "sessions"],
};
const doctor: DoctorPayload = {
  ok: true,
  app_name: "MARA",
  default_user_id: "default",
  index_name: "File Collection",
  index_id: 1,
  llm_default: "local",
  embedding_default: "local",
  file_count: 1,
  session_count: 1,
  graph_cache_dir: "/desktop/state/knowledge_graph/conversations",
  issues: [],
  warnings: [],
  indexing_ready: true,
  indexing_issue_code: null,
  indexing_message: "File indexing is ready.",
  indexing_action: "none",
  indexing_retryable: false,
  query_ready: true,
  query_issue_code: null,
  query_message: "Question answering is ready.",
  query_action: "none",
  query_retryable: false,
  query_persistence_ready: true,
  query_persistence_issue_code: null,
  query_persistence_message: "Answer state storage is ready.",
  query_persistence_action: "none",
  query_persistence_retryable: false,
  query_provider: "Ollama",
  query_model: "local-chat",
  embedding_provider: "Ollama",
  embedding_model: "local-embedding",
  settings_revision: "settings-revision-test",
  sidecar_pid: 4321,
  route_fingerprint: "a".repeat(64),
  request_id: "doctor-request",
};

function render(state: ResourceState<DoctorPayload>, answerTask?: QueryTask) {
  return renderToStaticMarkup(
    <Inspector
      activeTab="run"
      answerTask={answerTask}
      doctor={state}
      files={{ status: "success", data: [] }}
      onClose={() => undefined}
      onRetryFiles={() => undefined}
      onRetryDoctor={() => undefined}
      onToggleSource={() => undefined}
      onSelectTab={() => undefined}
      runtime={runtime}
      selectedSourceIds={[]}
    />,
  );
}

test("Doctor panel covers loading, success, failed, and degraded states", () => {
  assert.match(render({ status: "loading" }), /正在运行 Doctor/);
  assert.match(render({ status: "success", data: doctor }), /Doctor 通过/);
  assert.match(
    render({ status: "failed", message: "Doctor 暂不可用" }),
    /Doctor 暂不可用/,
  );
  assert.match(
    render({ status: "failed", message: "Doctor 暂不可用" }),
    /重试/,
  );
  assert.match(
    render({
      status: "success",
      data: { ...doctor, ok: false, issues: ["默认索引不可用"] },
    }),
    /默认索引不可用/,
  );
});

test("Run inspector shows only safe persistence identity and task ID", () => {
  const answerTask: QueryTask = {
    task_id: "bd9c80d7-fa0e-4fda-8a88-304ea7c00a2e",
    retry_of_task_id: null,
    conversation_id: "session-1",
    prompt: "private question must not be shown",
    selected_file_ids: ["file-1"],
    qa_scope: "document",
    route_provider: "openai",
    route_model: "test-model",
    settings_revision: "revision",
    sidecar_pid: 4321,
    route_fingerprint: "a".repeat(64),
    status: "failed",
    stage: "storage_error",
    answer: "private answer must not be shown",
    answer_saved: false,
    citations: [],
    error: {
      code: "query_state_replace_blocked",
      message: "State replacement is blocked.",
      retryable: true,
      persistence: {
        operation: "atomic_replace",
        errno: 13,
        winerror: 5,
        retry_count: 4,
        post_failure_probe: "ready",
        smoke_mode: false,
        fingerprint: "qpf-0123456789abcdef",
      },
    },
    retryable: true,
    created_at: "2026-08-12T10:00:00Z",
    updated_at: "2026-08-12T10:00:01Z",
    version: 4,
  };

  const markup = render({ status: "success", data: doctor }, answerTask);

  assert.match(markup, /bd9c80d7-fa0e-4fda-8a88-304ea7c00a2e/);
  assert.match(markup, /qpf-0123456789abcdef/);
  assert.match(markup, /atomic_replace/);
  assert.doesNotMatch(markup, /private question|private answer/);
  assert.doesNotMatch(markup, /[A-Z]:\\|\/Users\/|\/home\//);
});

test("Sources panel renders real file states and selected identities", () => {
  const file: FileRecord = {
    file_id: "file-1",
    name: "real-paper.pdf",
    size: 1024,
    tokens: 42,
    loader: "PDFReader",
    date_created: "2026-08-08T10:00:00Z",
  };
  const markup = renderToStaticMarkup(
    <Inspector
      activeTab="sources"
      doctor={{ status: "success", data: doctor }}
      files={{ status: "success", data: [file] }}
      onClose={() => undefined}
      onRetryDoctor={() => undefined}
      onRetryFiles={() => undefined}
      onSelectTab={() => undefined}
      onToggleSource={() => undefined}
      runtime={runtime}
      selectedSourceIds={["file-1"]}
    />,
  );

  assert.match(markup, /real-paper.pdf/);
  assert.match(markup, /42 tokens/);
  assert.match(markup, /已选择 1 个来源/);
  assert.doesNotMatch(markup, /agent_verifiable_trajectories/);
});

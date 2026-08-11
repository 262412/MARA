import assert from "node:assert/strict";
import test from "node:test";

import type { DesktopResult, RuntimeStatus } from "../shared/runtime-contracts";
import type { DoctorPayload } from "../shared/doctor-contracts";
import type { FileRecord } from "../shared/file-contracts";
import type { ImportCapabilities } from "../shared/file-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
import type { QueryTask } from "../shared/query-contracts";
import type {
  SessionDetail,
  SessionSummary,
} from "../shared/session-contracts";
import {
  GATE2_SMOKE_FILE_ID,
  GATE2_SMOKE_SESSION_ID,
  GATE3_CANCEL_INPUT_NAMES,
  GATE3_FORMAT_RECORD_NAMES,
  GATE3_MODEL_UNAVAILABLE_INPUT_NAME,
  GATE3_RENAMED_SESSION_NAME,
  assertGate3DeleteSmoke,
  assertGate3CancellationSmoke,
  assertGate3CancelRetrySmoke,
  assertGate3IndexSmoke,
  assertIndexingBlockedSmoke,
  assertGate3ModelUnavailableSmoke,
  assertGate3QueryCancelSmoke,
  assertGate3QueryRetrySmoke,
  assertGate3QuerySuccessSmoke,
  assertGate3RetrySource,
  assertGate3SessionMutationSmoke,
  assertPackagedSmoke,
} from "./smoke-validation";

const queryTask: QueryTask = {
  task_id: "query-1",
  retry_of_task_id: null,
  conversation_id: GATE2_SMOKE_SESSION_ID,
  prompt: "What is the fixture?",
  selected_file_ids: [GATE2_SMOKE_FILE_ID],
  qa_scope: "document",
  status: "success",
  stage: "completed",
  answer: "MARA Desktop preserves grounded evidence identities.",
  citations: [
    {
      citation_id: "chunk-1",
      file_id: GATE2_SMOKE_FILE_ID,
      file_name: "gate2-smoke.txt",
      page_label: null,
      element_id: "element-1",
      quote: "MARA Desktop Gate 2 deterministic smoke fixture.",
    },
  ],
  error: null,
  retryable: false,
  created_at: "2026-08-08T10:00:00Z",
  updated_at: "2026-08-08T10:00:01Z",
  version: 3,
};

const status: RuntimeStatus = {
  state: "healthy",
  protocol: 1,
  version: "0.2.0",
  capabilities: ["doctor", "files", "sessions"],
};
const doctorPayload: DoctorPayload = {
    ok: true,
    app_name: "MARA",
    default_user_id: "default",
    index_name: "File Collection",
    index_id: 1,
    llm_default: "openai",
    embedding_default: "openai",
    file_count: 1,
    session_count: 1,
    graph_cache_dir: "/private/runtime/path",
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
    query_provider: "OpenAI-compatible",
    query_model: "desktop-chat",
    embedding_provider: "OpenAI-compatible",
    embedding_model: "desktop-embedding",
    request_id: "doctor-smoke",
};
const doctor: DesktopResult<DoctorPayload> = {
  ok: true,
  data: doctorPayload,
};
const files: DesktopResult<FileRecord[]> = {
  ok: true,
  data: [
    {
      file_id: GATE2_SMOKE_FILE_ID,
      name: "gate2-smoke.txt",
      size: 24,
      tokens: 4,
      loader: "TextReader",
      date_created: "2026-07-30T12:00:00+00:00",
    },
  ],
};
const sessions: DesktopResult<SessionSummary[]> = {
  ok: true,
  data: [
    {
      conversation_id: GATE2_SMOKE_SESSION_ID,
      name: "Gate 2 smoke session",
      message_count: 1,
      graph_source_count: 1,
      origin: "desktop-gate2-smoke",
      is_public: false,
      date_created: "2026-07-30T12:00:00+00:00",
      date_updated: "2026-07-30T12:00:00+00:00",
    },
  ],
};
const session: DesktopResult<SessionDetail | null> = {
  ok: true,
  data: {
    conversation_id: GATE2_SMOKE_SESSION_ID,
    name: "Gate 2 smoke session",
    messages: [
      { role: "user", content: "What is this fixture?" },
      { role: "assistant", content: "A packaged Desktop smoke record." },
    ],
    graph_source_ids: [GATE2_SMOKE_FILE_ID],
    origin: "desktop-gate2-smoke",
    is_public: false,
    date_created: "2026-07-30T12:00:00+00:00",
    date_updated: "2026-07-30T12:00:00+00:00",
  },
};
const importCapabilities: DesktopResult<ImportCapabilities> = {
  ok: true,
  data: {
    supported_extensions: [".pdf", ".docx", ".txt", ".md", ".zip"],
  },
};

test("accepts the deterministic non-empty packaged smoke snapshot", () => {
  assert.doesNotThrow(() =>
    assertPackagedSmoke(
      { status, doctor, files, sessions, session, importCapabilities },
      true,
    ),
  );
});

test("requires grounded query success, partial cancellation, and scoped retry", () => {
  const reloaded = {
    ok: true as const,
    data: {
      ...(session.ok && session.data ? session.data : ({} as SessionDetail)),
      messages: [
        ...(session.ok && session.data ? session.data.messages : []),
        { role: "user" as const, content: queryTask.prompt },
        { role: "assistant" as const, content: queryTask.answer },
      ],
      graph_source_ids: [GATE2_SMOKE_FILE_ID],
    },
  };
  assert.doesNotThrow(() =>
    assertGate3QuerySuccessSmoke(
      { ok: true, data: { ...queryTask, status: "queued", answer: "", citations: [] } },
      { ok: true, data: queryTask },
      reloaded,
    ),
  );

  const cancelled = {
    ...queryTask,
    task_id: "query-cancelled",
    status: "cancelled" as const,
    answer: "MARA Desktop ",
    citations: [],
    error: {
      code: "query_cancelled",
      message: "Answer generation was cancelled.",
      retryable: true,
    },
    retryable: true,
  };
  assert.doesNotThrow(() =>
    assertGate3QueryCancelSmoke(
      { ok: true, data: { ...cancelled, status: "running", error: null } },
      { ok: true, data: { ...cancelled, status: "running", stage: "cancelling" } },
      { ok: true, data: cancelled },
    ),
  );

  const retried = {
    ...queryTask,
    task_id: "query-retried",
    retry_of_task_id: cancelled.task_id,
  };
  assert.doesNotThrow(() =>
    assertGate3QueryRetrySmoke(
      {
        ok: true,
        data: {
          ...retried,
          status: "queued",
          answer: cancelled.answer,
          citations: [],
        },
      },
      { ok: true, data: retried },
      reloaded,
      cancelled,
    ),
  );
  assert.throws(
    () =>
      assertGate3QuerySuccessSmoke(
        { ok: true, data: queryTask },
        { ok: true, data: { ...queryTask, citations: [] } },
        reloaded,
      ),
    /citation identity/,
  );
});

test("requires real multi-document smoke to retain both source identities", () => {
  const expectedSources = [
    { file_id: "query-source-1", file_name: "report.txt" },
    { file_id: "query-source-2", file_name: "report.txt.bak.txt" },
  ];
  const multiTask: QueryTask = {
    ...queryTask,
    answer:
      "MARA Desktop preserves grounded evidence identities and keeps cross-file citations distinct.",
    selected_file_ids: expectedSources.map((source) => source.file_id),
    qa_scope: "multi_document",
    citations: expectedSources.map((source, index) => ({
      citation_id: `citation-${index + 1}`,
      file_id: source.file_id,
      file_name: source.file_name,
      page_label: null,
      element_id: null,
      quote: `Evidence ${index + 1}`,
    })),
  };
  const reloaded = {
    ok: true as const,
    data: {
      ...(session.ok && session.data ? session.data : ({} as SessionDetail)),
      messages: [
        ...(session.ok && session.data ? session.data.messages : []),
        { role: "user" as const, content: multiTask.prompt },
        { role: "assistant" as const, content: multiTask.answer },
      ],
      graph_source_ids: multiTask.selected_file_ids,
    },
  };

  assert.doesNotThrow(() =>
    assertGate3QuerySuccessSmoke(
      { ok: true, data: { ...multiTask, status: "queued" } },
      { ok: true, data: multiTask },
      reloaded,
      expectedSources,
    ),
  );
});

test("accepts an additional CLI-indexed file in the shared smoke data", () => {
  const cliFiles: DesktopResult<FileRecord[]> = {
    ok: true,
    data: [
      ...files.data,
      {
        file_id: "cli-indexed-file",
        name: "gate3-cli-compat.txt",
        size: 31,
        tokens: 5,
        loader: "TextReader",
        date_created: "2026-08-08T11:00:00+00:00",
      },
    ],
  };
  const cliDoctor: DesktopResult<DoctorPayload> = {
    ok: true,
    data: { ...doctorPayload, file_count: 2 },
  };

  assert.doesNotThrow(() =>
    assertPackagedSmoke(
      {
        status,
        doctor: cliDoctor,
        files: cliFiles,
        sessions,
        session,
        importCapabilities,
      },
      true,
    ),
  );
});

test("rejects empty data when the packaged smoke requires real records", () => {
  assert.throws(
    () =>
      assertPackagedSmoke(
        {
          status,
          doctor: {
            ok: true,
            data: { ...doctorPayload, file_count: 0, session_count: 0 },
          },
          files: { ok: true, data: [] },
          sessions: { ok: true, data: [] },
          session,
          importCapabilities,
        },
        true,
      ),
    /non-empty Gate 2 fixture:.*"doctor_file_count":0.*"file_ids":\[\]/,
  );
});

test("rejects a file response that exposes a local path", () => {
  const leakedFiles = {
    ok: true as const,
    data: [{ ...files.data[0], path: "/private/source/gate2-smoke.txt" }],
  } as unknown as DesktopResult<FileRecord[]>;

  assert.throws(
    () =>
      assertPackagedSmoke(
        {
          status,
          doctor,
          files: leakedFiles,
          sessions,
          session,
          importCapabilities,
        },
        true,
      ),
    /local path/,
  );
});

test("rejects packaged smoke without the configured import format contract", () => {
  assert.throws(
    () =>
      assertPackagedSmoke(
        {
          status,
          doctor,
          files,
          sessions,
          session,
          importCapabilities: { ok: true, data: { supported_extensions: [] } },
        },
        true,
      ),
    /import capabilities/,
  );
});

test("accepts packaged deletion only when the real fixture disappears", () => {
  assert.doesNotThrow(() =>
    assertGate3DeleteSmoke(
      { ok: true, data: [GATE2_SMOKE_FILE_ID, "gate3-indexed-file"] },
      { ok: true, data: [] },
    ),
  );
  assert.doesNotThrow(() =>
    assertGate3DeleteSmoke(
      { ok: true, data: [GATE2_SMOKE_FILE_ID, "gate3-indexed-file"] },
      { ok: true, data: [] },
      "gate3-indexed-file",
    ),
  );
  assert.throws(
    () =>
      assertGate3DeleteSmoke(
        { ok: true, data: [GATE2_SMOKE_FILE_ID] },
        files,
      ),
    /still present/,
  );
});

test("accepts packaged session rename and deletion only after real refreshes", () => {
  const createdSession: DesktopResult<SessionDetail> = {
    ok: true,
    data: {
      conversation_id: "created-session",
      name: "Untitled Conversation",
      messages: [],
      graph_source_ids: [],
      origin: "",
      is_public: false,
      date_created: "2026-08-08T12:00:00+00:00",
      date_updated: "2026-08-08T12:00:00+00:00",
    },
  };
  const sessionsWithCreated: DesktopResult<SessionSummary[]> = {
    ok: true,
    data: [
      ...sessions.data,
      {
        conversation_id: "created-session",
        name: "Untitled Conversation",
        message_count: 0,
        graph_source_count: 0,
        origin: "",
        is_public: false,
        date_created: "2026-08-08T12:00:00+00:00",
        date_updated: "2026-08-08T12:00:00+00:00",
      },
    ],
  };
  const renamed = {
    ok: true as const,
    data: {
      ...(session.ok && session.data ? session.data : ({} as SessionDetail)),
      name: GATE3_RENAMED_SESSION_NAME,
    },
  };
  const renamedSessions = {
    ok: true as const,
    data: sessions.ok
      ? sessions.data.map((item) => ({
          ...item,
          name: GATE3_RENAMED_SESSION_NAME,
        }))
      : [],
  };

  assert.doesNotThrow(() =>
    assertGate3SessionMutationSmoke(
      createdSession,
      createdSession,
      sessionsWithCreated,
      { ok: true, data: "created-session" },
      renamed,
      renamed,
      renamedSessions,
      { ok: true, data: GATE2_SMOKE_SESSION_ID },
      { ok: true, data: [] },
    ),
  );
  assert.throws(
    () =>
      assertGate3SessionMutationSmoke(
        createdSession,
        createdSession,
        sessionsWithCreated,
        { ok: true, data: "created-session" },
        renamed,
        renamed,
        renamedSessions,
        { ok: true, data: GATE2_SMOKE_SESSION_ID },
        renamedSessions,
      ),
    /still present/,
  );
});

test("accepts a successful packaged background index and refreshed Files", () => {
  const created = {
    ok: true as const,
    data: {
      task_id: "gate3-task",
      status: "queued" as const,
      stage: "queued",
      completed_files: 0,
      total_files: 1,
      file_names: ["gate3-index-smoke.txt"],
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
  const terminal = {
    ok: true as const,
    data: {
      ...created.data,
      status: "success" as const,
      stage: "completed",
      completed_files: 1,
      success_count: 1,
      version: 3,
    },
  };
  const indexedFiles: DesktopResult<FileRecord[]> = {
    ok: true,
    data: [
      ...files.data,
      {
        file_id: "gate3-indexed-file",
        name: "gate3-index-smoke.txt",
        size: 32,
        tokens: 5,
        loader: "TextReader",
        date_created: "2026-08-08T10:00:02Z",
      },
    ],
  };

  assert.deepEqual(
    assertGate3IndexSmoke(created, terminal, indexedFiles),
    ["gate3-indexed-file"],
  );
  assert.throws(
    () =>
      assertGate3IndexSmoke(
        created,
        { ...terminal, data: { ...terminal.data, status: "failed" } },
        indexedFiles,
      ),
    /did not succeed/,
  );
});

test("blocks an unconfigured packaged index before any task is created", () => {
  const blockedDoctor: DesktopResult<DoctorPayload> = {
    ok: true,
    data: {
      ...doctorPayload,
      indexing_ready: false,
      indexing_issue_code: "embedding_not_configured",
      indexing_message: "Configure a supported embedding model.",
      indexing_action: "configure_embedding",
      indexing_retryable: false,
      request_id: "doctor-unconfigured",
    },
  };
  const rejected: DesktopResult<IndexTask> = {
    ok: false,
    error: {
      code: "embedding_not_configured",
      message: "Configure a supported embedding model.",
      details: null,
      retryable: false,
      request_id: "index-unconfigured",
    },
  };

  assert.doesNotThrow(() =>
    assertIndexingBlockedSmoke(blockedDoctor, rejected, {
      ok: true,
      data: null,
    }),
  );
  assert.throws(
    () =>
      assertIndexingBlockedSmoke(blockedDoctor, {
        ok: true,
        data: {
          task_id: "must-not-exist",
        } as IndexTask,
      }, { ok: true, data: null }),
    /created an index task/,
  );
});

test("requires every selected format record to contain parsed content", () => {
  const formatFiles: DesktopResult<FileRecord[]> = {
    ok: true,
    data: GATE3_FORMAT_RECORD_NAMES.map((name, index) => ({
      file_id: `format-${index}`,
      name,
      size: 32,
      tokens: 5,
      loader: "fixture-loader",
      date_created: "2026-08-08T10:00:02Z",
    })),
  };
  const created = {
    ok: true as const,
    data: {
      task_id: "format-task",
      status: "queued" as const,
      stage: "queued",
      completed_files: 0,
      total_files: GATE3_FORMAT_RECORD_NAMES.length,
      file_names: ["format fixtures"],
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
  const terminal = {
    ok: true as const,
    data: {
      ...created.data,
      status: "success" as const,
      stage: "completed",
      completed_files: GATE3_FORMAT_RECORD_NAMES.length,
      success_count: GATE3_FORMAT_RECORD_NAMES.length,
    },
  };

  assert.equal(
    assertGate3IndexSmoke(
      created,
      terminal,
      formatFiles,
      GATE3_FORMAT_RECORD_NAMES,
    ).length,
    GATE3_FORMAT_RECORD_NAMES.length,
  );
  assert.throws(
    () =>
      assertGate3IndexSmoke(
        created,
        terminal,
        { ok: true, data: formatFiles.data.slice(0, -1) },
        GATE3_FORMAT_RECORD_NAMES,
      ),
    /fixtures are missing/,
  );
  assert.throws(
    () =>
      assertGate3IndexSmoke(
        created,
        terminal,
        {
          ok: true,
          data: formatFiles.data.map((record, index) =>
            index === 0 ? { ...record, tokens: 0 } : record,
          ),
        },
        GATE3_FORMAT_RECORD_NAMES,
      ),
    /no parsed content/,
  );
});

test("requires a safe retryable model-unavailable task before recovery", () => {
  const created = {
    ok: true as const,
    data: {
      task_id: "fault-task",
      status: "queued" as const,
      stage: "queued",
      completed_files: 0,
      total_files: 1,
      file_names: [GATE3_MODEL_UNAVAILABLE_INPUT_NAME],
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
  const failed = {
    ok: true as const,
    data: {
      ...created.data,
      status: "failed" as const,
      stage: "completed",
      completed_files: 1,
      failure_count: 1,
      failures: [
        {
          name: GATE3_MODEL_UNAVAILABLE_INPUT_NAME,
          code: "index_failed",
          message: "MARA could not index this file.",
          retryable: true,
        },
      ],
      error: {
        code: "index_failed",
        message: "MARA could not index the selected files.",
        retryable: true,
      },
      retryable: true,
      version: 3,
    },
  };

  assert.equal(assertGate3ModelUnavailableSmoke(created, failed), "fault-task");
  assert.equal(assertGate3RetrySource(failed), "fault-task");
  assert.throws(
    () =>
      assertGate3ModelUnavailableSmoke(created, {
        ...failed,
        data: { ...failed.data, status: "success" },
      }),
    /not reported safely/,
  );
  assert.throws(
    () => assertGate3RetrySource({ ok: true, data: null }),
    /did not find/,
  );
});

test("locks cancellation to a completed file boundary and retries the rest", () => {
  const created = {
    ok: true as const,
    data: {
      task_id: "cancel-task",
      status: "queued" as const,
      stage: "queued",
      completed_files: 0,
      total_files: 2,
      file_names: [...GATE3_CANCEL_INPUT_NAMES],
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
  const cancelling = {
    ok: true as const,
    data: {
      ...created.data,
      status: "running" as const,
      stage: "cancelling",
      version: 3,
    },
  };
  const cancelled = {
    ok: true as const,
    data: {
      ...cancelling.data,
      status: "cancelled" as const,
      stage: "completed",
      completed_files: 1,
      success_count: 1,
      error: {
        code: "index_cancelled",
        message: "Indexing was cancelled.",
        retryable: true,
      },
      retryable: true,
      version: 5,
    },
  };
  const filesAfterCancel: DesktopResult<FileRecord[]> = {
    ok: true,
    data: [
      {
        file_id: "first-file",
        name: GATE3_CANCEL_INPUT_NAMES[0],
        size: 32,
        tokens: 5,
        loader: "TextReader",
        date_created: "2026-08-08T10:00:02Z",
      },
    ],
  };
  assert.equal(
    assertGate3CancellationSmoke(
      created,
      cancelling,
      cancelled,
      filesAfterCancel,
    ),
    "first-file",
  );

  const retried = {
    ok: true as const,
    data: {
      ...created.data,
      task_id: "retry-task",
      total_files: 1,
      file_names: [GATE3_CANCEL_INPUT_NAMES[1]],
    },
  };
  const retryTerminal = {
    ok: true as const,
    data: {
      ...retried.data,
      status: "success" as const,
      stage: "completed",
      completed_files: 1,
      success_count: 1,
      version: 3,
    },
  };
  const filesAfterRetry: DesktopResult<FileRecord[]> = {
    ok: true,
    data: [
      ...filesAfterCancel.data,
      {
        file_id: "second-file",
        name: GATE3_CANCEL_INPUT_NAMES[1],
        size: 32,
        tokens: 5,
        loader: "TextReader",
        date_created: "2026-08-08T10:00:03Z",
      },
    ],
  };
  assert.deepEqual(
    assertGate3CancelRetrySmoke(retried, retryTerminal, filesAfterRetry),
    ["first-file", "second-file"],
  );
  assert.throws(
    () =>
      assertGate3CancellationSmoke(
        created,
        cancelling,
        { ...cancelled, data: { ...cancelled.data, completed_files: 2 } },
        filesAfterRetry,
      ),
    /file boundary/,
  );
});

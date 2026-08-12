import assert from "node:assert/strict";
import test from "node:test";

import { act } from "react";

import type { DoctorPayload } from "../shared/doctor-contracts";
import type { FileRecord } from "../shared/file-contracts";
import type { QueryTask } from "../shared/query-contracts";
import type { ModelSettingsStatus } from "../shared/model-contracts";
import type { DesktopResult } from "../shared/runtime-contracts";
import type {
  SessionDetail,
  SessionSummary,
} from "../shared/session-contracts";
import App from "./App";
import {
  click,
  flushPromises,
  renderInDom,
  setInputValue,
} from "./test-dom";

const doctor = {
  ok: true,
  app_name: "MARA",
  default_user_id: "default",
  index_name: "File Collection",
  index_id: 1,
  llm_default: "desktop-chat",
  embedding_default: "desktop-embedding",
  file_count: 1,
  session_count: 1,
  graph_cache_dir: "Desktop managed cache",
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
  query_provider: "OpenAI-compatible",
  query_model: "desktop-chat-model",
  embedding_provider: "OpenAI-compatible",
  embedding_model: "desktop-embedding-model",
  settings_revision: "settings-revision-test",
  sidecar_pid: 4321,
  route_fingerprint: "a".repeat(64),
  request_id: "doctor-request",
} as DoctorPayload;

const file: FileRecord = {
  file_id: "file-1",
  name: "paper.txt",
  size: 128,
  tokens: 20,
  loader: "TextReader",
  date_created: "2026-08-11T10:00:00Z",
};

const historicalSession: SessionSummary = {
  conversation_id: "session-history",
  name: "Historical task",
  message_count: 2,
  graph_source_count: 1,
  origin: "desktop",
  is_public: false,
  date_created: "2026-08-11T09:00:00Z",
  date_updated: "2026-08-11T09:05:00Z",
};

const historicalDetail: SessionDetail = {
  conversation_id: historicalSession.conversation_id,
  name: historicalSession.name,
  messages: [
    { role: "user", content: "Old question" },
    { role: "assistant", content: "Old answer" },
  ],
  graph_source_ids: [file.file_id],
  origin: "desktop",
  is_public: false,
  date_created: historicalSession.date_created,
  date_updated: historicalSession.date_updated,
};

const createdDetail: SessionDetail = {
  ...historicalDetail,
  conversation_id: "session-created",
  name: "New task",
  messages: [],
  graph_source_ids: [],
};

function ok<T>(data: T): Promise<DesktopResult<T>> {
  return Promise.resolve({ ok: true, data });
}

function queryTask(prompt: string): QueryTask {
  return {
    task_id: "query-created",
    retry_of_task_id: null,
    conversation_id: createdDetail.conversation_id,
    prompt,
    selected_file_ids: [file.file_id],
    qa_scope: "document",
    route_provider: "openai",
    route_model: "gpt-5.6-luna",
    settings_revision: "settings-revision-test",
    sidecar_pid: 4321,
    route_fingerprint: "a".repeat(64),
    status: "queued",
    stage: "queued",
    answer: "",
    answer_saved: true,
    citations: [],
    error: null,
    retryable: false,
    created_at: "2026-08-11T10:00:00Z",
    updated_at: "2026-08-11T10:00:00Z",
    version: 1,
  };
}

type BridgeOptions = {
  createSessionResult?: DesktopResult<SessionDetail>;
  doctor?: DoctorPayload;
  latestAnswerTask?: QueryTask;
  sessions?: SessionSummary[];
};

function desktopBridge(options: BridgeOptions = {}) {
  const calls = {
    createSession: 0,
    cancelAnswer: 0,
    getSession: [] as string[],
    submitQuestion: [] as Array<{ prompt: string; conversation_id: string }>,
  };
  const bridge: NonNullable<Window["desktop"]> = {
    getRuntimeStatus: async () => ({
      state: "healthy",
      protocol: 1,
      version: "0.8.0",
      capabilities: [],
    }),
    getDoctor: () => ok(options.doctor ?? doctor),
    listFiles: () => ok([file]),
    listSessions: () => ok(options.sessions ?? []),
    getSession: (conversationId) => {
      calls.getSession.push(conversationId);
      return ok(historicalDetail);
    },
    createSession: () => {
      calls.createSession += 1;
      return options.createSessionResult
        ? Promise.resolve(options.createSessionResult)
        : ok(createdDetail);
    },
    renameSession: () => ok(historicalDetail),
    deleteSession: (conversationId) => ok(conversationId),
    importFiles: () => ok(null),
    importDroppedFiles: () => ok({} as never),
    openEmbeddingConfiguration: () => ok(true),
    getModelSettings: () => ok(emptyModelSettings()),
    saveModelSettings: () => ok(emptyModelSettings()),
    getLatestIndexTask: () => ok(null),
    cancelIndexTask: () => ok({} as never),
    retryIndexTask: () => ok({} as never),
    deleteFile: () => ok([]),
    deleteFiles: () => ok([]),
    submitQuestion: (payload) => {
      calls.submitQuestion.push({
        prompt: payload.prompt,
        conversation_id: payload.conversation_id,
      });
      return ok(queryTask(payload.prompt));
    },
    getLatestAnswerTask: () => ok(options.latestAnswerTask ?? null),
    cancelAnswer: () => {
      calls.cancelAnswer += 1;
      return ok({} as never);
    },
    retryAnswer: () => ok({} as never),
    onRuntimeStatus: () => () => undefined,
    onIndexTaskStatus: () => () => undefined,
    onAnswerTaskStatus: () => () => undefined,
    platform: "linux",
  };
  return { bridge, calls };
}

function emptyModelSettings(): ModelSettingsStatus {
  const route = {
    provider: "none" as const,
    base_url: "",
    model: "",
    api_version: "",
    credential_present: false,
    credential_storage: "none" as const,
  };
  return {
    chat: route,
    embedding: route,
    secure_storage_available: false,
    source: "compatibility",
  };
}

test("cold start stays on an editable draft without creating a history row", async () => {
  const { bridge, calls } = desktopBridge({ sessions: [historicalSession] });
  const rendered = await renderInDom(<App />, (window) => {
    window.desktop = bridge;
  });
  try {
    await act(flushPromises);
    const input = rendered.document.querySelector<HTMLTextAreaElement>("#task-input");
    assert.ok(input);
    assert.equal(input.disabled, false);
    assert.match(rendered.document.body.textContent ?? "", /新任务/);
    assert.equal(calls.createSession, 0);
    assert.deepEqual(calls.getSession, []);
  } finally {
    await rendered.cleanup();
  }
});

test("history selection followed by New task returns to a clean draft", async () => {
  const { bridge, calls } = desktopBridge({ sessions: [historicalSession] });
  const rendered = await renderInDom(<App />, (window) => {
    window.desktop = bridge;
  });
  try {
    await act(flushPromises);
    await click(buttonWithText(rendered.document, "Historical task"));
    assert.deepEqual(calls.getSession, [historicalSession.conversation_id]);
    const input = rendered.document.querySelector<HTMLTextAreaElement>("#task-input")!;
    await setInputValue(input, "discard this draft");
    await click(buttonWithText(rendered.document, "新建任务"));
    assert.equal(calls.createSession, 0);
    assert.equal(input.value, "");
    assert.match(rendered.document.body.textContent ?? "", /新任务/);
  } finally {
    await rendered.cleanup();
  }
});

test("first draft submission creates one session and one query despite repeated Enter", async () => {
  const { bridge, calls } = desktopBridge();
  const rendered = await renderInDom(<App />, (window) => {
    window.desktop = bridge;
  });
  try {
    await act(flushPromises);
    await click(buttonWithText(rendered.document, "Sources"));
    await click(rendered.document.querySelector<HTMLInputElement>("input[type=checkbox]")!);
    const input = rendered.document.querySelector<HTMLTextAreaElement>("#task-input")!;
    await setInputValue(input, "What does the source say?");
    await act(async () => {
      for (let index = 0; index < 2; index += 1) {
        input.dispatchEvent(
          new rendered.window.KeyboardEvent("keydown", {
            bubbles: true,
            cancelable: true,
            key: "Enter",
          }),
        );
      }
      await flushPromises();
    });

    assert.equal(calls.createSession, 1);
    assert.deepEqual(calls.submitQuestion, [
      {
        conversation_id: createdDetail.conversation_id,
        prompt: "What does the source say?",
      },
    ]);
  } finally {
    await rendered.cleanup();
  }
});

test("Resources, Help, and Settings are distinct navigable pages", async () => {
  const { bridge } = desktopBridge();
  const rendered = await renderInDom(<App />, (window) => {
    window.desktop = bridge;
  });
  try {
    await act(flushPromises);
    for (const [label, heading, title] of [
      ["Resources", "资源状态", "Resources"],
      ["Help", "帮助与快捷键", "Help"],
      ["Settings", "模型设置", "Settings"],
    ]) {
      const navigation = buttonWithText(rendered.document, label);
      await click(navigation);
      assert.equal(navigation.getAttribute("aria-current"), "page");
      assert.match(rendered.document.body.textContent ?? "", new RegExp(heading));
      assert.match(rendered.document.title, new RegExp(title));
    }
  } finally {
    await rendered.cleanup();
  }
});

test("a failed first session creation preserves the draft and sources", async () => {
  const failure: DesktopResult<SessionDetail> = {
    ok: false,
    error: {
      code: "session_create_failed",
      message: "The draft could not be saved.",
      details: null,
      retryable: true,
      request_id: "create-request-1",
    },
  };
  const { bridge, calls } = desktopBridge({ createSessionResult: failure });
  const rendered = await renderInDom(<App />, (window) => {
    window.desktop = bridge;
  });
  try {
    await act(flushPromises);
    await click(buttonWithText(rendered.document, "Sources"));
    await click(rendered.document.querySelector<HTMLInputElement>("input[type=checkbox]")!);
    const input = rendered.document.querySelector<HTMLTextAreaElement>("#task-input")!;
    await setInputValue(input, "Keep this question");
    await dispatchKey(rendered, input, { key: "Enter" });

    assert.equal(calls.createSession, 1);
    assert.deepEqual(calls.submitQuestion, []);
    assert.equal(input.value, "Keep this question");
    assert.match(rendered.document.body.textContent ?? "", /create-request-1/);
    assert.match(rendered.document.body.textContent ?? "", /1 个已选来源/);
  } finally {
    await rendered.cleanup();
  }
});

test("an unconfigured LLM blocks tasks, keeps the prompt, and opens Settings", async () => {
  const blockedDoctor: DoctorPayload = {
    ...doctor,
    ok: false,
    query_ready: false,
    query_issue_code: "llm_not_configured",
    query_message: "请先配置 Chat LLM。",
    query_action: "configure_llm",
    query_retryable: false,
    query_provider: "",
    query_model: "",
  };
  const { bridge, calls } = desktopBridge({ doctor: blockedDoctor });
  const rendered = await renderInDom(<App />, (window) => {
    window.desktop = bridge;
  });
  try {
    await act(flushPromises);
    await click(buttonWithText(rendered.document, "Sources"));
    await click(rendered.document.querySelector<HTMLInputElement>("input[type=checkbox]")!);
    const input = rendered.document.querySelector<HTMLTextAreaElement>("#task-input")!;
    await setInputValue(input, "Do not lose this draft");
    await dispatchKey(rendered, input, { key: "Enter" });

    assert.equal(calls.createSession, 0);
    assert.deepEqual(calls.submitQuestion, []);
    assert.equal(input.value, "Do not lose this draft");
    await click(buttonWithText(rendered.document, "配置模型"));
    assert.match(rendered.document.body.textContent ?? "", /模型设置/);
    await click(buttonWithText(rendered.document, "工作台"));
    assert.equal(
      rendered.document.querySelector<HTMLTextAreaElement>("#task-input")?.value,
      "Do not lose this draft",
    );
  } finally {
    await rendered.cleanup();
  }
});

test("Ctrl or Command plus comma opens Settings", async () => {
  const { bridge } = desktopBridge();
  const rendered = await renderInDom(<App />, (window) => {
    window.desktop = bridge;
  });
  try {
    await dispatchKey(rendered, rendered.window, { ctrlKey: true, key: "," });
    assert.match(rendered.document.body.textContent ?? "", /模型设置/);
    assert.equal(
      buttonWithText(rendered.document, "Settings").getAttribute("aria-current"),
      "page",
    );
  } finally {
    await rendered.cleanup();
  }
});

test("page navigation does not cancel an active answer task", async () => {
  const runningTask = {
    ...queryTask("Background answer"),
    status: "running" as const,
    stage: "generating",
    version: 2,
  };
  const { bridge, calls } = desktopBridge({ latestAnswerTask: runningTask });
  const rendered = await renderInDom(<App />, (window) => {
    window.desktop = bridge;
  });
  try {
    await act(flushPromises);
    for (const label of ["Resources", "Help", "Settings", "工作台"]) {
      await click(buttonWithText(rendered.document, label));
    }
    assert.equal(calls.cancelAnswer, 0);
  } finally {
    await rendered.cleanup();
  }
});

test("a delayed Sidecar readiness check leaves the cold-start draft editable", async () => {
  const { bridge, calls } = desktopBridge();
  let resolveDoctor: ((result: DesktopResult<DoctorPayload>) => void) | undefined;
  bridge.getDoctor = () =>
    new Promise<DesktopResult<DoctorPayload>>((resolve) => {
      resolveDoctor = resolve;
    });
  const rendered = await renderInDom(<App />, (window) => {
    window.desktop = bridge;
  });
  try {
    const input = rendered.document.querySelector<HTMLTextAreaElement>("#task-input")!;
    assert.equal(input.disabled, false);
    await setInputValue(input, "Draft while Sidecar starts");
    assert.equal(input.value, "Draft while Sidecar starts");
    assert.equal(calls.createSession, 0);
    await act(async () => {
      resolveDoctor?.({ ok: true, data: doctor });
      await flushPromises();
    });
    assert.equal(input.value, "Draft while Sidecar starts");
  } finally {
    await rendered.cleanup();
  }
});

async function dispatchKey(
  rendered: Awaited<ReturnType<typeof renderInDom>>,
  target: Element | Window,
  init: KeyboardEventInit,
): Promise<void> {
  await act(async () => {
    target.dispatchEvent(
      new rendered.window.KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        ...init,
      }),
    );
    await flushPromises();
  });
}

function buttonWithText(document: Document, text: string): HTMLButtonElement {
  const button = Array.from(document.querySelectorAll("button")).find(
    (candidate) => candidate.textContent?.includes(text),
  );
  assert.ok(button, `Missing button containing ${text}`);
  return button;
}

import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import type { IpcMain } from "electron";

import {
  createTrustedIdentifierIpcHandler,
  createTrustedIdentifierListIpcHandler,
  createTrustedIpcHandler,
  createTrustedPathListIpcHandler,
  createTrustedQuestionIpcHandler,
  createTrustedModelSettingsIpcHandler,
  createTrustedSessionRenameIpcHandler,
  registerDesktopIpc,
} from "./ipc";

test("model settings IPC accepts only exact supported routes without exposing generic payloads", async () => {
  const calls: unknown[] = [];
  const handler = createTrustedModelSettingsIpcHandler(async (settings) => {
    calls.push(settings);
    return "ok";
  });
  const settings = {
    chat: {
      provider: "openai_compatible",
      base_url: "https://api.openai.com/v1",
      model: "gpt-4o-mini",
      api_version: "",
      credential: "configured-secret",
    },
    embedding: {
      provider: "ollama",
      base_url: "http://127.0.0.1:11434/v1",
      model: "nomic-embed-text",
      api_version: "",
      credential: null,
    },
  };

  assert.equal(
    await handler({ senderFrame: { url: "mara://app/" } }, settings),
    "ok",
  );
  assert.equal(calls.length, 1);
  await assert.rejects(
    handler(
      { senderFrame: { url: "https://attacker.invalid/" } },
      settings,
    ),
    /Untrusted IPC sender/,
  );
  await assert.rejects(
    handler(
      { senderFrame: { url: "mara://app/" } },
      { ...settings, url: "file:///private/config" },
    ),
    /invalid model settings/,
  );
  await assert.rejects(
    handler(
      { senderFrame: { url: "mara://app/" } },
      {
        ...settings,
        chat: { ...settings.chat, provider: "arbitrary-provider" },
      },
    ),
    /invalid model settings/,
  );
});

test("question IPC validates only a conversation, prompt, and source ids", async () => {
  const calls: unknown[] = [];
  const handler = createTrustedQuestionIpcHandler(async (request) => {
    calls.push(request);
    return "ok";
  });
  const valid = {
    conversation_id: "session-1",
    prompt: "  Compare the evidence.  ",
    selected_file_ids: ["file-1", "file-2"],
  };

  assert.equal(
    await handler({ senderFrame: { url: "mara://app/" } }, valid),
    "ok",
  );
  assert.deepEqual(calls, [
    {
      ...valid,
      prompt: "Compare the evidence.",
    },
  ]);
  await assert.rejects(
    handler(
      { senderFrame: { url: "https://attacker.invalid/" } },
      valid,
    ),
    /Untrusted IPC sender/,
  );
  await assert.rejects(
    handler(
      { senderFrame: { url: "mara://app/" } },
      { ...valid, model: "private-model" },
    ),
    /invalid question/,
  );
  await assert.rejects(
    handler(
      { senderFrame: { url: "mara://app/" } },
      { ...valid, selected_file_ids: ["file-1", "/private/paper.pdf"] },
    ),
    /invalid question/,
  );
  await assert.rejects(
    handler(
      { senderFrame: { url: "mara://app/" } },
      {
        ...valid,
        selected_file_ids: Array.from({ length: 65 }, (_, index) => `file-${index}`),
      },
    ),
    /invalid question/,
  );
});

test("trusted desktop IPC accepts only the packaged renderer and no arguments", async () => {
  const handler = createTrustedIpcHandler(async () => "ok");

  assert.equal(
    await handler({ senderFrame: { url: "mara://app/" } }),
    "ok",
  );
  await assert.rejects(
    handler({ senderFrame: { url: "https://attacker.invalid/" } }),
    /Untrusted IPC sender/,
  );
  await assert.rejects(
    handler({ senderFrame: { url: "mara://app/" } }, { path: "/etc/passwd" }),
    /does not accept arguments/,
  );
});

test("dropped-file IPC accepts only trusted absolute path lists", async () => {
  const selectedPath = path.resolve("private", "source", "paper.pdf");
  const calls: string[][] = [];
  const handler = createTrustedPathListIpcHandler(async (filePaths) => {
    calls.push(filePaths);
    return "ok";
  });

  assert.equal(
    await handler({ senderFrame: { url: "mara://app/" } }, [selectedPath]),
    "ok",
  );
  assert.deepEqual(calls, [[selectedPath]]);
  await assert.rejects(
    handler(
      { senderFrame: { url: "https://attacker.invalid/" } },
      [selectedPath],
    ),
    /Untrusted IPC sender/,
  );
  await assert.rejects(
    handler({ senderFrame: { url: "mara://app/" } }, ["relative/paper.pdf"]),
    /invalid file list/,
  );
  await assert.rejects(
    handler(
      { senderFrame: { url: "mara://app/" } },
      [selectedPath, selectedPath],
    ),
    /invalid file list/,
  );
});

test("batch mutation IPC validates a bounded list of opaque identifiers", async () => {
  const calls: string[][] = [];
  const handler = createTrustedIdentifierListIpcHandler(async (identifiers) => {
    calls.push(identifiers);
    return "ok";
  });

  assert.equal(
    await handler(
      { senderFrame: { url: "mara://app/" } },
      ["file-1", "file-2"],
    ),
    "ok",
  );
  assert.deepEqual(calls, [["file-1", "file-2"]]);
  await assert.rejects(
    handler(
      { senderFrame: { url: "https://attacker.invalid/" } },
      ["file-1"],
    ),
    /Untrusted IPC sender/,
  );
  await assert.rejects(
    handler({ senderFrame: { url: "mara://app/" } }, []),
    /non-empty identifier list/,
  );
  await assert.rejects(
    handler(
      { senderFrame: { url: "mara://app/" } },
      ["file-1", "/etc/passwd"],
    ),
    /invalid identifier list/,
  );
  await assert.rejects(
    handler(
      { senderFrame: { url: "mara://app/" } },
      ["file-1", "file-1"],
    ),
    /invalid identifier list/,
  );
});

test("mutation IPC validates the packaged sender and one opaque identifier", async () => {
  const calls: string[] = [];
  const handler = createTrustedIdentifierIpcHandler(async (identifier) => {
    calls.push(identifier);
    return "ok";
  });

  assert.equal(
    await handler({ senderFrame: { url: "mara://app/" } }, "file-1"),
    "ok",
  );
  assert.deepEqual(calls, ["file-1"]);
  await assert.rejects(
    handler({ senderFrame: { url: "https://attacker.invalid/" } }, "file-1"),
    /Untrusted IPC sender/,
  );
  await assert.rejects(
    handler({ senderFrame: { url: "mara://app/" } }, "/etc/passwd"),
    /invalid identifier/,
  );
  await assert.rejects(
    handler({ senderFrame: { url: "mara://app/" } }, "file-1", "extra"),
    /exactly one identifier/,
  );
});

test("session rename IPC validates one identifier and one bounded name", async () => {
  const calls: Array<[string, string]> = [];
  const handler = createTrustedSessionRenameIpcHandler(
    async (conversationId, name) => {
      calls.push([conversationId, name]);
      return "ok";
    },
  );

  assert.equal(
    await handler(
      { senderFrame: { url: "mara://app/" } },
      "session-1",
      "  Renamed session  ",
    ),
    "ok",
  );
  assert.deepEqual(calls, [["session-1", "Renamed session"]]);
  await assert.rejects(
    handler(
      { senderFrame: { url: "https://attacker.invalid/" } },
      "session-1",
      "Rejected",
    ),
    /Untrusted IPC sender/,
  );
  await assert.rejects(
    handler(
      { senderFrame: { url: "mara://app/" } },
      "/etc/passwd",
      "Rejected",
    ),
    /invalid session rename/,
  );
  await assert.rejects(
    handler(
      { senderFrame: { url: "mara://app/" } },
      "session-1",
      "   ",
    ),
    /invalid session rename/,
  );
  await assert.rejects(
    handler(
      { senderFrame: { url: "mara://app/" } },
      "session-1",
      "x".repeat(201),
    ),
    /invalid session rename/,
  );
  await assert.rejects(
    handler(
      { senderFrame: { url: "mara://app/" } },
      "session-1",
      "Name",
      "extra",
    ),
    /exactly one identifier and one name/,
  );
});

test("registers only explicit desktop capabilities", () => {
  const channels: string[] = [];
  const registrar = {
    handle(channel: string) {
      channels.push(channel);
    },
  } as unknown as IpcMain;

  registerDesktopIpc(registrar, {
    getRuntimeStatus: () => ({ state: "healthy", protocol: 1, capabilities: [] }),
    getDoctor: async () => ({ ok: true, data: {} as never }),
    listFiles: async () => ({ ok: true, data: [] }),
    listSessions: async () => ({ ok: true, data: [] }),
    getSession: async () => ({ ok: true, data: {} as never }),
    createSession: async () => ({ ok: true, data: {} as never }),
    renameSession: async () => ({ ok: true, data: {} as never }),
    deleteSession: async () => ({ ok: true, data: "session-1" }),
    importFiles: async () => ({ ok: true, data: null }),
    importDroppedFiles: async () => ({ ok: true, data: {} as never }),
    openEmbeddingConfiguration: async () => ({ ok: true, data: true }),
    getModelSettings: async () => ({ ok: true, data: {} as never }),
    saveModelSettings: async () => ({ ok: true, data: {} as never }),
    getLatestIndexTask: async () => ({ ok: true, data: null }),
    cancelIndexTask: async () => ({ ok: true, data: {} as never }),
    retryIndexTask: async () => ({ ok: true, data: {} as never }),
    deleteFile: async () => ({ ok: true, data: ["file-1"] }),
    deleteFiles: async () => ({ ok: true, data: ["file-1", "file-2"] }),
    submitQuestion: async () => ({ ok: true, data: {} as never }),
    getLatestAnswerTask: async () => ({ ok: true, data: null }),
    cancelAnswer: async () => ({ ok: true, data: {} as never }),
    retryAnswer: async () => ({ ok: true, data: {} as never }),
  });

  assert.deepEqual(channels, [
    "desktop:get-runtime-status",
    "desktop:get-doctor",
    "desktop:list-files",
    "desktop:list-sessions",
    "desktop:get-session",
    "desktop:create-session",
    "desktop:rename-session",
    "desktop:delete-session",
    "desktop:import-files",
    "desktop:import-dropped-files",
    "desktop:open-embedding-configuration",
    "desktop:get-model-settings",
    "desktop:save-model-settings",
    "desktop:get-latest-index-task",
    "desktop:cancel-index-task",
    "desktop:retry-index-task",
    "desktop:delete-file",
    "desktop:delete-files",
    "desktop:submit-question",
    "desktop:get-latest-answer-task",
    "desktop:cancel-answer",
    "desktop:retry-answer",
  ]);
});

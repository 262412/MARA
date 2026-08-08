import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import type { IpcMain } from "electron";

import {
  createTrustedIdentifierIpcHandler,
  createTrustedIdentifierListIpcHandler,
  createTrustedIpcHandler,
  createTrustedPathListIpcHandler,
  registerDesktopIpc,
} from "./ipc";

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
    importFiles: async () => ({ ok: true, data: null }),
    importDroppedFiles: async () => ({ ok: true, data: {} as never }),
    getLatestIndexTask: async () => ({ ok: true, data: null }),
    cancelIndexTask: async () => ({ ok: true, data: {} as never }),
    retryIndexTask: async () => ({ ok: true, data: {} as never }),
    deleteFile: async () => ({ ok: true, data: ["file-1"] }),
    deleteFiles: async () => ({ ok: true, data: ["file-1", "file-2"] }),
  });

  assert.deepEqual(channels, [
    "desktop:get-runtime-status",
    "desktop:get-doctor",
    "desktop:list-files",
    "desktop:list-sessions",
    "desktop:get-session",
    "desktop:import-files",
    "desktop:import-dropped-files",
    "desktop:get-latest-index-task",
    "desktop:cancel-index-task",
    "desktop:retry-index-task",
    "desktop:delete-file",
    "desktop:delete-files",
  ]);
});

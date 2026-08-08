import assert from "node:assert/strict";
import test from "node:test";

import type { IpcMain } from "electron";

import {
  createTrustedIdentifierIpcHandler,
  createTrustedIpcHandler,
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

test("registers only explicit Gate 2 and Gate 3 desktop capabilities", () => {
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
    importFiles: async () => ({ ok: true, data: null }),
    getLatestIndexTask: async () => ({ ok: true, data: null }),
    cancelIndexTask: async () => ({ ok: true, data: {} as never }),
    retryIndexTask: async () => ({ ok: true, data: {} as never }),
    deleteFile: async () => ({ ok: true, data: ["file-1"] }),
  });

  assert.deepEqual(channels, [
    "desktop:get-runtime-status",
    "desktop:get-doctor",
    "desktop:list-files",
    "desktop:list-sessions",
    "desktop:import-files",
    "desktop:get-latest-index-task",
    "desktop:cancel-index-task",
    "desktop:retry-index-task",
    "desktop:delete-file",
  ]);
});

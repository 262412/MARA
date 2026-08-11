import assert from "node:assert/strict";
import test from "node:test";

import {
  runIndexingBlockedRendererSmoke,
  runRendererBridgeSmoke,
} from "./renderer-bridge-smoke";

const successfulResult = {
  bridgeAvailable: true,
  missingMethods: [],
  runtimeState: "healthy",
  doctorOk: true,
  filesOk: true,
  sessionsOk: true,
  unavailableMessageVisible: false,
};

test("packaged renderer smoke exercises the narrow bridge and real IPC methods", async () => {
  let script = "";
  const messages: string[] = [];
  await runRendererBridgeSmoke(
    {
      executeJavaScript: async (source: string) => {
        script = source;
        return successfulResult;
      },
    },
    (message: string) => messages.push(message),
  );

  assert.match(script, /window\.desktop/);
  for (const method of [
    "getRuntimeStatus",
    "getDoctor",
    "listFiles",
    "listSessions",
  ]) {
    assert.match(script, new RegExp(`bridge\\.${method}\\(\\)`));
  }
  assert.deepEqual(messages, [
    "renderer_bridge=window.desktop real_ipc=runtime,doctor,files,sessions status_success",
  ]);
});

test("packaged renderer smoke rejects a missing preload bridge", async () => {
  await assert.rejects(
    runRendererBridgeSmoke({
      executeJavaScript: async () => ({
        ...successfulResult,
        bridgeAvailable: false,
        missingMethods: ["getDoctor"],
      }),
    }),
    /window\.desktop is unavailable; missing methods: getDoctor/,
  );
});

test("packaged renderer smoke rejects failed IPC and fallback UI", async () => {
  await assert.rejects(
    runRendererBridgeSmoke({
      executeJavaScript: async () => ({
        ...successfulResult,
        filesOk: false,
        unavailableMessageVisible: true,
      }),
    }),
    /Files IPC failed; renderer displayed the bridge-unavailable fallback/,
  );
});

test("packaged renderer smoke verifies the real unconfigured Files UI", async () => {
  let script = "";
  const messages: string[] = [];
  await runIndexingBlockedRendererSmoke(
    {
      executeJavaScript: async (source) => {
        script = source;
        return {
          addButtonDisabled: true,
          configActionVisible: true,
          doctorBlocked: true,
          dropPromptVisible: false,
          issueCodeVisible: true,
          latestTaskEmpty: true,
        };
      },
    },
    (message) => messages.push(message),
  );

  assert.match(script, /bridge\.getDoctor\(\)/);
  assert.match(script, /bridge\.getLatestIndexTask\(\)/);
  assert.match(script, /文件索引尚未准备好/);
  assert.match(script, /embedding_not_configured/);
  assert.deepEqual(messages, [
    "renderer_indexing=embedding_not_configured ui_blocked=true latest_task=empty status_success",
  ]);
});

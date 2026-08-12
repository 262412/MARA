import assert from "node:assert/strict";
import test from "node:test";

import { runRendererWorkbenchSmoke } from "./renderer-workbench-smoke";

const navigationResult = {
  altEnterOk: true,
  blockedTaskEmpty: true,
  configurationActionVisible: true,
  draftEditable: true,
  draftPromptPreserved: true,
  imeAndRepeatBlocked: true,
  modelSettingsRedacted: true,
  navigationOk: true,
  queryCitationCount: 0,
  queryCitationMarkersOk: true,
  queryConversationId: null,
  queryMarkdownOk: true,
  queryMessageCount: 0,
  queryStatus: null,
  queryUnsafeContentBlocked: true,
  sessionDelta: 0,
};

test("packaged renderer navigation smoke uses real pages and keyboard events", async () => {
  let source = "";
  const messages: string[] = [];
  await runRendererWorkbenchSmoke(
    {
      executeJavaScript: async (script) => {
        source = script;
        return navigationResult;
      },
    },
    "navigation",
    (message) => messages.push(message),
  );

  assert.match(source, /button\("Resources"\)/);
  assert.match(source, /\["Help",/);
  assert.match(source, /\["Settings",/);
  assert.match(source, /altKey: true/);
  assert.match(source, /getModelSettings/);
  assert.doesNotThrow(() => new Function(`return ${source}`));
  assert.deepEqual(messages, [
    "renderer_ui=real-navigation,draft,settings,keyboard mode=navigation status_success",
  ]);
});

test("packaged renderer blocked smoke requires no task and a preserved draft", async () => {
  await assert.rejects(
    runRendererWorkbenchSmoke(
      { executeJavaScript: async () => ({ ...navigationResult, blockedTaskEmpty: false }) },
      "blocked",
    ),
    /blocked query created persisted work/,
  );
});

test("packaged renderer query smoke requires one persisted cited answer", async () => {
  const messages: string[] = [];
  const conversationId = await runRendererWorkbenchSmoke(
    {
      executeJavaScript: async () => ({
        ...navigationResult,
        queryCitationCount: 1,
        queryConversationId: "renderer-session",
        queryMessageCount: 2,
        queryStatus: "success",
        sessionDelta: 1,
      }),
    },
    "query",
    (message) => messages.push(message),
  );
  assert.equal(conversationId, "renderer-session");
  assert.ok(
    messages.includes(
      "renderer_markdown=heading,list,table,code,blockquote,katex,citations,safe-links status_success",
    ),
  );
});

test("packaged renderer query smoke requires semantic and safe Markdown DOM", async () => {
  await assert.rejects(
    runRendererWorkbenchSmoke(
      {
        executeJavaScript: async () => ({
          ...navigationResult,
          queryCitationCount: 1,
          queryCitationMarkersOk: false,
          queryConversationId: "renderer-session",
          queryMarkdownOk: false,
          queryMessageCount: 2,
          queryStatus: "success",
          queryUnsafeContentBlocked: false,
          sessionDelta: 1,
        }),
      },
      "query",
    ),
    /citation markers changed.*semantic DOM.*unsafe Markdown content/,
  );
});

test("packaged renderer settings smoke saves through the real page and refreshes Doctor", async () => {
  let source = "";
  await runRendererWorkbenchSmoke(
    {
      executeJavaScript: async (script) => {
        source = script;
        return {
          ...navigationResult,
          modelSettingsApplied: true,
          modelSettingsReady: true,
        };
      },
    },
    "settings",
    () => undefined,
    {
      baseUrl: "http://127.0.0.1:43127/v1",
      provider: "openai_compatible",
      credential: "packaged-fake-key",
    },
  );

  assert.match(source, /chat\.provider/);
  assert.match(source, /embedding\.provider/);
  assert.match(source, /保存并应用/);
  assert.match(source, /query_ready/);
  assert.match(source, /indexing_ready/);
  assert.match(source, /openai_compatible/);
  assert.match(source, /packaged-fake-key/);
});

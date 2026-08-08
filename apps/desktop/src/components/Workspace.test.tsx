import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import type { SessionDetail } from "../../shared/session-contracts";
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

function render(session: ResourceState<SessionDetail> | undefined) {
  return renderToStaticMarkup(
    <Workspace
      onRetrySession={() => undefined}
      onToggleInspector={() => undefined}
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

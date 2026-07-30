import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import type { SessionSummary } from "../../shared/session-contracts";
import type { ResourceState } from "../resource-state";
import { Sidebar } from "./Sidebar";

const session: SessionSummary = {
  conversation_id: "session-1",
  name: "Research session",
  message_count: 3,
  graph_source_count: 2,
  origin: "desktop",
  is_public: false,
  date_created: "2026-07-30T10:00:00",
  date_updated: "2026-07-30T10:05:00",
};

function render(sessions: ResourceState<SessionSummary[]>) {
  return renderToStaticMarkup(
    <Sidebar
      active="workbench"
      onNavigate={() => undefined}
      onRetrySessions={() => undefined}
      onSelectSession={() => undefined}
      selectedSessionId={undefined}
      sessions={sessions}
    />,
  );
}

test("Sessions list covers loading, success, empty, and failed states", () => {
  assert.match(render({ status: "loading" }), /正在读取最近任务/);
  assert.match(render({ status: "success", data: [session] }), /Research session/);
  assert.match(render({ status: "success", data: [] }), /还没有保存的任务/);
  assert.match(
    render({ status: "failed", message: "无法读取会话" }),
    /无法读取会话/,
  );
  assert.match(
    render({ status: "failed", message: "无法读取会话" }),
    /重试/,
  );
});

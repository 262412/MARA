import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import type { SessionSummary } from "../../shared/session-contracts";
import type { ResourceState } from "../resource-state";
import { filterSessions, Sidebar } from "./Sidebar";

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

function render(
  sessions: ResourceState<SessionSummary[]>,
  options: {
    searchQuery?: string;
    editingSessionId?: string;
    editingSessionName?: string;
    sessionAction?: {
      conversationId: string;
      action: "rename" | "delete";
    };
    sessionActionError?: string;
  } = {},
) {
  return renderToStaticMarkup(
    <Sidebar
      active="workbench"
      editingSessionId={options.editingSessionId}
      editingSessionName={options.editingSessionName ?? ""}
      onCancelRename={() => undefined}
      onDeleteSession={() => undefined}
      onEditingSessionNameChange={() => undefined}
      onNavigate={() => undefined}
      onRenameSession={() => undefined}
      onRetrySessions={() => undefined}
      onSearchQueryChange={() => undefined}
      onSelectSession={() => undefined}
      onStartRename={() => undefined}
      searchQuery={options.searchQuery ?? ""}
      selectedSessionId={undefined}
      sessionAction={options.sessionAction}
      sessionActionError={options.sessionActionError}
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

test("Sessions search is case-insensitive and renders a no-match state", () => {
  const other = {
    ...session,
    conversation_id: "session-2",
    name: "Finance review",
  };

  assert.deepEqual(
    filterSessions([session, other], "  FINANCE ").map(
      (item) => item.conversation_id,
    ),
    ["session-2"],
  );
  const filtered = render(
    { status: "success", data: [session, other] },
    { searchQuery: "finance" },
  );
  assert.doesNotMatch(filtered, />Research session</);
  assert.match(filtered, /Finance review/);
  assert.match(
    render(
      { status: "success", data: [session] },
      { searchQuery: "missing" },
    ),
    /未找到匹配的任务/,
  );
});

test("Session actions cover editing, pending, and failed states", () => {
  const editing = render(
    { status: "success", data: [session] },
    {
      editingSessionId: "session-1",
      editingSessionName: "Renamed session",
    },
  );
  assert.match(editing, /任务名称/);
  assert.match(editing, /value="Renamed session"/);
  assert.match(editing, /保存/);
  assert.match(editing, /取消/);

  const deleting = render(
    { status: "success", data: [session] },
    {
      sessionAction: { conversationId: "session-1", action: "delete" },
    },
  );
  assert.match(deleting, /正在删除/);
  assert.match(
    render(
      { status: "success", data: [session] },
      { sessionActionError: "会话删除失败" },
    ),
    /role="alert">会话删除失败/,
  );
});

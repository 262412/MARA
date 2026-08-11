import type { SessionSummary } from "../../shared/session-contracts";
import type { ResourceState } from "../resource-state";
import type { AppPage } from "../navigation";
import { Icon, type IconName } from "./Icon";

type SidebarProps = {
  active: AppPage;
  onNavigate: (value: AppPage) => void;
  sessions: ResourceState<SessionSummary[]>;
  selectedSessionId: string | undefined;
  onSelectSession: (sessionId: string) => void;
  onRetrySessions: () => void;
  onCreateSession: () => void;
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  editingSessionId: string | undefined;
  editingSessionName: string;
  onStartRename: (session: SessionSummary) => void;
  onEditingSessionNameChange: (value: string) => void;
  onCancelRename: () => void;
  onRenameSession: (conversationId: string, name: string) => void;
  onDeleteSession: (session: SessionSummary) => void;
  sessionAction:
    | { conversationId: string; action: "rename" | "delete" }
    | undefined;
  sessionActionError: string | undefined;
  sessionCreatePending: boolean;
};

const navigation: Array<{ id: AppPage; label: string; icon: IconName }> = [
  { id: "workbench", label: "工作台", icon: "workbench" },
  { id: "files", label: "Files", icon: "files" },
  { id: "resources", label: "Resources", icon: "resources" },
  { id: "help", label: "Help", icon: "help" },
];

export function Sidebar({
  active,
  onNavigate,
  sessions,
  selectedSessionId,
  onSelectSession,
  onRetrySessions,
  onCreateSession,
  searchQuery,
  onSearchQueryChange,
  editingSessionId,
  editingSessionName,
  onStartRename,
  onEditingSessionNameChange,
  onCancelRename,
  onRenameSession,
  onDeleteSession,
  sessionAction,
  sessionActionError,
  sessionCreatePending,
}: SidebarProps) {
  const visibleSessions =
    sessions.status === "success"
      ? filterSessions(sessions.data, searchQuery)
      : [];
  const actionPending = sessionAction !== undefined || sessionCreatePending;

  return (
    <aside className="sidebar" aria-label="应用导航">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">M</span>
        <div>
          <strong>MARA</strong>
          <span>Local research</span>
        </div>
      </div>

      <button
        className="new-task"
        disabled={sessionCreatePending || actionPending}
        onClick={onCreateSession}
        type="button"
      >
        <Icon name="add" />
        {sessionCreatePending ? "正在新建…" : "新建任务"}
        <kbd>Ctrl N</kbd>
      </button>

      <nav className="primary-nav" aria-label="主要页面">
        {navigation.map((item) => (
          <button
            aria-current={active === item.id ? "page" : undefined}
            className={active === item.id ? "nav-item active" : "nav-item"}
            key={item.id}
            onClick={() => onNavigate(item.id)}
            type="button"
          >
            <Icon name={item.icon} />
            {item.label}
          </button>
        ))}
      </nav>

      <div className="recent-heading">
        <label htmlFor="session-search">最近任务</label>
      </div>
      <div className="session-search">
        <Icon name="search" size={15} />
        <input
          autoComplete="off"
          id="session-search"
          onChange={(event) => onSearchQueryChange(event.target.value)}
          placeholder="搜索最近任务"
          type="search"
          value={searchQuery}
        />
      </div>
      <div className="task-list" role="list">
        {sessionActionError ? (
          <p className="session-action-error" role="alert">
            {sessionActionError}
          </p>
        ) : null}
        {sessions.status === "loading" ? (
          <p className="sidebar-state">正在读取最近任务…</p>
        ) : null}
        {sessions.status === "failed" ? (
          <div className="sidebar-state" role="alert">
            <span>{sessions.message}</span>
            <button onClick={onRetrySessions} type="button">重试</button>
          </div>
        ) : null}
        {sessions.status === "success" && sessions.data.length === 0 ? (
          <p className="sidebar-state">还没有保存的任务</p>
        ) : null}
        {sessions.status === "success" &&
        sessions.data.length > 0 &&
        visibleSessions.length === 0 ? (
          <p className="sidebar-state">未找到匹配的任务</p>
        ) : null}
        {sessions.status === "success"
          ? visibleSessions.map((session) => {
              const isEditing = editingSessionId === session.conversation_id;
              const rowPending =
                sessionAction?.conversationId === session.conversation_id;
              if (isEditing) {
                return (
                  <form
                    className="session-editor"
                    key={session.conversation_id}
                    onSubmit={(event) => {
                      event.preventDefault();
                      onRenameSession(
                        session.conversation_id,
                        editingSessionName,
                      );
                    }}
                    role="listitem"
                  >
                    <label
                      className="sr-only"
                      htmlFor={`session-name-${session.conversation_id}`}
                    >
                      任务名称
                    </label>
                    <input
                      autoFocus
                      disabled={rowPending}
                      id={`session-name-${session.conversation_id}`}
                      maxLength={200}
                      onChange={(event) =>
                        onEditingSessionNameChange(event.target.value)
                      }
                      value={editingSessionName}
                    />
                    {rowPending ? (
                      <span className="session-action-status">
                        正在重命名…
                      </span>
                    ) : (
                      <div className="session-editor-actions">
                        <button
                          disabled={editingSessionName.trim().length === 0}
                          type="submit"
                        >
                          保存
                        </button>
                        <button onClick={onCancelRename} type="button">
                          取消
                        </button>
                      </div>
                    )}
                  </form>
                );
              }
              return (
                <div className="task-row" key={session.conversation_id} role="listitem">
                  <button
                    aria-current={
                      selectedSessionId === session.conversation_id
                        ? "true"
                        : undefined
                    }
                    className={
                      selectedSessionId === session.conversation_id
                        ? "task active"
                        : "task"
                    }
                    disabled={rowPending && sessionAction.action === "delete"}
                    onClick={() => onSelectSession(session.conversation_id)}
                    type="button"
                  >
                    <span>{session.name || "未命名任务"}</span>
                    <small>
                      {session.message_count} 条消息 · {session.graph_source_count} 个图谱来源
                    </small>
                  </button>
                  {rowPending ? (
                    <span className="session-action-status">
                      {sessionAction.action === "delete"
                        ? "正在删除…"
                        : "正在重命名…"}
                    </span>
                  ) : (
                    <div className="task-actions">
                      <button
                        aria-label={`重命名${session.name || "未命名任务"}`}
                        disabled={actionPending}
                        onClick={() => onStartRename(session)}
                        type="button"
                      >
                        重命名
                      </button>
                      <button
                        aria-label={`删除${session.name || "未命名任务"}`}
                        disabled={actionPending}
                        onClick={() => onDeleteSession(session)}
                        type="button"
                      >
                        删除
                      </button>
                    </div>
                  )}
                </div>
              );
            })
          : null}
      </div>

      <div className="sidebar-footer">
        <button
          aria-current={active === "settings" ? "page" : undefined}
          className={active === "settings" ? "nav-item active" : "nav-item"}
          onClick={() => onNavigate("settings")}
          type="button"
        >
          <Icon name="settings" />
          Settings
        </button>
        <div className="data-space">
          <span className="status-dot healthy" />
          <div>
            <strong>本地数据空间</strong>
            <span>默认工作区</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

export function filterSessions(
  sessions: SessionSummary[],
  query: string,
): SessionSummary[] {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  if (!normalizedQuery) {
    return sessions;
  }
  return sessions.filter((session) =>
    (session.name || "未命名任务")
      .toLocaleLowerCase()
      .includes(normalizedQuery),
  );
}

import type { SessionSummary } from "../../shared/session-contracts";
import type { ResourceState } from "../resource-state";
import { Icon, type IconName } from "./Icon";

type SidebarProps = {
  active: string;
  onNavigate: (value: string) => void;
  sessions: ResourceState<SessionSummary[]>;
  selectedSessionId: string | undefined;
  onSelectSession: (sessionId: string) => void;
  onRetrySessions: () => void;
};

const navigation: Array<{ id: string; label: string; icon: IconName }> = [
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
}: SidebarProps) {
  return (
    <aside className="sidebar" aria-label="应用导航">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">M</span>
        <div>
          <strong>MARA</strong>
          <span>Local research</span>
        </div>
      </div>

      <button className="new-task" type="button">
        <Icon name="add" />
        新建任务
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
        <span>最近任务</span>
        <button aria-label="搜索任务" className="icon-button" type="button">
          <Icon name="search" size={16} />
        </button>
      </div>
      <div className="task-list" role="list">
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
        {sessions.status === "success"
          ? sessions.data.map((session) => (
              <button
                aria-current={
                  selectedSessionId === session.conversation_id ? "true" : undefined
                }
                className={
                  selectedSessionId === session.conversation_id
                    ? "task active"
                    : "task"
                }
                key={session.conversation_id}
                onClick={() => onSelectSession(session.conversation_id)}
                role="listitem"
                type="button"
              >
                <span>{session.name || "未命名任务"}</span>
                <small>
                  {session.message_count} 条消息 · {session.graph_source_count} 个图谱来源
                </small>
              </button>
            ))
          : null}
      </div>

      <div className="sidebar-footer">
        <button className="nav-item" type="button">
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

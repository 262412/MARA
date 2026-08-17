import type { SessionSummary } from "../../shared/session-contracts";
import type { ResourceState } from "../resource-state";
import type { AppPage } from "../navigation";
import { useLanguage } from "../i18n";
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

const navigation: Array<{ id: AppPage; icon: IconName }> = [
  { id: "workbench", icon: "workbench" },
  { id: "files", icon: "files" },
  { id: "resources", icon: "resources" },
  { id: "help", icon: "help" },
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
  const { t } = useLanguage();
  const visibleSessions =
    sessions.status === "success"
      ? filterSessions(sessions.data, searchQuery, t("common.unnamedTask"))
      : [];
  const actionPending = sessionAction !== undefined || sessionCreatePending;

  return (
    <aside className="sidebar" aria-label={t("nav.appNavigation")}>
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">M</span>
        <div>
          <strong>MARA</strong>
          <span>{t("brand.localResearch")}</span>
        </div>
      </div>

      <button
        className="new-task"
        disabled={sessionCreatePending || actionPending}
        onClick={onCreateSession}
        type="button"
      >
        <Icon name="add" />
        {sessionCreatePending ? t("sidebar.newTaskPending") : t("sidebar.newTask")}
        <kbd>Ctrl N</kbd>
      </button>

      <nav className="primary-nav" aria-label={t("nav.primaryPages")}>
        {navigation.map((item) => (
          <button
            aria-current={active === item.id ? "page" : undefined}
            className={active === item.id ? "nav-item active" : "nav-item"}
            key={item.id}
            onClick={() => onNavigate(item.id)}
            type="button"
          >
            <Icon name={item.icon} />
            {t(`nav.${item.id}` as Parameters<typeof t>[0])}
          </button>
        ))}
      </nav>

      <div className="recent-heading">
        <label htmlFor="session-search">{t("sidebar.recentTasks")}</label>
      </div>
      <div className="session-search">
        <Icon name="search" size={15} />
        <input
          autoComplete="off"
          id="session-search"
          onChange={(event) => onSearchQueryChange(event.target.value)}
          placeholder={t("sidebar.searchRecentTasks")}
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
          <p className="sidebar-state">{t("sidebar.loadingRecentTasks")}</p>
        ) : null}
        {sessions.status === "failed" ? (
          <div className="sidebar-state" role="alert">
            <span>{sessions.message}</span>
            <button onClick={onRetrySessions} type="button">{t("common.retry")}</button>
          </div>
        ) : null}
        {sessions.status === "success" && sessions.data.length === 0 ? (
          <p className="sidebar-state">{t("sidebar.noSavedTasks")}</p>
        ) : null}
        {sessions.status === "success" &&
        sessions.data.length > 0 &&
        visibleSessions.length === 0 ? (
          <p className="sidebar-state">{t("sidebar.noMatchingTasks")}</p>
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
                      {t("sidebar.sessionName")}
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
                        {t("sidebar.renaming")}
                      </span>
                    ) : (
                      <div className="session-editor-actions">
                        <button
                          disabled={editingSessionName.trim().length === 0}
                          type="submit"
                        >
                          {t("common.save")}
                        </button>
                        <button onClick={onCancelRename} type="button">
                          {t("common.cancel")}
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
                    <span>{session.name || t("common.unnamedTask")}</span>
                    <small>
                      {t("common.messageCount", {
                        messages: session.message_count,
                        sources: session.graph_source_count,
                      })}
                    </small>
                  </button>
                  {rowPending ? (
                    <span className="session-action-status">
                      {sessionAction.action === "delete"
                        ? t("sidebar.deleting")
                        : t("sidebar.renaming")}
                    </span>
                  ) : (
                    <div className="task-actions">
                      <button
                        aria-label={t("sidebar.renameAria", {
                          name: session.name || t("common.unnamedTask"),
                        })}
                        disabled={actionPending}
                        onClick={() => onStartRename(session)}
                        type="button"
                      >
                        {t("sidebar.rename")}
                      </button>
                      <button
                        aria-label={t("sidebar.deleteAria", {
                          name: session.name || t("common.unnamedTask"),
                        })}
                        disabled={actionPending}
                        onClick={() => onDeleteSession(session)}
                        type="button"
                      >
                        {t("sidebar.delete")}
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
          {t("nav.settings")}
        </button>
        <div className="data-space">
          <span className="status-dot healthy" />
          <div>
            <strong>{t("sidebar.localDataSpace")}</strong>
            <span>{t("sidebar.defaultWorkspace")}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

export function filterSessions(
  sessions: SessionSummary[],
  query: string,
  unnamedTask = "Untitled task",
): SessionSummary[] {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  if (!normalizedQuery) {
    return sessions;
  }
  return sessions.filter((session) =>
    (session.name || unnamedTask)
      .toLocaleLowerCase()
      .includes(normalizedQuery),
  );
}

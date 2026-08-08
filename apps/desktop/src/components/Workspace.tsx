import type { ReactNode } from "react";

import type { SessionDetail } from "../../shared/session-contracts";
import type { ResourceState } from "../resource-state";
import { Icon } from "./Icon";

type WorkspaceProps = {
  onRetrySession: () => void;
  onToggleInspector: () => void;
  session: ResourceState<SessionDetail> | undefined;
};

export function Workspace({
  onRetrySession,
  onToggleInspector,
  session,
}: WorkspaceProps) {
  const detail = session?.status === "success" ? session.data : undefined;
  const sourceCount = detail?.graph_source_ids.length ?? 0;

  return (
    <main className="workspace" id="main-workspace">
      <header className="workspace-toolbar">
        <div>
          <p className="eyebrow">研究任务</p>
          <h1>{detail?.name || "工作台"}</h1>
        </div>
        <div className="toolbar-actions">
          <span className="source-count">{sourceCount} 个来源</span>
          <button
            aria-label="显示或隐藏检查器"
            className="icon-button"
            onClick={onToggleInspector}
            type="button"
          >
            <Icon name="panel" />
          </button>
        </div>
      </header>

      <section className="conversation" aria-label="任务对话">
        {!session ? (
          <WorkspaceState>从左侧选择一个任务以查看真实 MARA 会话。</WorkspaceState>
        ) : null}
        {session?.status === "loading" ? (
          <WorkspaceState>正在读取会话…</WorkspaceState>
        ) : null}
        {session?.status === "failed" ? (
          <WorkspaceState role="alert">
            <span>{session.message}</span>
            <button onClick={onRetrySession} type="button">重试</button>
          </WorkspaceState>
        ) : null}
        {detail && detail.messages.length === 0 ? (
          <WorkspaceState>这个任务还没有消息。</WorkspaceState>
        ) : null}
        {detail?.messages.map((message, index) =>
          message.role === "user" ? (
            <div className="message user-message" key={`user-${index}`}>
              <div className="message-label">你</div>
              <p>{message.content}</p>
            </div>
          ) : (
            <article
              className="message assistant-message"
              key={`assistant-${index}`}
            >
              <div className="assistant-heading">
                <span className="assistant-mark" aria-hidden="true">M</span>
                <div>
                  <div className="message-label">MARA</div>
                  <small>已保存的回答</small>
                </div>
              </div>
              <p>{message.content}</p>
            </article>
          ),
        )}
      </section>

      <div className="composer-wrap">
        <div className="prototype-notice" role="status">
          真实会话读取已接通；新问题与流式回答将在下一纵向切片启用。
        </div>
        <div className="context-row">
          <button className="context-chip" disabled type="button">
            <Icon name="files" size={14} />
            {sourceCount} 个来源
          </button>
        </div>
        <div className="composer composer-disabled">
          <label className="sr-only" htmlFor="task-input">描述研究任务</label>
          <textarea
            disabled
            id="task-input"
            placeholder="问答能力尚未启用"
            rows={2}
          />
          <div className="composer-footer">
            <button className="add-source" disabled type="button">
              <Icon name="add" size={16} />
              添加
            </button>
            <button aria-label="发送" className="send-button" disabled type="button">
              <Icon name="send" size={17} />
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}

function WorkspaceState({
  children,
  role,
}: {
  children: ReactNode;
  role?: "alert";
}) {
  return (
    <div className="workspace-state" role={role}>
      {children}
    </div>
  );
}

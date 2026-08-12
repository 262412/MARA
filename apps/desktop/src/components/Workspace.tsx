import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import type { QueryCitation, QueryTask } from "../../shared/query-contracts";
import type { DoctorPayload } from "../../shared/doctor-contracts";
import type { SidecarError } from "../../shared/runtime-contracts";
import type { SessionDetail, SessionMessage } from "../../shared/session-contracts";
import type { ResourceState } from "../resource-state";
import { submittedPromptTransition } from "../query-task-state";
import { AssistantMarkdown } from "./AssistantMarkdown";
import { Icon } from "./Icon";

type WorkspaceProps = {
  answerActionError?: SidecarError;
  answerActionPending: boolean;
  answerTask?: QueryTask;
  modelName?: string;
  isDraft?: boolean;
  onPromptChange?: (value: string) => void;
  onCancelAnswer: () => void;
  onOpenSources: () => void;
  onOpenSettings?: () => void;
  onRetryAnswer: () => void;
  onRetrySession: () => void;
  onSubmitQuestion: (prompt: string) => void;
  onToggleInspector: () => void;
  selectedSourceCount: number;
  session: ResourceState<SessionDetail> | undefined;
  queryReadiness?: QueryReadiness;
  promptValue?: string;
  workspaceId?: string;
};

export type QueryReadiness = Pick<
  DoctorPayload,
  | "query_ready"
  | "query_issue_code"
  | "query_message"
  | "query_action"
  | "query_retryable"
  | "request_id"
>;

const readyQuery: QueryReadiness = {
  query_ready: true,
  query_issue_code: null,
  query_message: "Question answering is ready.",
  query_action: "none",
  query_retryable: false,
  request_id: "workspace-ready",
};

export function Workspace({
  answerActionError,
  answerActionPending,
  answerTask,
  isDraft = false,
  modelName,
  onCancelAnswer,
  onOpenSources,
  onOpenSettings = () => undefined,
  onPromptChange,
  onRetryAnswer,
  onRetrySession,
  onSubmitQuestion,
  onToggleInspector,
  selectedSourceCount,
  session,
  queryReadiness = readyQuery,
  promptValue,
  workspaceId = "workspace",
}: WorkspaceProps) {
  const [localPrompt, setLocalPrompt] = useState("");
  const prompt = promptValue ?? localPrompt;
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const consumedPromptTaskId = useRef<string | undefined>(undefined);
  const submitLock = useRef(false);
  const previousWorkspaceId = useRef(workspaceId);
  const detail = session?.status === "success" ? session.data : undefined;
  const visibleTask =
    answerTask && answerTask.conversation_id === detail?.conversation_id
      ? answerTask
      : undefined;
  const active = visibleTask?.status === "queued" || visibleTask?.status === "running";
  const backgroundActive = Boolean(
    answerTask &&
      answerTask !== visibleTask &&
      (answerTask.status === "queued" || answerTask.status === "running"),
  );
  const history = useMemo(
    () => messagesBeforeVisibleTask(detail, visibleTask),
    [detail, visibleTask],
  );
  const disabledReason = composerDisabledReason(
    isDraft,
    session,
    detail,
    selectedSourceCount,
    queryReadiness,
    active,
    backgroundActive,
    answerActionPending,
  );
  const canSubmit = !disabledReason && prompt.trim().length > 0;
  const setPrompt = (value: string) => {
    setLocalPrompt(value);
    onPromptChange?.(value);
  };

  useEffect(() => {
    const transition = submittedPromptTransition(
      prompt,
      visibleTask,
      consumedPromptTaskId.current,
    );
    consumedPromptTaskId.current = transition.consumedTaskId;
    if (transition.prompt !== prompt) {
      setPrompt(transition.prompt);
    }
  }, [prompt, visibleTask]);

  useEffect(() => {
    if (previousWorkspaceId.current === workspaceId) {
      return;
    }
    previousWorkspaceId.current = workspaceId;
    setPrompt("");
    consumedPromptTaskId.current = undefined;
    submitLock.current = false;
  }, [workspaceId]);

  useEffect(() => {
    if (!answerActionPending && (answerActionError || visibleTask)) {
      submitLock.current = false;
    }
  }, [answerActionError, answerActionPending, visibleTask]);

  useEffect(() => {
    const handleShortcut = (event: globalThis.KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "l") {
        event.preventDefault();
        inputRef.current?.focus();
      } else if (event.key === "Escape" && active) {
        event.preventDefault();
        if (window.confirm("停止当前回答？已经生成的内容会保留。")) {
          onCancelAnswer();
        }
      }
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [active, onCancelAnswer]);

  const submit = () => {
    const normalized = prompt.trim();
    if (canSubmit && normalized && !submitLock.current) {
      submitLock.current = true;
      onSubmitQuestion(normalized);
    }
  };
  const handlePromptKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.nativeEvent.isComposing) {
      return;
    }
    if (event.altKey) {
      event.preventDefault();
      const input = event.currentTarget;
      const start = input.selectionStart ?? prompt.length;
      const end = input.selectionEnd ?? start;
      const nextPrompt = `${prompt.slice(0, start)}\n${prompt.slice(end)}`;
      const caret = start + 1;
      setPrompt(nextPrompt);
      queueMicrotask(() => input.setSelectionRange(caret, caret));
      return;
    }
    if (event.shiftKey) {
      return;
    }
    event.preventDefault();
    if (!event.repeat) {
      submit();
    }
  };

  return (
    <main className="workspace" id="main-workspace">
      <header className="workspace-toolbar">
        <div>
          <p className="eyebrow">研究任务</p>
          <h1 data-page-title tabIndex={-1}>{isDraft ? "新任务" : detail?.name || "工作台"}</h1>
        </div>
        <div className="toolbar-actions">
          <button className="source-count" onClick={onOpenSources} type="button">
            {selectedSourceCount} 个已选来源
          </button>
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
        {isDraft ? (
          <WorkspaceState>这是一个新草稿。选择来源并输入问题后，首次发送才会保存任务。</WorkspaceState>
        ) : null}
        {!isDraft && !session ? (
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
        {detail && history.length === 0 && !visibleTask ? (
          <WorkspaceState>这个任务还没有消息。选择来源后即可提问。</WorkspaceState>
        ) : null}
        {history.map((message, index) => (
          <SavedMessage key={`${message.role}-${index}`} message={message} />
        ))}
        {visibleTask ? (
          <CurrentAnswer
            actionPending={answerActionPending}
            onCancel={onCancelAnswer}
            onOpenSettings={onOpenSettings}
            onRetry={onRetryAnswer}
            task={visibleTask}
          />
        ) : null}
      </section>

      <div className="composer-wrap">
        {answerActionError ? (
          <div className="answer-action-error" role="alert">
            <span>{answerActionError.message}</span>
            <small>
              错误代码：{answerActionError.code} · 请求 ID：
              {answerActionError.request_id}
            </small>
          </div>
        ) : null}
        {disabledReason ? (
          <div className="composer-notice" id="composer-notice" role="status">
            <span>{disabledReason}</span>
            {!queryReadiness.query_ready ? (
              <small>
                {queryReadiness.query_issue_code ?? "query_unavailable"} · 请求 ID：
                {queryReadiness.request_id}
              </small>
            ) : null}
            {!queryReadiness.query_ready &&
            ["configure_llm", "configure_credentials"].includes(
              queryReadiness.query_action,
            ) ? (
              <button onClick={onOpenSettings} type="button">配置模型</button>
            ) : null}
          </div>
        ) : null}
        <div className="context-row">
          <button className="context-chip" onClick={onOpenSources} type="button">
            <Icon name="files" size={14} />
            {selectedSourceCount} 个来源
          </button>
          <span className="context-model" title="模型由 MARA 本地配置提供">
            {modelName || "默认模型路由"}
          </span>
        </div>
        <div className={`composer${disabledReason ? " composer-disabled" : ""}`}>
          <label className="sr-only" htmlFor="task-input">向所选来源提问</label>
          <textarea
            aria-describedby={disabledReason ? "composer-notice composer-shortcut" : "composer-shortcut"}
            id="task-input"
            maxLength={20_000}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={handlePromptKeyDown}
            placeholder="向所选来源提问…"
            ref={inputRef}
            rows={2}
            value={prompt}
          />
          <div className="composer-footer">
            <button className="add-source" onClick={onOpenSources} type="button">
              <Icon name="add" size={16} />
              来源
            </button>
            <button
              aria-label="发送问题"
              className="send-button"
              disabled={!canSubmit}
              onClick={submit}
              title="Enter 发送；Alt+Enter 换行"
              type="button"
            >
              <Icon name="send" size={17} />
            </button>
          </div>
          <span className="sr-only" id="composer-shortcut">
            Enter 发送，Alt+Enter 换行，Ctrl 或 Command 加 Enter 也可发送。
          </span>
        </div>
      </div>
    </main>
  );
}

function SavedMessage({ message }: { message: SessionMessage }) {
  if (message.role === "user") {
    return (
      <div className="message user-message">
        <div className="message-label">你</div>
        <p>{message.content}</p>
      </div>
    );
  }
  return (
    <article className="message assistant-message">
      <AssistantHeading detail="已保存的回答" />
      <AssistantMarkdown content={message.content} />
    </article>
  );
}

function CurrentAnswer({
  actionPending,
  onCancel,
  onOpenSettings,
  onRetry,
  task,
}: {
  actionPending: boolean;
  onCancel: () => void;
  onOpenSettings: () => void;
  onRetry: () => void;
  task: QueryTask;
}) {
  const active = task.status === "queued" || task.status === "running";
  return (
    <div className="current-answer" aria-busy={active} aria-live="polite">
      <div className="message user-message">
        <div className="message-label">你</div>
        <p>{task.prompt}</p>
      </div>
      <article className={`message assistant-message answer-${task.status}`}>
        <AssistantHeading detail={answerStatus(task)} />
        {task.answer ? <AssistantMarkdown content={task.answer} /> : null}
        {active && !task.answer ? <p className="answer-placeholder">正在检索所选来源…</p> : null}
        {task.error ? (
          <div className="answer-error" role="alert">
            {task.status === "cancelled" ? "生成已停止。" : task.error.message}
            <p>{queryErrorAction(task.error.code)}</p>
            <small>错误代码：{task.error.code} · 任务 ID：{task.task_id}</small>
            {task.error.provider_request_id ? (
              <small>提供方请求 ID：{task.error.provider_request_id}</small>
            ) : null}
            {task.error.diagnostic ? (
              <small>诊断：{task.error.diagnostic}</small>
            ) : null}
          </div>
        ) : null}
        {task.citations.length > 0 ? <Citations citations={task.citations} /> : null}
        <div className="answer-actions">
          {active ? (
            <button disabled={actionPending} onClick={onCancel} type="button">
              {actionPending ? "正在停止…" : "停止"}
            </button>
          ) : null}
          {task.retryable ? (
            <button disabled={actionPending} onClick={onRetry} type="button">
              {actionPending ? "正在重试…" : "重试回答"}
            </button>
          ) : null}
          {task.error && queryErrorNeedsSettings(task.error.code) ? (
            <button disabled={actionPending} onClick={onOpenSettings} type="button">
              打开模型设置
            </button>
          ) : null}
        </div>
      </article>
    </div>
  );
}

function queryErrorNeedsSettings(code: string): boolean {
  return [
    "llm_model_not_found",
    "llm_model_unsupported",
    "llm_model_access_denied",
    "llm_authentication_failed",
    "llm_credentials_missing",
  ].includes(code);
}

function queryErrorAction(code: string): string {
  const actions: Record<string, string> = {
    llm_model_not_found: "请检查模型 ID 和提供方地址，然后重新保存设置。",
    llm_model_unsupported: "请在设置中选择该提供方支持的聊天模型。",
    llm_model_access_denied: "请确认当前账号拥有该模型的访问权限。",
    llm_authentication_failed: "请在设置中更新模型凭据。",
    llm_credentials_missing: "请在设置中补充模型凭据。",
    llm_rate_limited: "请稍后重试；无需重新安装 MARA。",
    llm_provider_unreachable: "请检查网络或本地模型服务后重试。",
    llm_dependency_missing: "当前安装缺少提供方依赖，请修复或重新安装 MARA。",
    query_storage_full: "请释放应用数据所在磁盘的空间，然后重试。",
    query_state_locked: "请关闭额外的 MARA 实例，然后重试。",
    query_state_permission_denied: "请检查 MARA 应用数据目录的写入权限，然后重试。",
    query_state_read_only: "请让 MARA 应用数据目录恢复可写，然后重试。",
    query_state_corrupt: "回答状态文件已保留，请先修复状态文件再继续。",
    query_persistence_failed: "请确认应用数据存储可用，然后重试。",
  };
  return actions[code] ?? "请记录任务 ID 后重试；若持续失败，请联系维护者。";
}

function AssistantHeading({ detail }: { detail: string }) {
  return (
    <div className="assistant-heading">
      <span className="assistant-mark" aria-hidden="true">M</span>
      <div>
        <div className="message-label">MARA</div>
        <small>{detail}</small>
      </div>
    </div>
  );
}

function Citations({ citations }: { citations: QueryCitation[] }) {
  return (
    <ol className="answer-citations" aria-label="回答引用">
      {citations.map((citation, index) => (
        <li key={citation.citation_id}>
          <span className="citation-number">{index + 1}</span>
          <div>
            <strong>{citation.file_name}</strong>
            <small>
              {citation.page_label ? `第 ${citation.page_label} 页` : "文件级证据"}
              {citation.element_id ? ` · ${citation.element_id}` : ""}
            </small>
            {citation.quote ? <blockquote>{citation.quote}</blockquote> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

function messagesBeforeVisibleTask(
  detail: SessionDetail | undefined,
  task: QueryTask | undefined,
): SessionMessage[] {
  if (!detail || !task || detail.messages.length < 2 || !task.answer) {
    return detail?.messages ?? [];
  }
  const user = detail.messages.at(-2);
  const assistant = detail.messages.at(-1);
  return user?.role === "user" &&
    user.content === task.prompt &&
    assistant?.role === "assistant" &&
    assistant.content === task.answer
    ? detail.messages.slice(0, -2)
    : detail.messages;
}

function composerDisabledReason(
  isDraft: boolean,
  session: ResourceState<SessionDetail> | undefined,
  detail: SessionDetail | undefined,
  selectedSourceCount: number,
  queryReadiness: QueryReadiness,
  active: boolean,
  backgroundActive: boolean,
  actionPending: boolean,
): string | undefined {
  if (!isDraft && session?.status === "loading") {
    return "正在读取任务；你可以先编辑问题。";
  }
  if (!isDraft && !detail) {
    return "先选择或新建任务。";
  }
  if (!queryReadiness.query_ready) {
    return queryReadiness.query_message;
  }
  if (selectedSourceCount === 0) {
    return "请先在 Sources 中选择来源。";
  }
  if (actionPending) {
    return "正在处理回答操作…";
  }
  if (active) {
    return "当前回答仍在生成；可先停止，再提交新问题。";
  }
  if (backgroundActive) {
    return "另一个任务的回答仍在生成；请返回该任务停止或等待完成。";
  }
  return undefined;
}

function answerStatus(task: QueryTask): string {
  if (task.status === "queued") {
    return "正在排队";
  }
  if (task.status === "running") {
    return "正在生成";
  }
  if (task.status === "success") {
    return "回答已保存";
  }
  if (task.status === "cancelled") {
    return task.answer ? "生成已停止，内容未完成" : "生成已停止";
  }
  if (task.stage === "storage_error" && task.answer) {
    return "部分回答未安全保存";
  }
  return task.answer ? "回答未完成" : "生成失败";
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

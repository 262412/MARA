import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import type {
  QueryCitation,
  QueryPersistenceDiagnostic,
  QueryTask,
  QueryTaskError,
} from "../../shared/query-contracts";
import type { DoctorPayload } from "../../shared/doctor-contracts";
import type { SidecarError } from "../../shared/runtime-contracts";
import { useLanguage, type Translate } from "../i18n";
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
  const { t } = useLanguage();
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
    t,
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
        if (window.confirm(t("workspace.answerStopConfirm"))) {
          onCancelAnswer();
        }
      }
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [active, onCancelAnswer, t]);

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
          <p className="eyebrow">{t("workspace.researchTask")}</p>
          <h1 data-page-title tabIndex={-1}>
            {isDraft ? t("workspace.newTask") : detail?.name || t("workspace.workbench")}
          </h1>
        </div>
        <div className="toolbar-actions">
          <button className="source-count" onClick={onOpenSources} type="button">
            {t("workspace.selectedSources", { count: selectedSourceCount })}
          </button>
          <button
            aria-label={t("workspace.toggleInspector")}
            className="icon-button"
            onClick={onToggleInspector}
            type="button"
          >
            <Icon name="panel" />
          </button>
        </div>
      </header>

      <section className="conversation" aria-label={t("workspace.conversation")}>
        {isDraft ? (
          <WorkspaceState>{t("workspace.draftState")}</WorkspaceState>
        ) : null}
        {!isDraft && !session ? (
          <WorkspaceState>{t("workspace.selectTask")}</WorkspaceState>
        ) : null}
        {session?.status === "loading" ? (
          <WorkspaceState>{t("workspace.loadingSession")}</WorkspaceState>
        ) : null}
        {session?.status === "failed" ? (
          <WorkspaceState role="alert">
            <span>{session.message}</span>
            <button onClick={onRetrySession} type="button">{t("common.retry")}</button>
          </WorkspaceState>
        ) : null}
        {detail && history.length === 0 && !visibleTask ? (
          <WorkspaceState>{t("workspace.emptySession")}</WorkspaceState>
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
            <span>{queryActionErrorAction(answerActionError, t)}</span>
            <small>
              {t("workspace.errorCodeRequest", {
                code: answerActionError.code,
                id: answerActionError.request_id,
              })}
            </small>
          </div>
        ) : null}
        {disabledReason ? (
          <div className="composer-notice" id="composer-notice" role="status">
            <span>{disabledReason}</span>
            {!queryReadiness.query_ready ? (
              <small>
                {t("workspace.queryCodeRequest", {
                  code: queryReadiness.query_issue_code ?? "query_unavailable",
                  id: queryReadiness.request_id,
                })}
              </small>
            ) : null}
            {!queryReadiness.query_ready &&
            ["configure_llm", "configure_credentials"].includes(
              queryReadiness.query_action,
            ) ? (
              <button onClick={onOpenSettings} type="button">
                {t("common.configureModel")}
              </button>
            ) : null}
          </div>
        ) : null}
        <div className="context-row">
          <button className="context-chip" onClick={onOpenSources} type="button">
            <Icon name="files" size={14} />
            {t("common.sourceCount", { count: selectedSourceCount })}
          </button>
          <span className="context-model" title={t("workspace.modelProvidedLocally")}>
            {modelName || t("common.defaultModelRoute")}
          </span>
        </div>
        <div className={`composer${disabledReason ? " composer-disabled" : ""}`}>
          <label className="sr-only" htmlFor="task-input">
            {t("workspace.askSelectedSources")}
          </label>
          <textarea
            aria-describedby={disabledReason ? "composer-notice composer-shortcut" : "composer-shortcut"}
            id="task-input"
            maxLength={20_000}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={handlePromptKeyDown}
            placeholder={t("workspace.askPlaceholder")}
            ref={inputRef}
            rows={2}
            value={prompt}
          />
          <div className="composer-footer">
            <button className="add-source" onClick={onOpenSources} type="button">
              <Icon name="add" size={16} />
              {t("workspace.sources")}
            </button>
            <button
              aria-label={t("workspace.sendQuestion")}
              className="send-button"
              disabled={!canSubmit}
              onClick={submit}
              title={t("workspace.sendShortcutTitle")}
              type="button"
            >
              <Icon name="send" size={17} />
            </button>
          </div>
          <span className="sr-only" id="composer-shortcut">
            {t("workspace.sendShortcut")}
          </span>
        </div>
      </div>
    </main>
  );
}

function SavedMessage({ message }: { message: SessionMessage }) {
  const { t } = useLanguage();
  if (message.role === "user") {
    return (
      <div className="message user-message">
        <div className="message-label">{t("workspace.you")}</div>
        <p>{message.content}</p>
      </div>
    );
  }
  return (
    <article className="message assistant-message">
      <AssistantHeading detail={t("workspace.savedAnswer")} />
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
  const { t } = useLanguage();
  const active = task.status === "queued" || task.status === "running";
  return (
    <div className="current-answer" aria-busy={active} aria-live="polite">
      <div className="message user-message">
        <div className="message-label">{t("workspace.you")}</div>
        <p>{task.prompt}</p>
      </div>
      <article className={`message assistant-message answer-${task.status}`}>
        <AssistantHeading detail={answerStatus(task, t)} />
        {task.answer ? <AssistantMarkdown content={task.answer} /> : null}
        {active && !task.answer ? (
          <p className="answer-placeholder">{t("workspace.searchingSources")}</p>
        ) : null}
        {task.error ? (
          <div className="answer-error" role="alert">
            {task.status === "cancelled"
              ? t("workspace.answerStopped")
              : task.error.message}
            <p>{queryErrorAction(task.error, t)}</p>
            {task.answer && !task.answer_saved ? (
              <p>{t("workspace.partialAnswerNotSaved")}</p>
            ) : null}
            <small>
              {t("common.errorCode", { code: task.error.code })} · {t("common.taskId", { id: task.task_id })}
            </small>
            {task.error.provider_request_id ? (
              <small>
                {t("common.providerRequestId", {
                  id: task.error.provider_request_id,
                })}
              </small>
            ) : null}
            {task.error.diagnostic ? (
              <small>{t("common.diagnostic", { value: task.error.diagnostic })}</small>
            ) : null}
          </div>
        ) : null}
        {task.citations.length > 0 ? <Citations citations={task.citations} /> : null}
        <div className="answer-actions">
          {active ? (
            <button disabled={actionPending} onClick={onCancel} type="button">
              {actionPending ? t("workspace.stopping") : t("workspace.stop")}
            </button>
          ) : null}
          {task.retryable ? (
            <button disabled={actionPending} onClick={onRetry} type="button">
              {actionPending
                ? t("workspace.retrying")
                : t("workspace.retryAnswer")}
            </button>
          ) : null}
          {task.error && queryErrorNeedsSettings(task.error.code) ? (
            <button disabled={actionPending} onClick={onOpenSettings} type="button">
              {t("workspace.openModelSettings")}
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

function queryErrorAction(error: QueryTaskError, t: Translate): string {
  const persistenceAction = persistenceErrorAction(error.persistence, t);
  if (persistenceAction) {
    return persistenceAction;
  }
  const actions: Record<string, string> = {
    llm_model_not_found: t("workspace.queryActionModelNotFound"),
    llm_model_unsupported: t("workspace.queryActionModelUnsupported"),
    llm_model_access_denied: t("workspace.queryActionAccessDenied"),
    llm_authentication_failed: t("workspace.queryActionAuthFailed"),
    llm_credentials_missing: t("workspace.queryActionCredentialsMissing"),
    llm_rate_limited: t("workspace.queryActionRateLimited"),
    llm_provider_unreachable: t("workspace.queryActionProviderUnreachable"),
    llm_dependency_missing: t("workspace.queryActionDependencyMissing"),
    query_storage_full: t("workspace.queryActionStorageFull"),
    query_state_locked: t("workspace.queryActionLocked"),
    query_state_permission_denied: t("workspace.queryActionPermission"),
    query_state_replace_blocked: t("workspace.queryActionReplaceBlocked"),
    query_state_read_only: t("workspace.queryActionReadOnly"),
    query_state_corrupt: t("workspace.queryActionCorrupt"),
    query_persistence_failed: t("workspace.queryActionPersistence"),
  };
  return actions[error.code] ?? t("workspace.queryActionDefault");
}

function queryActionErrorAction(error: SidecarError, t: Translate): string {
  return queryErrorAction({
    code: error.code,
    message: error.message,
    retryable: error.retryable,
    persistence: persistenceDiagnosticFromDetails(error.details),
  }, t);
}

function persistenceErrorAction(
  persistence: QueryPersistenceDiagnostic | null | undefined,
  t: Translate,
): string | undefined {
  if (persistence?.smoke_mode) {
    return t("workspace.persistenceSmoke");
  }
  if (persistence?.operation === "write_temp") {
    return t("workspace.persistenceWrite");
  }
  if (
    persistence?.operation === "atomic_replace" &&
    persistence.post_failure_probe === "write_blocked"
  ) {
    return t("workspace.persistenceReplaceProbe");
  }
  if (persistence?.operation === "atomic_replace") {
    return t("workspace.persistenceReplace");
  }
  if (persistence?.operation === "flush") {
    return t("workspace.persistenceFlush");
  }
  return undefined;
}

function persistenceDiagnosticFromDetails(
  details: unknown,
): QueryPersistenceDiagnostic | undefined {
  if (!details || typeof details !== "object" || !("persistence" in details)) {
    return undefined;
  }
  const persistence = details.persistence;
  if (!persistence || typeof persistence !== "object") {
    return undefined;
  }
  const candidate = persistence as Partial<QueryPersistenceDiagnostic>;
  const operations = ["write_temp", "flush", "atomic_replace", "load", "unknown"];
  const probes = [
    "not_run",
    "ready",
    "write_blocked",
    "replace_blocked",
    "flush_blocked",
  ];
  if (
    !operations.includes(candidate.operation ?? "") ||
    !probes.includes(candidate.post_failure_probe ?? "") ||
    typeof candidate.retry_count !== "number" ||
    typeof candidate.smoke_mode !== "boolean" ||
    typeof candidate.fingerprint !== "string"
  ) {
    return undefined;
  }
  return candidate as QueryPersistenceDiagnostic;
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
  const { t } = useLanguage();
  return (
    <ol className="answer-citations" aria-label={t("workspace.citations")}>
      {citations.map((citation, index) => (
        <li key={citation.citation_id}>
          <span className="citation-number">{index + 1}</span>
          <div>
            <strong>{citation.file_name}</strong>
            <small>
              {citation.page_label
                ? t("workspace.page", { page: citation.page_label })
                : t("workspace.fileEvidence")}
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
  t: Translate,
): string | undefined {
  if (!isDraft && session?.status === "loading") {
    return t("workspace.loadingTaskEditable");
  }
  if (!isDraft && !detail) {
    return t("workspace.selectOrCreateTask");
  }
  if (!queryReadiness.query_ready) {
    return queryReadiness.query_message;
  }
  if (selectedSourceCount === 0) {
    return t("workspace.selectSourcesFirst");
  }
  if (actionPending) {
    return t("workspace.answerActionPending");
  }
  if (active) {
    return t("workspace.answerStillGenerating");
  }
  if (backgroundActive) {
    return t("workspace.backgroundAnswerGenerating");
  }
  return undefined;
}

function answerStatus(task: QueryTask, t: Translate): string {
  if (task.status === "queued") {
    return t("workspace.statusQueued");
  }
  if (task.status === "running") {
    return t("workspace.statusRunning");
  }
  if (task.status === "success") {
    return t("workspace.statusSuccess");
  }
  if (task.status === "cancelled") {
    return task.answer
      ? t("workspace.statusCancelledWithAnswer")
      : t("workspace.statusCancelled");
  }
  if (task.stage === "storage_error" && task.answer) {
    return t("workspace.statusPartialNotSaved");
  }
  return task.answer
    ? t("workspace.statusIncomplete")
    : t("workspace.statusFailed");
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

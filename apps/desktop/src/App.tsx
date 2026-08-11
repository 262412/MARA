import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import type { FileRecord } from "../shared/file-contracts";
import type { DoctorPayload } from "../shared/doctor-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
import type {
  ModelSettingsInput,
  ModelSettingsStatus,
} from "../shared/model-contracts";
import type { QueryTask } from "../shared/query-contracts";
import type {
  DesktopResult,
  RuntimeStatus,
  SidecarError,
} from "../shared/runtime-contracts";
import type {
  SessionDetail,
  SessionSummary,
} from "../shared/session-contracts";
import { FilesPage } from "./components/FilesPage";
import { HelpPage } from "./components/HelpPage";
import { Inspector, type InspectorTab } from "./components/Inspector";
import { ResourcesPage } from "./components/ResourcesPage";
import { SettingsPage } from "./components/SettingsPage";
import { Sidebar } from "./components/Sidebar";
import { Workspace } from "./components/Workspace";
import { refreshFilesForTerminalTask } from "./index-task-state";
import { mergeQueryTaskSnapshot } from "./query-task-state";
import { PAGE_TITLES, type AppPage } from "./navigation";
import type { ResourceState } from "./resource-state";
import { useDesktopResource } from "./useDesktopResource";

const unavailableRuntime: RuntimeStatus = {
  state: "failed",
  protocol: 1,
  capabilities: [],
  message: "Desktop bridge 不可用。",
};

export default function App() {
  const [activeNav, setActiveNav] = useState<AppPage>("workbench");
  const draftGeneration = useRef(0);
  const [workspaceId, setWorkspaceId] = useState("draft:0");
  const [composerPrompt, setComposerPrompt] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState<string>();
  const [selectedSession, setSelectedSession] = useState<
    ResourceState<SessionDetail> | undefined
  >();
  const [sessionReload, setSessionReload] = useState(0);
  const [sessionSearchQuery, setSessionSearchQuery] = useState("");
  const [editingSessionId, setEditingSessionId] = useState<string>();
  const [editingSessionName, setEditingSessionName] = useState("");
  const [sessionAction, setSessionAction] = useState<
    { conversationId: string; action: "rename" | "delete" } | undefined
  >();
  const [sessionActionError, setSessionActionError] = useState<string>();
  const [sessionCreatePending, setSessionCreatePending] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("preview");
  const [indexTask, setIndexTask] = useState<IndexTask>();
  const [answerTask, setAnswerTask] = useState<QueryTask>();
  const [answerActionPending, setAnswerActionPending] = useState(false);
  const [answerActionError, setAnswerActionError] = useState<SidecarError>();
  const [modelSettingsSavePending, setModelSettingsSavePending] = useState(false);
  const [modelSettingsSaveError, setModelSettingsSaveError] = useState<SidecarError>();
  const [indexActionPending, setIndexActionPending] = useState(false);
  const [deletingFileIds, setDeletingFileIds] = useState<string[]>([]);
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [fileActionError, setFileActionError] = useState<SidecarError>();
  const lastTaskRefresh = useRef<string | undefined>(undefined);
  const lastAnswerRefresh = useRef<string | undefined>(undefined);
  const fileDeletionLock = useRef(false);
  const indexActionLock = useRef(false);
  const sessionRequestGeneration = useRef(0);
  const sessionMutationLock = useRef(false);
  const sessionCreateLock = useRef(false);
  const answerActionLock = useRef(false);
  const modelSettingsSaveLock = useRef(false);
  const sourceSelectionSession = useRef<string | undefined>(undefined);
  const [runtime, setRuntime] = useState<RuntimeStatus>(
    window.desktop
      ? { state: "starting", protocol: 1, capabilities: [] }
      : unavailableRuntime,
  );
  const loadDoctor = useCallback(
    () =>
      window.desktop?.getDoctor() ??
      unavailableResult("Doctor 仅能在 MARA Desktop 中使用。"),
    [],
  );
  const loadFiles = useCallback(
    () =>
      window.desktop?.listFiles() ??
      unavailableResult("Files 仅能在 MARA Desktop 中使用。"),
    [],
  );
  const loadSessions = useCallback(
    () =>
      window.desktop?.listSessions() ??
      unavailableResult("Sessions 仅能在 MARA Desktop 中使用。"),
    [],
  );
  const loadModelSettings = useCallback(
    () =>
      window.desktop?.getModelSettings() ??
      unavailableResult<ModelSettingsStatus>(
        "模型设置仅能在 MARA Desktop 中使用。",
      ),
    [],
  );
  const doctor = useDesktopResource(loadDoctor);
  const files = useDesktopResource(loadFiles);
  const sessions = useDesktopResource(loadSessions);
  const modelSettings = useDesktopResource(loadModelSettings);
  const indexing = indexingReadiness(doctor.resource);
  const querying = queryReadiness(doctor.resource);

  useEffect(() => {
    document.title = `${PAGE_TITLES[activeNav]} · MARA`;
    document.querySelector<HTMLElement>("[data-page-title]")?.focus();
  }, [activeNav]);

  useEffect(() => {
    const generation = ++sessionRequestGeneration.current;
    if (!selectedSessionId) {
      setSelectedSession(undefined);
      return;
    }
    setSelectedSession({ status: "loading" });
    void (async () => {
      let result: DesktopResult<SessionDetail>;
      try {
        result = await (
          window.desktop?.getSession(selectedSessionId) ??
          unavailableResult<SessionDetail>(
            "会话详情仅能在 MARA Desktop 中使用。",
          )
        );
      } catch {
        result = await unavailableResult<SessionDetail>("会话读取未能完成。");
      }
      if (generation !== sessionRequestGeneration.current) {
        return;
      }
      setSelectedSession(
        result.ok
          ? { status: "success", data: result.data }
          : {
              status: "failed",
              message: result.error.message,
              error: result.error,
            },
      );
    })();
    return () => {
      if (generation === sessionRequestGeneration.current) {
        sessionRequestGeneration.current += 1;
      }
    };
  }, [selectedSessionId, sessionReload]);
  const updateIndexTask = useCallback(
    (task: IndexTask) => {
      setIndexTask(task);
      lastTaskRefresh.current = refreshFilesForTerminalTask(
        task,
        lastTaskRefresh.current,
        files.retry,
      );
    },
    [files.retry],
  );
  const updateAnswerTask = useCallback(
    (task: QueryTask, replace = false) => {
      setAnswerTask((current) =>
        mergeQueryTaskSnapshot(current, task, replace),
      );
    },
    [],
  );

  useEffect(() => {
    if (answerTask?.status !== "success") {
      return;
    }
    const refreshKey = `${answerTask.task_id}:${answerTask.version}`;
    if (lastAnswerRefresh.current === refreshKey) {
      return;
    }
    lastAnswerRefresh.current = refreshKey;
    sessions.retry();
    if (answerTask.conversation_id === selectedSessionId) {
      setSessionReload((value) => value + 1);
    }
  }, [answerTask, selectedSessionId, sessions.retry]);

  useEffect(() => {
    if (!window.desktop) {
      return;
    }
    void window.desktop
      .getRuntimeStatus()
      .then(setRuntime)
      .catch(() => setRuntime(unavailableRuntime));
    void window.desktop.getLatestIndexTask().then((result) => {
      if (result.ok && result.data) {
        updateIndexTask(result.data);
      }
    });
    void window.desktop.getLatestAnswerTask().then((result) => {
      if (result.ok && result.data) {
        updateAnswerTask(result.data);
      }
    });
    const removeRuntimeListener = window.desktop.onRuntimeStatus(setRuntime);
    const removeTaskListener = window.desktop.onIndexTaskStatus(updateIndexTask);
    const removeAnswerListener = window.desktop.onAnswerTaskStatus(updateAnswerTask);
    return () => {
      removeRuntimeListener();
      removeTaskListener();
      removeAnswerListener();
    };
  }, [updateAnswerTask, updateIndexTask]);

  const runFileImport = useCallback(
    async (
      operation: () => Promise<DesktopResult<IndexTask | null>>,
      failureCode: string,
      failureMessage: string,
    ) => {
      if (!indexing.indexing_ready || indexActionLock.current) {
        return;
      }
      indexActionLock.current = true;
      setIndexActionPending(true);
      setFileActionError(undefined);
      try {
        const result = await operation();
        if (!result.ok) {
          setFileActionError(result.error);
        } else if (result.data) {
          updateIndexTask(result.data);
        }
      } catch {
        setFileActionError(rendererSidecarError(failureCode, failureMessage));
      } finally {
        indexActionLock.current = false;
        setIndexActionPending(false);
      }
    },
    [indexing.indexing_ready, updateIndexTask],
  );

  const importFiles = useCallback(
    () =>
      runFileImport(
        () =>
          window.desktop?.importFiles() ??
          unavailableResult<IndexTask | null>(
            "文件导入仅能在 MARA Desktop 中使用。",
          ),
        "file_import_failed",
        "文件导入未能完成。",
      ),
    [runFileImport],
  );

  const importDroppedFiles = useCallback(
    (droppedFiles: File[]) =>
      runFileImport(
        () =>
          window.desktop?.importDroppedFiles(droppedFiles) ??
          unavailableResult<IndexTask>(
            "文件拖放仅能在 MARA Desktop 中使用。",
          ),
        "file_drop_failed",
        "拖放文件未能导入。",
      ),
    [runFileImport],
  );

  const cancelIndexTask = useCallback(async () => {
    if (!indexTask) {
      return;
    }
    if (indexActionLock.current) {
      return;
    }
    indexActionLock.current = true;
    setIndexActionPending(true);
    setFileActionError(undefined);
    try {
      const result = await (
        window.desktop?.cancelIndexTask(indexTask.task_id) ??
        unavailableResult<IndexTask>("索引任务仅能在 MARA Desktop 中管理。")
      );
      if (result.ok) {
        updateIndexTask(result.data);
      } else {
        setFileActionError(result.error);
      }
    } catch {
      setFileActionError(
        rendererSidecarError("index_cancel_failed", "取消索引未能完成。"),
      );
    } finally {
      indexActionLock.current = false;
      setIndexActionPending(false);
    }
  }, [indexTask, updateIndexTask]);

  const retryIndexTask = useCallback(async () => {
    if (!indexTask) {
      return;
    }
    if (indexActionLock.current) {
      return;
    }
    indexActionLock.current = true;
    setIndexActionPending(true);
    setFileActionError(undefined);
    try {
      const result = await (
        window.desktop?.retryIndexTask(indexTask.task_id) ??
        unavailableResult<IndexTask>("索引任务仅能在 MARA Desktop 中管理。")
      );
      if (result.ok) {
        updateIndexTask(result.data);
      } else {
        setFileActionError(result.error);
      }
    } catch {
      setFileActionError(
        rendererSidecarError("index_retry_failed", "重试索引未能完成。"),
      );
    } finally {
      indexActionLock.current = false;
      setIndexActionPending(false);
    }
  }, [indexTask, updateIndexTask]);

  const deleteFiles = useCallback(
    async (targets: FileRecord[]) => {
      if (targets.length === 0) {
        return;
      }
      if (fileDeletionLock.current) {
        return;
      }
      const confirmation =
        targets.length === 1
          ? `删除“${targets[0].name || "未命名文件"}”的索引和受管副本？`
          : `删除选中的 ${targets.length} 个文件索引和受管副本？此操作不可撤销。`;
      if (!window.confirm(confirmation)) {
        return;
      }
      fileDeletionLock.current = true;
      const fileIds = targets.map((file) => file.file_id);
      setDeletingFileIds(fileIds);
      setFileActionError(undefined);
      try {
        const result = await (
          window.desktop?.deleteFiles(fileIds) ??
          unavailableResult<string[]>("文件删除仅能在 MARA Desktop 中使用。")
        );
        if (result.ok) {
          setSelectedFileIds((selected) =>
            selected.filter((fileId) => !result.data.includes(fileId)),
          );
          setSelectedSourceIds((selected) =>
            selected.filter((fileId) => !result.data.includes(fileId)),
          );
          files.retry();
        } else {
          setFileActionError(result.error);
          files.retry();
        }
      } catch {
        setFileActionError(
          rendererSidecarError("file_delete_failed", "文件删除未能完成。"),
        );
        files.retry();
      } finally {
        fileDeletionLock.current = false;
        setDeletingFileIds([]);
      }
    },
    [files.retry],
  );

  useEffect(() => {
    if (files.resource.status !== "success") {
      return;
    }
    const availableIds = new Set(
      files.resource.data.map((file) => file.file_id),
    );
    setSelectedFileIds((selected) =>
      selected.filter((fileId) => availableIds.has(fileId)),
    );
    setSelectedSourceIds((selected) =>
      selected.filter((fileId) => availableIds.has(fileId)),
    );
  }, [files.resource]);

  useEffect(() => {
    if (
      selectedSession?.status !== "success" ||
      files.resource.status !== "success" ||
      sourceSelectionSession.current === selectedSession.data.conversation_id
    ) {
      return;
    }
    const availableIds = new Set(
      files.resource.data.map((file) => file.file_id),
    );
    setSelectedSourceIds(
      selectedSession.data.graph_source_ids.filter((fileId) =>
        availableIds.has(fileId),
      ),
    );
    sourceSelectionSession.current = selectedSession.data.conversation_id;
  }, [files.resource, selectedSession]);

  const toggleSource = useCallback((fileId: string) => {
    setSelectedSourceIds((selected) =>
      selected.includes(fileId)
        ? selected.filter((candidate) => candidate !== fileId)
        : [...selected, fileId],
    );
  }, []);

  const submitQuestion = useCallback(
    async (prompt: string) => {
      if (
        selectedSourceIds.length === 0 ||
        !querying.query_ready ||
        answerActionLock.current ||
        answerTask?.status === "queued" ||
        answerTask?.status === "running"
      ) {
        return;
      }
      answerActionLock.current = true;
      setAnswerActionPending(true);
      setAnswerActionError(undefined);
      try {
        let conversationId = selectedSessionId;
        if (!conversationId) {
          if (sessionCreateLock.current || sessionMutationLock.current) {
            return;
          }
          sessionCreateLock.current = true;
          setSessionCreatePending(true);
          const created = await (
            window.desktop?.createSession() ??
            unavailableResult<SessionDetail>(
              "新建任务仅能在 MARA Desktop 中使用。",
            )
          );
          if (!created.ok) {
            setAnswerActionError(created.error);
            return;
          }
          conversationId = created.data.conversation_id;
          sourceSelectionSession.current = conversationId;
          setSelectedSession({ status: "success", data: created.data });
          setSelectedSessionId(conversationId);
          sessions.retry();
        }
        const result = await (
          window.desktop?.submitQuestion({
            conversation_id: conversationId,
            prompt,
            selected_file_ids: selectedSourceIds,
          }) ?? unavailableResult<QueryTask>("问答仅能在 MARA Desktop 中使用。")
        );
        if (result.ok) {
          updateAnswerTask(result.data, true);
        } else {
          setAnswerActionError(result.error);
        }
      } catch {
        setAnswerActionError(
          rendererSidecarError("query_submit_failed", "问题未能提交。"),
        );
      } finally {
        sessionCreateLock.current = false;
        setSessionCreatePending(false);
        answerActionLock.current = false;
        setAnswerActionPending(false);
      }
    },
    [
      answerTask?.status,
      querying.query_ready,
      selectedSessionId,
      selectedSourceIds,
      sessions.retry,
      updateAnswerTask,
    ],
  );

  const cancelAnswer = useCallback(async () => {
    if (!answerTask || answerActionLock.current) {
      return;
    }
    answerActionLock.current = true;
    setAnswerActionPending(true);
    setAnswerActionError(undefined);
    try {
      const result = await (
        window.desktop?.cancelAnswer(answerTask.task_id) ??
        unavailableResult<QueryTask>("回答任务仅能在 MARA Desktop 中管理。")
      );
      if (result.ok) {
        updateAnswerTask(result.data);
      } else {
        setAnswerActionError(result.error);
      }
    } catch {
      setAnswerActionError(
        rendererSidecarError("query_cancel_failed", "停止回答未能完成。"),
      );
    } finally {
      answerActionLock.current = false;
      setAnswerActionPending(false);
    }
  }, [answerTask, updateAnswerTask]);

  const retryAnswer = useCallback(async () => {
    if (!answerTask || answerActionLock.current) {
      return;
    }
    answerActionLock.current = true;
    setAnswerActionPending(true);
    setAnswerActionError(undefined);
    try {
      const result = await (
        window.desktop?.retryAnswer(answerTask.task_id) ??
        unavailableResult<QueryTask>("回答任务仅能在 MARA Desktop 中管理。")
      );
      if (result.ok) {
        updateAnswerTask(result.data, true);
      } else {
        setAnswerActionError(result.error);
      }
    } catch {
      setAnswerActionError(
        rendererSidecarError("query_retry_failed", "重试回答未能完成。"),
      );
    } finally {
      answerActionLock.current = false;
      setAnswerActionPending(false);
    }
  }, [answerTask, updateAnswerTask]);

  const startDraft = useCallback(() => {
    if (sessionCreateLock.current || sessionMutationLock.current) {
      return;
    }
    draftGeneration.current += 1;
    setWorkspaceId(`draft:${draftGeneration.current}`);
    setActiveNav("workbench");
    setSelectedSessionId(undefined);
    setSelectedSession(undefined);
    setComposerPrompt("");
    setSessionSearchQuery("");
    setSelectedSourceIds([]);
    sourceSelectionSession.current = undefined;
    setAnswerActionError(undefined);
    setSessionActionError(undefined);
  }, []);

  const saveModelSettings = useCallback(
    async (settings: ModelSettingsInput) => {
      if (modelSettingsSaveLock.current) {
        return;
      }
      modelSettingsSaveLock.current = true;
      setModelSettingsSavePending(true);
      setModelSettingsSaveError(undefined);
      try {
        const result = await (
          window.desktop?.saveModelSettings(settings) ??
          unavailableResult<ModelSettingsStatus>(
            "模型设置仅能在 MARA Desktop 中保存。",
          )
        );
        if (!result.ok) {
          setModelSettingsSaveError(result.error);
          return;
        }
        modelSettings.retry();
        doctor.retry();
      } catch {
        setModelSettingsSaveError(
          rendererSidecarError(
            "model_settings_apply_failed",
            "模型设置未能保存并应用。",
          ),
        );
      } finally {
        modelSettingsSaveLock.current = false;
        setModelSettingsSavePending(false);
      }
    },
    [doctor.retry, modelSettings.retry],
  );

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "o") {
        event.preventDefault();
        void importFiles();
      } else if (
        (event.ctrlKey || event.metaKey) &&
        event.key.toLowerCase() === "n"
      ) {
        event.preventDefault();
        startDraft();
      } else if (
        (event.ctrlKey || event.metaKey) &&
        event.key === ","
      ) {
        event.preventDefault();
        setActiveNav("settings");
      }
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [importFiles, startDraft]);

  const selectSession = useCallback((sessionId: string) => {
    setActiveNav("workbench");
    setSelectedSessionId(sessionId);
    setWorkspaceId(`session:${sessionId}`);
    setComposerPrompt("");
    sourceSelectionSession.current = undefined;
    setAnswerActionError(undefined);
    setSessionActionError(undefined);
  }, []);

  const startSessionRename = useCallback((session: SessionSummary) => {
    setEditingSessionId(session.conversation_id);
    setEditingSessionName(session.name || "未命名任务");
    setSessionActionError(undefined);
  }, []);

  const cancelSessionRename = useCallback(() => {
    if (sessionMutationLock.current) {
      return;
    }
    setEditingSessionId(undefined);
    setEditingSessionName("");
    setSessionActionError(undefined);
  }, []);

  const renameSession = useCallback(
    async (conversationId: string, rawName: string) => {
      const name = rawName.trim();
      if (
        sessionMutationLock.current ||
        sessionCreateLock.current ||
        name.length === 0 ||
        Array.from(name).length > 200
      ) {
        return;
      }
      sessionMutationLock.current = true;
      setSessionAction({ conversationId, action: "rename" });
      setSessionActionError(undefined);
      try {
        const result = await (
          window.desktop?.renameSession(conversationId, name) ??
          unavailableResult<SessionDetail>(
            "会话重命名仅能在 MARA Desktop 中使用。",
          )
        );
        if (result.ok) {
          if (selectedSessionId === conversationId) {
            setSelectedSession({ status: "success", data: result.data });
          }
          setEditingSessionId(undefined);
          setEditingSessionName("");
          sessions.retry();
        } else {
          setSessionActionError(result.error.message);
        }
      } catch {
        setSessionActionError("会话重命名未能完成。");
      } finally {
        sessionMutationLock.current = false;
        setSessionAction(undefined);
      }
    },
    [selectedSessionId, sessions.retry],
  );

  const deleteSession = useCallback(
    async (session: SessionSummary) => {
      if (sessionMutationLock.current || sessionCreateLock.current) {
        return;
      }
      const name = session.name || "未命名任务";
      if (
        !window.confirm(
          `删除“${name}”会永久删除该会话及其消息记录；此操作不可撤销。`,
        )
      ) {
        return;
      }
      const conversationId = session.conversation_id;
      sessionMutationLock.current = true;
      setSessionAction({ conversationId, action: "delete" });
      setSessionActionError(undefined);
      try {
        const result = await (
          window.desktop?.deleteSession(conversationId) ??
          unavailableResult<string>("会话删除仅能在 MARA Desktop 中使用。")
        );
        if (result.ok) {
          if (selectedSessionId === conversationId) {
            draftGeneration.current += 1;
            setWorkspaceId(`draft:${draftGeneration.current}`);
            setSelectedSessionId(undefined);
            setSelectedSession(undefined);
            setComposerPrompt("");
            setSelectedSourceIds([]);
            sourceSelectionSession.current = undefined;
            if (answerTask?.conversation_id === conversationId) {
              setAnswerTask(undefined);
            }
          }
          if (editingSessionId === conversationId) {
            setEditingSessionId(undefined);
            setEditingSessionName("");
          }
          sessions.retry();
        } else {
          setSessionActionError(result.error.message);
          sessions.retry();
        }
      } catch {
        setSessionActionError("会话删除未能完成。");
        sessions.retry();
      } finally {
        sessionMutationLock.current = false;
        setSessionAction(undefined);
      }
    },
    [answerTask?.conversation_id, editingSessionId, selectedSessionId, sessions.retry],
  );

  return (
    <>
      <a className="skip-link" href="#main-workspace">跳到主工作区</a>
      <div className="app-shell">
        <Sidebar
          active={activeNav}
          onNavigate={setActiveNav}
          onRetrySessions={sessions.retry}
          onSelectSession={selectSession}
          onSearchQueryChange={setSessionSearchQuery}
          searchQuery={sessionSearchQuery}
          editingSessionId={editingSessionId}
          editingSessionName={editingSessionName}
          onStartRename={startSessionRename}
          onEditingSessionNameChange={setEditingSessionName}
          onCancelRename={cancelSessionRename}
          onCreateSession={startDraft}
          onRenameSession={(conversationId, name) =>
            void renameSession(conversationId, name)
          }
          onDeleteSession={(session) => void deleteSession(session)}
          sessionAction={sessionAction}
          sessionActionError={sessionActionError}
          sessionCreatePending={sessionCreatePending}
          selectedSessionId={selectedSessionId}
          sessions={sessions.resource}
        />
        {activeNav === "files" ? (
          <FilesPage
            actionError={fileActionError}
            deletingFileIds={deletingFileIds}
            files={files.resource}
            indexing={indexing}
            indexActionPending={
              indexActionPending || deletingFileIds.length > 0
            }
            indexTask={indexTask}
            onCancelIndexTask={() => void cancelIndexTask()}
            onDelete={(targets) => void deleteFiles(targets)}
            onDropFiles={(droppedFiles) =>
              void importDroppedFiles(droppedFiles)
            }
            onImport={() => void importFiles()}
            onOpenEmbeddingConfiguration={() => setActiveNav("settings")}
            onRetry={() => void files.retry()}
            onRetryIndexTask={() => void retryIndexTask()}
            onSelectionChange={setSelectedFileIds}
            selectedFileIds={selectedFileIds}
          />
        ) : activeNav === "resources" ? (
          <ResourcesPage
            doctor={doctor.resource}
            onOpenSettings={() => setActiveNav("settings")}
            onRetry={doctor.retry}
            runtime={runtime}
          />
        ) : activeNav === "help" ? (
          <HelpPage
            onOpenResources={() => setActiveNav("resources")}
            onOpenSettings={() => setActiveNav("settings")}
            version={runtime.version}
          />
        ) : activeNav === "settings" ? (
          <SettingsPage
            doctor={doctor.resource}
            onRetry={() => {
              modelSettings.retry();
              doctor.retry();
            }}
            onSave={(settings) => void saveModelSettings(settings)}
            saveError={modelSettingsSaveError}
            savePending={modelSettingsSavePending}
            settings={modelSettings.resource}
          />
        ) : (
          <Workspace
            answerActionError={answerActionError}
            answerActionPending={answerActionPending}
            answerTask={answerTask}
            isDraft={!selectedSessionId}
            modelName={
              doctor.resource.status === "success"
                ? doctor.resource.data.query_model
                : undefined
            }
            onCancelAnswer={() => void cancelAnswer()}
            onOpenSources={() => {
              setInspectorOpen(true);
              setInspectorTab("sources");
            }}
            onRetryAnswer={() => void retryAnswer()}
            onRetrySession={() => setSessionReload((value) => value + 1)}
            onOpenSettings={() => setActiveNav("settings")}
            onPromptChange={setComposerPrompt}
            onSubmitQuestion={(prompt) => void submitQuestion(prompt)}
            onToggleInspector={() => setInspectorOpen((value) => !value)}
            queryReadiness={querying}
            promptValue={composerPrompt}
            selectedSourceCount={selectedSourceIds.length}
            session={selectedSession}
            workspaceId={workspaceId}
          />
        )}
        {activeNav === "workbench" && inspectorOpen ? (
          <Inspector
            activeTab={inspectorTab}
            doctor={doctor.resource}
            files={files.resource}
            onClose={() => setInspectorOpen(false)}
            onRetryDoctor={doctor.retry}
            onRetryFiles={files.retry}
            onSelectTab={setInspectorTab}
            onToggleSource={toggleSource}
            runtime={runtime}
            selectedSourceIds={selectedSourceIds}
          />
        ) : null}
      </div>
    </>
  );
}

function unavailableResult<T>(message: string): Promise<DesktopResult<T>> {
  return Promise.resolve({
    ok: false,
    error: {
      code: "desktop_bridge_unavailable",
      message,
      details: null,
      retryable: false,
      request_id: "renderer-offline",
    },
  });
}

type FilesIndexingReadiness = Pick<
  DoctorPayload,
  | "indexing_ready"
  | "indexing_issue_code"
  | "indexing_message"
  | "indexing_action"
  | "request_id"
>;

type WorkbenchQueryReadiness = Pick<
  DoctorPayload,
  | "query_ready"
  | "query_issue_code"
  | "query_message"
  | "query_action"
  | "query_retryable"
  | "request_id"
>;

function indexingReadiness(
  doctor: ResourceState<DoctorPayload>,
): FilesIndexingReadiness {
  if (doctor.status === "success") {
    return {
      indexing_ready: doctor.data.indexing_ready,
      indexing_issue_code: doctor.data.indexing_issue_code,
      indexing_message: doctor.data.indexing_message,
      indexing_action: doctor.data.indexing_action,
      request_id: doctor.data.request_id,
    };
  }
  if (doctor.status === "failed") {
    return {
      indexing_ready: false,
      indexing_issue_code: doctor.error?.code ?? "doctor_unavailable",
      indexing_message: "无法确认文件索引准备状态。",
      indexing_action: "none",
      request_id: doctor.error?.request_id ?? "doctor-unavailable",
    };
  }
  return {
    indexing_ready: false,
    indexing_issue_code: "indexing_status_pending",
    indexing_message: "正在检查文件索引准备状态。",
    indexing_action: "none",
    request_id: "doctor-pending",
  };
}

function queryReadiness(
  doctor: ResourceState<DoctorPayload>,
): WorkbenchQueryReadiness {
  if (doctor.status === "success") {
    return {
      query_ready: doctor.data.query_ready,
      query_issue_code: doctor.data.query_issue_code,
      query_message: doctor.data.query_message,
      query_action: doctor.data.query_action,
      query_retryable: doctor.data.query_retryable,
      request_id: doctor.data.request_id,
    };
  }
  if (doctor.status === "failed") {
    return {
      query_ready: false,
      query_issue_code: doctor.error?.code ?? "doctor_unavailable",
      query_message: "无法确认问答模型准备状态。",
      query_action: "none",
      query_retryable: true,
      request_id: doctor.error?.request_id ?? "doctor-unavailable",
    };
  }
  return {
    query_ready: false,
    query_issue_code: "query_status_pending",
    query_message: "正在检查问答模型准备状态。",
    query_action: "none",
    query_retryable: true,
    request_id: "doctor-pending",
  };
}

function rendererSidecarError(code: string, message: string): SidecarError {
  return {
    code,
    message,
    details: null,
    retryable: false,
    request_id: "renderer-local",
  };
}

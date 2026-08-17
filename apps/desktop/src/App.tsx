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
import { type AppPage } from "./navigation";
import { LanguageProvider, useLanguage, type Translate } from "./i18n";
import type { ResourceState } from "./resource-state";
import { useDesktopResource } from "./useDesktopResource";

export default function App() {
  return (
    <LanguageProvider>
      <AppContent />
    </LanguageProvider>
  );
}

function AppContent() {
  const { t } = useLanguage();
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
      : unavailableRuntime(t("errors.desktopBridgeUnavailable")),
  );
  const loadDoctor = useCallback(
    () =>
      window.desktop?.getDoctor() ??
      unavailableResult(t("errors.doctorDesktopOnly")),
    [t],
  );
  const loadFiles = useCallback(
    () =>
      window.desktop?.listFiles() ??
      unavailableResult(t("errors.filesDesktopOnly")),
    [t],
  );
  const loadSessions = useCallback(
    () =>
      window.desktop?.listSessions() ??
      unavailableResult(t("errors.sessionsDesktopOnly")),
    [t],
  );
  const loadModelSettings = useCallback(
    () =>
      window.desktop?.getModelSettings() ??
      unavailableResult<ModelSettingsStatus>(
        t("errors.modelSettingsDesktopOnly"),
      ),
    [t],
  );
  const doctor = useDesktopResource(loadDoctor, t("errors.desktopBridgeUnavailable"));
  const files = useDesktopResource(loadFiles, t("errors.desktopBridgeUnavailable"));
  const sessions = useDesktopResource(loadSessions, t("errors.desktopBridgeUnavailable"));
  const modelSettings = useDesktopResource(
    loadModelSettings,
    t("errors.desktopBridgeUnavailable"),
  );
  const indexing = indexingReadiness(doctor.resource, t);
  const querying = queryReadiness(doctor.resource, t);

  useEffect(() => {
    document.title = t(`nav.${activeNav}` as Parameters<typeof t>[0]);
    document.title = t("common.pageTitle", { page: document.title });
    document.querySelector<HTMLElement>("[data-page-title]")?.focus();
  }, [activeNav, t]);

  useEffect(() => {
    if (!window.desktop) {
      setRuntime(unavailableRuntime(t("errors.desktopBridgeUnavailable")));
    }
  }, [t]);

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
            t("errors.sessionDetailsDesktopOnly"),
          )
        );
      } catch {
        result = await unavailableResult<SessionDetail>(
          t("errors.sessionReadFailed"),
        );
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
  }, [selectedSessionId, sessionReload, t]);
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
      .catch(() =>
        setRuntime(unavailableRuntime(t("errors.desktopBridgeUnavailable"))),
      );
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
  }, [t, updateAnswerTask, updateIndexTask]);

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
            t("errors.fileImportDesktopOnly"),
          ),
        "file_import_failed",
        t("errors.fileImportFailed"),
      ),
    [runFileImport, t],
  );

  const importDroppedFiles = useCallback(
    (droppedFiles: File[]) =>
      runFileImport(
        () =>
          window.desktop?.importDroppedFiles(droppedFiles) ??
          unavailableResult<IndexTask>(
            t("errors.fileDropDesktopOnly"),
          ),
        "file_drop_failed",
        t("errors.fileDropFailed"),
      ),
    [runFileImport, t],
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
        unavailableResult<IndexTask>(t("errors.indexTaskDesktopOnly"))
      );
      if (result.ok) {
        updateIndexTask(result.data);
      } else {
        setFileActionError(result.error);
      }
    } catch {
      setFileActionError(
        rendererSidecarError(
          "index_cancel_failed",
          t("errors.indexCancelFailed"),
        ),
      );
    } finally {
      indexActionLock.current = false;
      setIndexActionPending(false);
    }
  }, [indexTask, t, updateIndexTask]);

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
        unavailableResult<IndexTask>(t("errors.indexTaskDesktopOnly"))
      );
      if (result.ok) {
        updateIndexTask(result.data);
      } else {
        setFileActionError(result.error);
      }
    } catch {
      setFileActionError(
        rendererSidecarError(
          "index_retry_failed",
          t("errors.indexRetryFailed"),
        ),
      );
    } finally {
      indexActionLock.current = false;
      setIndexActionPending(false);
    }
  }, [indexTask, t, updateIndexTask]);

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
          ? t("errors.deleteFileConfirm", {
              name: targets[0].name || t("common.unnamedFile"),
            })
          : t("errors.deleteFilesConfirm", { count: targets.length });
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
          unavailableResult<string[]>(t("errors.fileDeleteDesktopOnly"))
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
          rendererSidecarError(
            "file_delete_failed",
            t("errors.fileDeleteFailed"),
          ),
        );
        files.retry();
      } finally {
        fileDeletionLock.current = false;
        setDeletingFileIds([]);
      }
    },
    [files.retry, t],
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
              t("errors.newTaskDesktopOnly"),
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
          }) ?? unavailableResult<QueryTask>(t("errors.qaDesktopOnly"))
        );
        if (result.ok) {
          updateAnswerTask(result.data, true);
        } else {
          setAnswerActionError(result.error);
        }
      } catch {
        setAnswerActionError(
          rendererSidecarError(
            "query_submit_failed",
            t("errors.questionSubmitFailed"),
          ),
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
      t,
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
        unavailableResult<QueryTask>(t("errors.answerTaskDesktopOnly"))
      );
      if (result.ok) {
        updateAnswerTask(result.data);
      } else {
        setAnswerActionError(result.error);
      }
    } catch {
      setAnswerActionError(
        rendererSidecarError(
          "query_cancel_failed",
          t("errors.answerCancelFailed"),
        ),
      );
    } finally {
      answerActionLock.current = false;
      setAnswerActionPending(false);
    }
  }, [answerTask, t, updateAnswerTask]);

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
        unavailableResult<QueryTask>(t("errors.answerTaskDesktopOnly"))
      );
      if (result.ok) {
        updateAnswerTask(result.data, true);
      } else {
        setAnswerActionError(result.error);
      }
    } catch {
      setAnswerActionError(
        rendererSidecarError(
          "query_retry_failed",
          t("errors.answerRetryFailed"),
        ),
      );
    } finally {
      answerActionLock.current = false;
      setAnswerActionPending(false);
    }
  }, [answerTask, t, updateAnswerTask]);

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
            t("errors.modelSettingsSaveDesktopOnly"),
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
            t("errors.modelSettingsApplyFailed"),
          ),
        );
      } finally {
        modelSettingsSaveLock.current = false;
        setModelSettingsSavePending(false);
      }
    },
    [doctor.retry, modelSettings.retry, t],
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
    setEditingSessionName(session.name || t("common.unnamedTask"));
    setSessionActionError(undefined);
  }, [t]);

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
            t("errors.renameDesktopOnly"),
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
        setSessionActionError(t("errors.renameFailed"));
      } finally {
        sessionMutationLock.current = false;
        setSessionAction(undefined);
      }
    },
    [selectedSessionId, sessions.retry, t],
  );

  const deleteSession = useCallback(
    async (session: SessionSummary) => {
      if (sessionMutationLock.current || sessionCreateLock.current) {
        return;
      }
      const name = session.name || t("common.unnamedTask");
      if (
        !window.confirm(
          t("errors.deleteSessionConfirm", { name }),
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
          unavailableResult<string>(t("errors.deleteSessionDesktopOnly"))
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
        setSessionActionError(t("errors.deleteSessionFailed"));
        sessions.retry();
      } finally {
        sessionMutationLock.current = false;
        setSessionAction(undefined);
      }
    },
    [
      answerTask?.conversation_id,
      editingSessionId,
      selectedSessionId,
      sessions.retry,
      t,
    ],
  );

  return (
    <>
      <a className="skip-link" href="#main-workspace">{t("nav.skipToMain")}</a>
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
            answerTask={answerTask}
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

function unavailableRuntime(message: string): RuntimeStatus {
  return {
    state: "failed",
    protocol: 1,
    capabilities: [],
    message,
  };
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
  t: Translate,
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
      indexing_message: t("errors.indexingUnavailable"),
      indexing_action: "none",
      request_id: doctor.error?.request_id ?? "doctor-unavailable",
    };
  }
  return {
    indexing_ready: false,
    indexing_issue_code: "indexing_status_pending",
    indexing_message: t("errors.indexingPending"),
    indexing_action: "none",
    request_id: "doctor-pending",
  };
}

function queryReadiness(
  doctor: ResourceState<DoctorPayload>,
  t: Translate,
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
      query_message: t("errors.queryUnavailable"),
      query_action: "none",
      query_retryable: true,
      request_id: doctor.error?.request_id ?? "doctor-unavailable",
    };
  }
  return {
    query_ready: false,
    query_issue_code: "query_status_pending",
    query_message: t("errors.queryPending"),
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

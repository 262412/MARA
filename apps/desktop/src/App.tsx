import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import type { FileRecord } from "../shared/file-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
import type {
  DesktopResult,
  RuntimeStatus,
} from "../shared/runtime-contracts";
import type {
  SessionDetail,
  SessionSummary,
} from "../shared/session-contracts";
import { FilesPage } from "./components/FilesPage";
import { Inspector, type InspectorTab } from "./components/Inspector";
import { Sidebar } from "./components/Sidebar";
import { Workspace } from "./components/Workspace";
import { refreshFilesForTerminalTask } from "./index-task-state";
import type { ResourceState } from "./resource-state";
import { useDesktopResource } from "./useDesktopResource";

const unavailableRuntime: RuntimeStatus = {
  state: "failed",
  protocol: 1,
  capabilities: [],
  message: "Desktop bridge 不可用。",
};

export default function App() {
  const [activeNav, setActiveNav] = useState("workbench");
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
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("preview");
  const [indexTask, setIndexTask] = useState<IndexTask>();
  const [indexActionPending, setIndexActionPending] = useState(false);
  const [deletingFileIds, setDeletingFileIds] = useState<string[]>([]);
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>([]);
  const [fileActionError, setFileActionError] = useState<string>();
  const lastTaskRefresh = useRef<string | undefined>(undefined);
  const fileDeletionLock = useRef(false);
  const indexActionLock = useRef(false);
  const sessionRequestGeneration = useRef(0);
  const sessionMutationLock = useRef(false);
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
  const doctor = useDesktopResource(loadDoctor);
  const files = useDesktopResource(loadFiles);
  const sessions = useDesktopResource(loadSessions);

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
    const removeRuntimeListener = window.desktop.onRuntimeStatus(setRuntime);
    const removeTaskListener = window.desktop.onIndexTaskStatus(updateIndexTask);
    return () => {
      removeRuntimeListener();
      removeTaskListener();
    };
  }, [updateIndexTask]);

  const runFileImport = useCallback(
    async (
      operation: () => Promise<DesktopResult<IndexTask | null>>,
      failureMessage: string,
    ) => {
      if (indexActionLock.current) {
        return;
      }
      indexActionLock.current = true;
      setIndexActionPending(true);
      setFileActionError(undefined);
      try {
        const result = await operation();
        if (!result.ok) {
          setFileActionError(result.error.message);
        } else if (result.data) {
          updateIndexTask(result.data);
        }
      } catch {
        setFileActionError(failureMessage);
      } finally {
        indexActionLock.current = false;
        setIndexActionPending(false);
      }
    },
    [updateIndexTask],
  );

  const importFiles = useCallback(
    () =>
      runFileImport(
        () =>
          window.desktop?.importFiles() ??
          unavailableResult<IndexTask | null>(
            "文件导入仅能在 MARA Desktop 中使用。",
          ),
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
        setFileActionError(result.error.message);
      }
    } catch {
      setFileActionError("取消索引未能完成。");
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
        setFileActionError(result.error.message);
      }
    } catch {
      setFileActionError("重试索引未能完成。");
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
          files.retry();
        } else {
          setFileActionError(result.error.message);
          files.retry();
        }
      } catch {
        setFileActionError("文件删除未能完成。");
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
  }, [files.resource]);

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "o") {
        event.preventDefault();
        void importFiles();
      }
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [importFiles]);

  const selectSession = useCallback((sessionId: string) => {
    setActiveNav("workbench");
    setSelectedSessionId(sessionId);
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
      if (sessionMutationLock.current) {
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
            setSelectedSessionId(undefined);
            setSelectedSession(undefined);
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
    [editingSessionId, selectedSessionId, sessions.retry],
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
          onRenameSession={(conversationId, name) =>
            void renameSession(conversationId, name)
          }
          onDeleteSession={(session) => void deleteSession(session)}
          sessionAction={sessionAction}
          sessionActionError={sessionActionError}
          selectedSessionId={selectedSessionId}
          sessions={sessions.resource}
        />
        {activeNav === "files" ? (
          <FilesPage
            actionError={fileActionError}
            deletingFileIds={deletingFileIds}
            files={files.resource}
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
            onRetry={() => void files.retry()}
            onRetryIndexTask={() => void retryIndexTask()}
            onSelectionChange={setSelectedFileIds}
            selectedFileIds={selectedFileIds}
          />
        ) : (
          <Workspace
            onRetrySession={() => setSessionReload((value) => value + 1)}
            onToggleInspector={() => setInspectorOpen((value) => !value)}
            session={selectedSession}
          />
        )}
        {inspectorOpen ? (
          <Inspector
            activeTab={inspectorTab}
            doctor={doctor.resource}
            onClose={() => setInspectorOpen(false)}
            onRetryDoctor={doctor.retry}
            onSelectTab={setInspectorTab}
            runtime={runtime}
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

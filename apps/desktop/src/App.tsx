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
import { FilesPage } from "./components/FilesPage";
import { Inspector, type InspectorTab } from "./components/Inspector";
import { Sidebar } from "./components/Sidebar";
import { Workspace } from "./components/Workspace";
import { refreshFilesForTerminalTask } from "./index-task-state";
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
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("preview");
  const [indexTask, setIndexTask] = useState<IndexTask>();
  const [indexActionPending, setIndexActionPending] = useState(false);
  const [deletingFileId, setDeletingFileId] = useState<string>();
  const [fileActionError, setFileActionError] = useState<string>();
  const lastTaskRefresh = useRef<string | undefined>(undefined);
  const indexActionLock = useRef(false);
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

  const importFiles = useCallback(async () => {
    if (indexActionLock.current) {
      return;
    }
    indexActionLock.current = true;
    setIndexActionPending(true);
    setFileActionError(undefined);
    try {
      const result = await (
        window.desktop?.importFiles() ??
        unavailableResult<IndexTask | null>(
          "文件导入仅能在 MARA Desktop 中使用。",
        )
      );
      if (!result.ok) {
        setFileActionError(result.error.message);
      } else if (result.data) {
        updateIndexTask(result.data);
      }
    } catch {
      setFileActionError("文件导入未能完成。");
    } finally {
      indexActionLock.current = false;
      setIndexActionPending(false);
    }
  }, [updateIndexTask]);

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

  const deleteFile = useCallback(
    async (file: FileRecord) => {
      if (!window.confirm(`删除“${file.name}”的索引和受管副本？`)) {
        return;
      }
      setDeletingFileId(file.file_id);
      setFileActionError(undefined);
      try {
        const result = await (
          window.desktop?.deleteFile(file.file_id) ??
          unavailableResult<string[]>("文件删除仅能在 MARA Desktop 中使用。")
        );
        if (result.ok) {
          void files.retry();
        } else {
          setFileActionError(result.error.message);
        }
      } catch {
        setFileActionError("文件删除未能完成。");
      } finally {
        setDeletingFileId(undefined);
      }
    },
    [files.retry],
  );

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

  const openCitation = () => {
    setInspectorOpen(true);
    setInspectorTab("preview");
  };

  return (
    <>
      <a className="skip-link" href="#main-workspace">跳到主工作区</a>
      <div className="app-shell">
        <Sidebar
          active={activeNav}
          onNavigate={setActiveNav}
          onRetrySessions={sessions.retry}
          onSelectSession={setSelectedSessionId}
          selectedSessionId={selectedSessionId}
          sessions={sessions.resource}
        />
        {activeNav === "files" ? (
          <FilesPage
            actionError={fileActionError}
            deletingFileId={deletingFileId}
            files={files.resource}
            indexActionPending={indexActionPending}
            indexTask={indexTask}
            onCancelIndexTask={() => void cancelIndexTask()}
            onDelete={(file) => void deleteFile(file)}
            onImport={() => void importFiles()}
            onRetry={() => void files.retry()}
            onRetryIndexTask={() => void retryIndexTask()}
          />
        ) : (
          <Workspace
            onOpenCitation={openCitation}
            onToggleInspector={() => setInspectorOpen((value) => !value)}
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

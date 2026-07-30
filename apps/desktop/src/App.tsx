import {
  useCallback,
  useEffect,
  useState,
} from "react";

import type {
  DesktopResult,
  RuntimeStatus,
} from "../shared/runtime-contracts";
import { FilesPage } from "./components/FilesPage";
import { Inspector, type InspectorTab } from "./components/Inspector";
import { Sidebar } from "./components/Sidebar";
import { Workspace } from "./components/Workspace";
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
    if (!window.desktop) {
      return;
    }
    void window.desktop
      .getRuntimeStatus()
      .then(setRuntime)
      .catch(() => setRuntime(unavailableRuntime));
    return window.desktop.onRuntimeStatus(setRuntime);
  }, []);

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
          <FilesPage files={files.resource} onRetry={files.retry} />
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

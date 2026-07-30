import { useEffect, useState } from "react";

import type { RuntimeStatus } from "../electron/sidecar-manager";
import { Inspector, type InspectorTab } from "./components/Inspector";
import { Sidebar } from "./components/Sidebar";
import { Workspace } from "./components/Workspace";

const browserPreviewStatus: RuntimeStatus = {
  state: "healthy",
  protocol: 1,
  version: "browser-preview",
  capabilities: ["ui-preview"],
};

export default function App() {
  const [activeNav, setActiveNav] = useState("workbench");
  const [selectedTask, setSelectedTask] = useState(1);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("preview");
  const [runtime, setRuntime] = useState<RuntimeStatus>(
    window.maraDesktop
      ? { state: "starting", protocol: 1, capabilities: [] }
      : browserPreviewStatus,
  );

  useEffect(() => {
    if (!window.maraDesktop) {
      return;
    }
    void window.maraDesktop.getRuntimeStatus().then(setRuntime);
    return window.maraDesktop.onRuntimeStatus(setRuntime);
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
          onSelectTask={setSelectedTask}
          selectedTask={selectedTask}
        />
        <Workspace
          onOpenCitation={openCitation}
          onToggleInspector={() => setInspectorOpen((value) => !value)}
        />
        {inspectorOpen ? (
          <Inspector
            activeTab={inspectorTab}
            onClose={() => setInspectorOpen(false)}
            onSelectTab={setInspectorTab}
            runtime={runtime}
          />
        ) : null}
      </div>
    </>
  );
}

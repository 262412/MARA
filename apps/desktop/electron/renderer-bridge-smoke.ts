import type { WebContents } from "electron";

const requiredBridgeMethods = [
  "getRuntimeStatus",
  "getDoctor",
  "listFiles",
  "listSessions",
  "getModelSettings",
  "openEmbeddingConfiguration",
] as const;

type RendererBridgeSmokeResult = {
  bridgeAvailable: boolean;
  missingMethods: string[];
  runtimeState: string | null;
  doctorOk: boolean;
  filesOk: boolean;
  sessionsOk: boolean;
  modelSettingsOk: boolean;
  unavailableMessageVisible: boolean;
};

type RendererBridgeWebContents = Pick<WebContents, "executeJavaScript">;

type IndexingBlockedRendererSmokeResult = {
  addButtonDisabled: boolean;
  configActionVisible: boolean;
  doctorBlocked: boolean;
  dropPromptVisible: boolean;
  issueCodeVisible: boolean;
  latestTaskEmpty: boolean;
};

function rendererBridgeSmokeScript(): string {
  const methods = JSON.stringify(requiredBridgeMethods);
  return `
    (async () => {
      const bridge = window.desktop;
      const requiredMethods = ${methods};
      const missingMethods = bridge
        ? requiredMethods.filter((name) => typeof bridge[name] !== "function")
        : requiredMethods;
      if (!bridge || missingMethods.length > 0) {
        return {
          bridgeAvailable: Boolean(bridge),
          missingMethods,
          runtimeState: null,
          doctorOk: false,
          filesOk: false,
          sessionsOk: false,
          modelSettingsOk: false,
          unavailableMessageVisible: document.body.innerText.includes(
            "仅能在 MARA Desktop 中使用。",
          ),
        };
      }
      const [runtime, doctor, files, sessions, modelSettings] = await Promise.all([
        bridge.getRuntimeStatus(),
        bridge.getDoctor(),
        bridge.listFiles(),
        bridge.listSessions(),
        bridge.getModelSettings(),
      ]);
      return {
        bridgeAvailable: true,
        missingMethods,
        runtimeState: typeof runtime?.state === "string" ? runtime.state : null,
        doctorOk: doctor?.ok === true,
        filesOk: files?.ok === true && Array.isArray(files.data),
        sessionsOk: sessions?.ok === true && Array.isArray(sessions.data),
        modelSettingsOk:
          modelSettings?.ok === true &&
          !JSON.stringify(modelSettings.data).includes('"credential":'),
        unavailableMessageVisible: document.body.innerText.includes(
          "仅能在 MARA Desktop 中使用。",
        ),
      };
    })()
  `;
}

function assertRendererBridgeSmoke(
  result: RendererBridgeSmokeResult,
): void {
  const failures: string[] = [];
  if (!result.bridgeAvailable) failures.push("window.desktop is unavailable");
  if (result.missingMethods.length > 0) {
    failures.push(`missing methods: ${result.missingMethods.join(", ")}`);
  }
  if (result.runtimeState !== "healthy") {
    failures.push(`runtime state is ${result.runtimeState ?? "missing"}`);
  }
  if (!result.doctorOk) failures.push("Doctor IPC failed");
  if (!result.filesOk) failures.push("Files IPC failed");
  if (!result.sessionsOk) failures.push("Sessions IPC failed");
  if (!result.modelSettingsOk) failures.push("model settings IPC was not redacted");
  if (result.unavailableMessageVisible) {
    failures.push("renderer displayed the bridge-unavailable fallback");
  }
  if (failures.length > 0) {
    throw new Error(`Packaged renderer bridge smoke failed: ${failures.join("; ")}`);
  }
}

export async function runRendererBridgeSmoke(
  webContents: RendererBridgeWebContents,
  reportSuccess: (message: string) => void = console.log,
): Promise<void> {
  const result = (await webContents.executeJavaScript(
    rendererBridgeSmokeScript(),
  )) as RendererBridgeSmokeResult;
  assertRendererBridgeSmoke(result);
  reportSuccess(
    "renderer_bridge=window.desktop real_ipc=runtime,doctor,files,sessions,model-settings status_success",
  );
}

function indexingBlockedRendererSmokeScript(): string {
  return `
    (async () => {
      const bridge = window.desktop;
      if (!bridge) {
        return {};
      }
      const [doctor, latestTask] = await Promise.all([
        bridge.getDoctor(),
        bridge.getLatestIndexTask(),
      ]);
      const filesNavigation = Array.from(document.querySelectorAll("button"))
        .find((button) => button.textContent?.trim() === "Files");
      filesNavigation?.click();
      let dragAttempted = false;
      for (let attempt = 0; attempt < 100; attempt += 1) {
        const filesPage = document.querySelector(".files-page");
        if (filesPage && !dragAttempted) {
          const dataTransfer = new DataTransfer();
          dataTransfer.items.add(new File(["blocked"], "blocked.txt"));
          filesPage.dispatchEvent(
            new DragEvent("dragenter", {
              bubbles: true,
              cancelable: true,
              dataTransfer,
            }),
          );
          dragAttempted = true;
          await new Promise((resolve) => setTimeout(resolve, 0));
        }
        const bodyText = document.body.innerText;
        const buttons = Array.from(document.querySelectorAll("button"));
        const addButton = buttons.find((button) =>
          button.textContent?.includes("添加文件"),
        );
        const configButton = buttons.find((button) =>
          button.textContent?.includes("配置 Embedding"),
        );
        const result = {
          addButtonDisabled: addButton?.disabled === true,
          configActionVisible: Boolean(configButton),
          doctorBlocked:
            doctor?.ok === true &&
            doctor.data?.indexing_ready === false &&
            doctor.data?.indexing_issue_code === "embedding_not_configured",
          dropPromptVisible: bodyText.includes("释放文件以开始索引"),
          issueCodeVisible:
            bodyText.includes("文件索引尚未准备好") &&
            bodyText.includes("embedding_not_configured"),
          latestTaskEmpty: latestTask?.ok === true && latestTask.data === null,
        };
        if (
          result.addButtonDisabled &&
          result.configActionVisible &&
          result.issueCodeVisible
        ) {
          return result;
        }
        await new Promise((resolve) => setTimeout(resolve, 50));
      }
      return {
        addButtonDisabled: false,
        configActionVisible: false,
        doctorBlocked: false,
        dropPromptVisible: document.body.innerText.includes(
          "释放文件以开始索引",
        ),
        issueCodeVisible: false,
        latestTaskEmpty: false,
      };
    })()
  `;
}

export async function runIndexingBlockedRendererSmoke(
  webContents: RendererBridgeWebContents,
  reportSuccess: (message: string) => void = console.log,
): Promise<void> {
  const result = (await webContents.executeJavaScript(
    indexingBlockedRendererSmokeScript(),
  )) as IndexingBlockedRendererSmokeResult;
  const failures: string[] = [];
  if (!result.doctorBlocked) failures.push("Doctor did not block indexing");
  if (!result.addButtonDisabled) failures.push("Add file remained enabled");
  if (!result.configActionVisible) failures.push("config action is missing");
  if (!result.issueCodeVisible) failures.push("stable issue code is missing");
  if (!result.latestTaskEmpty) failures.push("an index task was persisted");
  if (result.dropPromptVisible) failures.push("file drop remained enabled");
  if (failures.length > 0) {
    throw new Error(
      `Packaged indexing readiness UI smoke failed: ${failures.join("; ")}`,
    );
  }
  reportSuccess(
    "renderer_indexing=embedding_not_configured ui_blocked=true latest_task=empty status_success",
  );
}

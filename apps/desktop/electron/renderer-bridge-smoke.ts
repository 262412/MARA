import type { WebContents } from "electron";

const requiredBridgeMethods = [
  "getRuntimeStatus",
  "getDoctor",
  "listFiles",
  "listSessions",
] as const;

type RendererBridgeSmokeResult = {
  bridgeAvailable: boolean;
  missingMethods: string[];
  runtimeState: string | null;
  doctorOk: boolean;
  filesOk: boolean;
  sessionsOk: boolean;
  unavailableMessageVisible: boolean;
};

type RendererBridgeWebContents = Pick<WebContents, "executeJavaScript">;

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
          unavailableMessageVisible: document.body.innerText.includes(
            "仅能在 MARA Desktop 中使用。",
          ),
        };
      }
      const [runtime, doctor, files, sessions] = await Promise.all([
        bridge.getRuntimeStatus(),
        bridge.getDoctor(),
        bridge.listFiles(),
        bridge.listSessions(),
      ]);
      return {
        bridgeAvailable: true,
        missingMethods,
        runtimeState: typeof runtime?.state === "string" ? runtime.state : null,
        doctorOk: doctor?.ok === true,
        filesOk: files?.ok === true && Array.isArray(files.data),
        sessionsOk: sessions?.ok === true && Array.isArray(sessions.data),
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
    "renderer_bridge=window.desktop real_ipc=runtime,doctor,files,sessions status_success",
  );
}

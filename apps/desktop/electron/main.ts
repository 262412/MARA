import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  protocol,
  session,
} from "electron";

import type {
  DesktopResult,
  RuntimeStatus,
} from "../shared/runtime-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
import { resolveDesktopDataRoot } from "./desktop-data";
import { chooseFilesForIndex } from "./file-import";
import { registerDesktopIpc } from "./ipc";
import { contentTypeFor, resolveAppAsset } from "./protocol";
import { SidecarManager } from "./sidecar-manager";
import { runDesktopSmoke } from "./smoke-runner";
import {
  GATE2_SMOKE_FILE_ID,
  GATE3_FORMAT_INPUT_NAMES,
  GATE3_FORMAT_RECORD_NAMES,
  assertGate3DeleteSmoke,
  assertGate3IndexSmoke,
  assertPackagedSmoke,
} from "./smoke-validation";

protocol.registerSchemesAsPrivileged([
  {
    scheme: "mara",
    privileges: {
      secure: true,
      standard: true,
      supportFetchAPI: true,
    },
  },
]);
app.enableSandbox();

let mainWindow: BrowserWindow | undefined;
let quitting = false;
const watchedIndexTasks = new Set<string>();

const desktopDataRoot = resolveDesktopDataRoot(
  process.platform,
  process.env,
  app.getPath("home"),
  app.getPath("appData"),
);
const sidecar = new SidecarManager({
  appPath: app.getAppPath(),
  dataRoot: desktopDataRoot,
  isPackaged: app.isPackaged,
  resourcesPath: process.resourcesPath,
  onStatus: (status) => broadcastRuntimeStatus(status),
});

function broadcastRuntimeStatus(status: RuntimeStatus): void {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("runtime:status", status);
  }
}

function broadcastIndexTask(task: IndexTask): void {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("index-task:status", task);
  }
}

function watchIndexTask(task: IndexTask): void {
  broadcastIndexTask(task);
  if (
    ["partial", "success", "failed", "cancelled"].includes(task.status) ||
    watchedIndexTasks.has(task.task_id)
  ) {
    return;
  }
  watchedIndexTasks.add(task.task_id);
  void sidecar
    .watchIndexTask(task.task_id, broadcastIndexTask)
    .finally(() => watchedIndexTasks.delete(task.task_id));
}

async function waitForIndexTaskTerminal(
  taskId: string,
): Promise<DesktopResult<IndexTask>> {
  const deadline = Date.now() + 60_000;
  let current = await sidecar.getIndexTask(taskId);
  while (
    current.ok &&
    ["queued", "running"].includes(current.data.status) &&
    Date.now() < deadline
  ) {
    await new Promise<void>((resolve) => setTimeout(resolve, 100));
    current = await sidecar.getIndexTask(taskId);
  }
  return current;
}

function registerIpc(): void {
  registerDesktopIpc(ipcMain, {
    getRuntimeStatus: () => sidecar.getStatus(),
    getDoctor: () => sidecar.getDoctor(),
    listFiles: () => sidecar.listFiles(),
    listSessions: () => sidecar.listSessions(),
    importFiles: async () => {
      const capabilities = await sidecar.getImportCapabilities();
      if (!capabilities.ok) {
        return { ok: false, error: capabilities.error };
      }
      const paths = await chooseFilesForIndex(
        (options) =>
          mainWindow
            ? dialog.showOpenDialog(mainWindow, options)
            : dialog.showOpenDialog(options),
        capabilities.data.supported_extensions,
      );
      if (paths.length === 0) {
        return { ok: true, data: null };
      }
      const result = await sidecar.createIndexTask(paths);
      if (result.ok) {
        watchIndexTask(result.data);
      }
      return result;
    },
    getLatestIndexTask: () => sidecar.getLatestIndexTask(),
    cancelIndexTask: async (taskId) => {
      const result = await sidecar.cancelIndexTask(taskId);
      if (result.ok) {
        watchIndexTask(result.data);
      }
      return result;
    },
    retryIndexTask: async (taskId) => {
      const result = await sidecar.retryIndexTask(taskId);
      if (result.ok) {
        watchIndexTask(result.data);
      }
      return result;
    },
    deleteFile: (fileId) => sidecar.deleteFile(fileId),
  });
}

async function registerApplicationProtocol(): Promise<void> {
  const rendererRoot = path.join(app.getAppPath(), "dist");
  protocol.handle("mara", async (request) => {
    try {
      const assetPath = resolveAppAsset(rendererRoot, request.url);
      const body = await readFile(assetPath);
      return new Response(body, {
        status: 200,
        headers: {
          "Content-Type": contentTypeFor(assetPath),
          "Cross-Origin-Opener-Policy": "same-origin",
          "X-Content-Type-Options": "nosniff",
        },
      });
    } catch {
      return new Response("Not found", { status: 404 });
    }
  });
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 720,
    backgroundColor: "#111312",
    show: false,
    title: "MARA",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith("mara://app/")) {
      event.preventDefault();
    }
  });
  mainWindow.once("ready-to-show", () => mainWindow?.show());
  void mainWindow.loadURL("mara://app/");
}

app.whenReady().then(async () => {
  await registerApplicationProtocol();
  session.defaultSession.setPermissionRequestHandler(
    (_webContents, _permission, callback) => callback(false),
  );
  registerIpc();
  const startup = sidecar.start();
  createWindow();
  const requireGate3Formats = process.argv.includes(
    "--smoke-test-gate3-formats",
  );
  const requireGate3Delete =
    process.argv.includes("--smoke-test-gate3") || requireGate3Formats;
  const requireNonEmptyFixture =
    process.argv.includes("--smoke-test-nonempty") || requireGate3Delete;
  if (process.argv.includes("--smoke-test") || requireNonEmptyFixture) {
    const exitCode = await runDesktopSmoke(async () => {
      const [status, doctor, files, sessions, importCapabilities] =
        await Promise.all([
          startup,
          sidecar.getDoctor(),
          sidecar.listFiles(),
          sidecar.listSessions(),
          sidecar.getImportCapabilities(),
        ]);
      assertPackagedSmoke(
        { status, doctor, files, sessions, importCapabilities },
        requireNonEmptyFixture,
      );
      if (requireGate3Delete) {
        const indexInput = path.join(
          desktopDataRoot,
          "tmp",
          "gate3-index-smoke.txt",
        );
        await writeFile(
          indexInput,
          "MARA Desktop Gate 3 deterministic indexing smoke fixture.\n",
          "utf8",
        );
        const indexInputs = [indexInput];
        if (requireGate3Formats) {
          indexInputs.push(
            ...GATE3_FORMAT_INPUT_NAMES.map((name) =>
              path.join(desktopDataRoot, "tmp", name),
            ),
          );
        }
        const created = await sidecar.createIndexTask(indexInputs);
        const terminal = created.ok
          ? await waitForIndexTaskTerminal(created.data.task_id)
          : created;
        const filesAfterIndex = await sidecar.listFiles();
        const indexedFileIds = assertGate3IndexSmoke(
          created,
          terminal,
          filesAfterIndex,
          requireGate3Formats
            ? GATE3_FORMAT_RECORD_NAMES
            : ["gate3-index-smoke.txt"],
        );
        const initialFileIds = files.ok
          ? files.data.map((record) => record.file_id)
          : [GATE2_SMOKE_FILE_ID];
        const fileIdsToDelete = [
          ...new Set([...initialFileIds, ...indexedFileIds]),
        ];
        const deleteResults: Array<{
          fileId: string;
          result: DesktopResult<string[]>;
        }> = [];
        for (const fileId of fileIdsToDelete) {
          deleteResults.push({
            fileId,
            result: await sidecar.deleteFile(fileId),
          });
        }
        const filesAfterDelete = await sidecar.listFiles();
        for (const deletion of deleteResults) {
          assertGate3DeleteSmoke(
            deletion.result,
            filesAfterDelete,
            deletion.fileId,
          );
        }
      }
    }, () => sidecar.stop());
    quitting = true;
    app.exit(exitCode);
    return;
  } else {
    await startup;
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("before-quit", (event) => {
  if (quitting) {
    return;
  }
  event.preventDefault();
  quitting = true;
  void sidecar.stop().finally(() => app.quit());
});

app.on("window-all-closed", () => {
  app.quit();
});

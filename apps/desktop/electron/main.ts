import { existsSync } from "node:fs";
import { readFile, unlink, writeFile } from "node:fs/promises";
import path from "node:path";

import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  protocol,
  session,
} from "electron";

import type { FileRecord } from "../shared/file-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
import type {
  DesktopResult,
  RuntimeStatus,
} from "../shared/runtime-contracts";
import { resolveDesktopDataRoot } from "./desktop-data";
import { chooseFilesForIndex } from "./file-import";
import { registerDesktopIpc } from "./ipc";
import { contentTypeFor, resolveAppAsset } from "./protocol";
import { SidecarManager } from "./sidecar-manager";
import { runDesktopSmoke } from "./smoke-runner";
import {
  GATE3_FORMAT_INPUT_NAMES,
  GATE3_FORMAT_RECORD_NAMES,
  GATE3_CANCEL_BLOCK_MARKER_NAME,
  GATE3_CANCEL_INPUT_NAMES,
  GATE3_CANCEL_REQUEST_MARKER_NAME,
  GATE3_DATABASE_LOCKED_INPUT_NAME,
  GATE3_DISK_FULL_INPUT_NAME,
  GATE3_INTERRUPTED_INPUT_NAME,
  GATE3_LARGE_FILE_BYTES,
  GATE3_LARGE_FILE_INPUT_NAME,
  GATE3_MODEL_UNAVAILABLE_INPUT_NAME,
  GATE3_PARTIAL_INPUT_NAMES,
  assertGate3CancellationSmoke,
  assertGate3CancelRetrySmoke,
  assertGate3DatabaseLockedSmoke,
  assertGate3DeleteSmoke,
  assertGate3DiskFullSmoke,
  assertGate3IndexSmoke,
  assertGate3InterruptedRetrySmoke,
  assertGate3InterruptedSmoke,
  assertGate3LargeFileSmoke,
  assertGate3ModelUnavailableSmoke,
  assertGate3PartialRetrySmoke,
  assertGate3PartialSmoke,
  assertGate3RetrySource,
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
let recoverIndexTaskAfterRestart = false;
const watchedIndexTasks = new Set<string>();

const requireGate3DiskFull = process.argv.includes(
  "--smoke-test-gate3-disk-full",
);
const requireGate3DatabaseLock = process.argv.includes(
  "--smoke-test-gate3-database-lock",
);
if (requireGate3DiskFull && requireGate3DatabaseLock) {
  throw new Error("Only one Gate 3 storage fault can be injected per launch");
}
const gate3SmokeFault = requireGate3DiskFull
  ? "disk_full"
  : requireGate3DatabaseLock
    ? "database_locked"
    : undefined;

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
  smokeFault: gate3SmokeFault,
  onStatus: handleSidecarStatus,
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

function handleSidecarStatus(status: RuntimeStatus): void {
  if (status.state === "failed") {
    recoverIndexTaskAfterRestart = true;
  }
  broadcastRuntimeStatus(status);
  if (status.state === "healthy" && recoverIndexTaskAfterRestart) {
    recoverIndexTaskAfterRestart = false;
    void sidecar.getLatestIndexTask().then((latest) => {
      if (latest.ok && latest.data) {
        watchIndexTask(latest.data);
      }
    });
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
  timeoutMs = 60_000,
): Promise<DesktopResult<IndexTask>> {
  const deadline = Date.now() + timeoutMs;
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

async function waitForSmokeMarker(markerPath: string): Promise<void> {
  const deadline = Date.now() + 30_000;
  while (!existsSync(markerPath) && Date.now() < deadline) {
    await new Promise<void>((resolve) => setTimeout(resolve, 50));
  }
  if (!existsSync(markerPath)) {
    throw new Error("Gate 3 embedding request did not reach the smoke server");
  }
}

async function waitForHealthySidecar(): Promise<RuntimeStatus> {
  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    const status = sidecar.getStatus();
    if (status.state === "healthy") {
      return status;
    }
    await new Promise<void>((resolve) => setTimeout(resolve, 50));
  }
  throw new Error("Gate 3 Sidecar did not restart automatically");
}

async function deleteSmokeFiles(
  initialFiles: FileRecord[],
  indexedFileIds: string[],
): Promise<void> {
  const initialFileIds = initialFiles.map((record) => record.file_id);
  const fileIds = [...new Set([...initialFileIds, ...indexedFileIds])];
  const deletions: Array<{
    fileId: string;
    result: DesktopResult<string[]>;
  }> = [];
  for (const fileId of fileIds) {
    deletions.push({ fileId, result: await sidecar.deleteFile(fileId) });
  }
  const filesAfterDelete = await sidecar.listFiles();
  for (const deletion of deletions) {
    assertGate3DeleteSmoke(
      deletion.result,
      filesAfterDelete,
      deletion.fileId,
    );
  }
}

async function runGate3IndexAndDeleteSmoke(
  initialFiles: FileRecord[],
  requireFormats: boolean,
): Promise<void> {
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
  if (requireFormats) {
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
  const expectedNames = requireFormats
    ? GATE3_FORMAT_RECORD_NAMES
    : ["gate3-index-smoke.txt"];
  const indexedFileIds = assertGate3IndexSmoke(
    created,
    terminal,
    filesAfterIndex,
    expectedNames,
  );
  process.stdout.write(`gate3_indexed_records=${expectedNames.join(",")}\n`);
  await deleteSmokeFiles(initialFiles, indexedFileIds);
}

async function runGate3ModelUnavailableSmoke(): Promise<void> {
  const inputPath = path.join(
    desktopDataRoot,
    "tmp",
    GATE3_MODEL_UNAVAILABLE_INPUT_NAME,
  );
  await writeFile(
    inputPath,
    "MARA Desktop Gate 3 model unavailable smoke fixture.\n",
    "utf8",
  );
  const created = await sidecar.createIndexTask([inputPath]);
  const terminal = created.ok
    ? await waitForIndexTaskTerminal(created.data.task_id)
    : created;
  assertGate3ModelUnavailableSmoke(created, terminal);
  process.stdout.write(
    "gate3_fault=model_unavailable status=failed retryable=true\n",
  );
}

async function runGate3RetrySmoke(initialFiles: FileRecord[]): Promise<void> {
  const latest = await sidecar.getLatestIndexTask();
  const failedTaskId = assertGate3RetrySource(latest);
  const retried = await sidecar.retryIndexTask(failedTaskId);
  const terminal = retried.ok
    ? await waitForIndexTaskTerminal(retried.data.task_id)
    : retried;
  const filesAfterRetry = await sidecar.listFiles();
  const indexedFileIds = assertGate3IndexSmoke(
    retried,
    terminal,
    filesAfterRetry,
    [GATE3_MODEL_UNAVAILABLE_INPUT_NAME],
  );
  process.stdout.write("gate3_fault_recovery=status_success\n");
  const currentFiles = filesAfterRetry.ok ? filesAfterRetry.data : initialFiles;
  await deleteSmokeFiles(currentFiles, indexedFileIds);
}

async function runGate3PartialFailureSmoke(
  initialFiles: FileRecord[],
): Promise<void> {
  const inputPaths = GATE3_PARTIAL_INPUT_NAMES.map((name) =>
    path.join(desktopDataRoot, "tmp", name),
  );
  await writeFile(
    inputPaths[0],
    "MARA Desktop Gate 3 pre-indexed partial failure fixture.\n",
    "utf8",
  );
  await writeFile(
    inputPaths[1],
    "MARA Desktop Gate 3 successful partial task fixture.\n",
    "utf8",
  );
  const seeded = await sidecar.createIndexTask([inputPaths[0]]);
  const seedTerminal = seeded.ok
    ? await waitForIndexTaskTerminal(seeded.data.task_id)
    : seeded;
  const filesAfterSeed = await sidecar.listFiles();
  assertGate3IndexSmoke(
    seeded,
    seedTerminal,
    filesAfterSeed,
    [GATE3_PARTIAL_INPUT_NAMES[0]],
  );
  const created = await sidecar.createIndexTask(inputPaths);
  const terminal = created.ok
    ? await waitForIndexTaskTerminal(created.data.task_id)
    : created;
  const filesAfterPartial = await sidecar.listFiles();
  const partialTaskId = assertGate3PartialSmoke(
    created,
    terminal,
    filesAfterPartial,
  );
  const retried = await sidecar.retryIndexTask(partialTaskId);
  const retryTerminal = retried.ok
    ? await waitForIndexTaskTerminal(retried.data.task_id)
    : retried;
  const filesAfterRetry = await sidecar.listFiles();
  const indexedFileIds = assertGate3PartialRetrySmoke(
    retried,
    retryTerminal,
    filesAfterRetry,
  );
  process.stdout.write(
    "gate3_partial=duplicate_1 success_1 retry=failed_only_success\n",
  );
  const currentFiles = filesAfterRetry.ok ? filesAfterRetry.data : initialFiles;
  await deleteSmokeFiles(currentFiles, indexedFileIds);
}

async function runGate3SidecarInterruptionSmoke(
  initialFiles: FileRecord[],
): Promise<void> {
  const inputPath = path.join(
    desktopDataRoot,
    "tmp",
    GATE3_INTERRUPTED_INPUT_NAME,
  );
  await writeFile(
    inputPath,
    "MARA Desktop Gate 3 Sidecar interruption smoke fixture.\n",
    "utf8",
  );
  const blockMarker = path.join(
    desktopDataRoot,
    "tmp",
    GATE3_CANCEL_BLOCK_MARKER_NAME,
  );
  const requestMarker = path.join(
    desktopDataRoot,
    "tmp",
    GATE3_CANCEL_REQUEST_MARKER_NAME,
  );
  const created = await sidecar.createIndexTask([inputPath]);
  if (!created.ok) {
    throw new Error(
      `Gate 3 interrupted task creation failed: ${created.error.code}`,
    );
  }
  await waitForSmokeMarker(requestMarker);
  await sidecar.crashForSmoke();
  const failedRuntime = sidecar.getStatus();
  await unlink(blockMarker);
  await unlink(requestMarker);
  const restartedRuntime = await waitForHealthySidecar();
  const latest = await sidecar.getLatestIndexTask();
  const interruptedTaskId = assertGate3InterruptedSmoke(
    created,
    failedRuntime,
    restartedRuntime,
    latest,
  );
  const retried = await sidecar.retryIndexTask(interruptedTaskId);
  const retryTerminal = retried.ok
    ? await waitForIndexTaskTerminal(retried.data.task_id)
    : retried;
  const filesAfterRetry = await sidecar.listFiles();
  const indexedFileIds = assertGate3InterruptedRetrySmoke(
    retried,
    retryTerminal,
    filesAfterRetry,
  );
  process.stdout.write(
    "gate3_sidecar_exit=failed interrupted retry=status_success\n",
  );
  const currentFiles = filesAfterRetry.ok ? filesAfterRetry.data : initialFiles;
  await deleteSmokeFiles(currentFiles, indexedFileIds);
}

async function runGate3LargeFileSmoke(
  initialFiles: FileRecord[],
): Promise<void> {
  const inputPath = path.join(
    desktopDataRoot,
    "tmp",
    GATE3_LARGE_FILE_INPUT_NAME,
  );
  await writeFile(
    inputPath,
    Buffer.alloc(
      GATE3_LARGE_FILE_BYTES,
      "MARA Desktop Gate 3 large file capacity fixture.\n",
    ),
  );
  const indexStartedAt = Date.now();
  const created = await sidecar.createIndexTask([inputPath]);
  const terminal = created.ok
    ? await waitForIndexTaskTerminal(created.data.task_id, 180_000)
    : created;
  const filesAfterIndex = await sidecar.listFiles();
  const indexedFileIds = assertGate3LargeFileSmoke(
    created,
    terminal,
    filesAfterIndex,
  );
  const indexElapsedMs = Date.now() - indexStartedAt;
  const currentFiles = filesAfterIndex.ok ? filesAfterIndex.data : initialFiles;
  const deleteStartedAt = Date.now();
  await deleteSmokeFiles(currentFiles, indexedFileIds);
  const deleteElapsedMs = Date.now() - deleteStartedAt;
  process.stdout.write(
    `gate3_large_file=bytes_${GATE3_LARGE_FILE_BYTES} index_ms=${indexElapsedMs} delete_ms=${deleteElapsedMs} status_success\n`,
  );
}

async function runGate3DiskFullSmoke(
  initialFiles: FileRecord[],
): Promise<void> {
  const inputPath = path.join(
    desktopDataRoot,
    "tmp",
    GATE3_DISK_FULL_INPUT_NAME,
  );
  await writeFile(
    inputPath,
    "MARA Desktop Gate 3 disk-full recovery smoke fixture.\n",
    "utf8",
  );
  const failed = await sidecar.createIndexTask([inputPath]);
  assertGate3DiskFullSmoke(failed);
  const recovered = await sidecar.createIndexTask([inputPath]);
  const terminal = recovered.ok
    ? await waitForIndexTaskTerminal(recovered.data.task_id)
    : recovered;
  const filesAfterRecovery = await sidecar.listFiles();
  const indexedFileIds = assertGate3IndexSmoke(
    recovered,
    terminal,
    filesAfterRecovery,
    [GATE3_DISK_FULL_INPUT_NAME],
  );
  process.stdout.write(
    "gate3_storage_fault=disk_full status=failed retry=status_success\n",
  );
  const currentFiles = filesAfterRecovery.ok
    ? filesAfterRecovery.data
    : initialFiles;
  await deleteSmokeFiles(currentFiles, indexedFileIds);
}

async function runGate3DatabaseLockSmoke(
  initialFiles: FileRecord[],
): Promise<void> {
  const inputPath = path.join(
    desktopDataRoot,
    "tmp",
    GATE3_DATABASE_LOCKED_INPUT_NAME,
  );
  await writeFile(
    inputPath,
    "MARA Desktop Gate 3 database-lock recovery smoke fixture.\n",
    "utf8",
  );
  const created = await sidecar.createIndexTask([inputPath]);
  const failed = created.ok
    ? await waitForIndexTaskTerminal(created.data.task_id)
    : created;
  const failedTaskId = assertGate3DatabaseLockedSmoke(created, failed);
  const retried = await sidecar.retryIndexTask(failedTaskId);
  const terminal = retried.ok
    ? await waitForIndexTaskTerminal(retried.data.task_id)
    : retried;
  const filesAfterRecovery = await sidecar.listFiles();
  const indexedFileIds = assertGate3IndexSmoke(
    retried,
    terminal,
    filesAfterRecovery,
    [GATE3_DATABASE_LOCKED_INPUT_NAME],
  );
  process.stdout.write(
    "gate3_storage_fault=database_locked status=failed retry=status_success\n",
  );
  const currentFiles = filesAfterRecovery.ok
    ? filesAfterRecovery.data
    : initialFiles;
  await deleteSmokeFiles(currentFiles, indexedFileIds);
}

async function runGate3CancellationSmoke(
  initialFiles: FileRecord[],
): Promise<void> {
  const inputPaths = GATE3_CANCEL_INPUT_NAMES.map((name) =>
    path.join(desktopDataRoot, "tmp", name),
  );
  for (const inputPath of inputPaths) {
    await writeFile(
      inputPath,
      "MARA Desktop Gate 3 cancellation smoke fixture.\n",
      "utf8",
    );
  }
  const blockMarker = path.join(
    desktopDataRoot,
    "tmp",
    GATE3_CANCEL_BLOCK_MARKER_NAME,
  );
  const requestMarker = path.join(
    desktopDataRoot,
    "tmp",
    GATE3_CANCEL_REQUEST_MARKER_NAME,
  );
  const created = await sidecar.createIndexTask(inputPaths);
  if (!created.ok) {
    throw new Error(`Gate 3 cancel task creation failed: ${created.error.code}`);
  }
  await waitForSmokeMarker(requestMarker);
  const cancelling = await sidecar.cancelIndexTask(created.data.task_id);
  await unlink(blockMarker);
  const terminal = await waitForIndexTaskTerminal(created.data.task_id);
  await unlink(requestMarker);
  const filesAfterCancel = await sidecar.listFiles();
  assertGate3CancellationSmoke(
    created,
    cancelling,
    terminal,
    filesAfterCancel,
  );
  const retried = await sidecar.retryIndexTask(created.data.task_id);
  const retryTerminal = retried.ok
    ? await waitForIndexTaskTerminal(retried.data.task_id)
    : retried;
  const filesAfterRetry = await sidecar.listFiles();
  const indexedFileIds = assertGate3CancelRetrySmoke(
    retried,
    retryTerminal,
    filesAfterRetry,
  );
  process.stdout.write(
    "gate3_cancel=cancelled_at_file_boundary retry=status_success\n",
  );
  const currentFiles = filesAfterRetry.ok ? filesAfterRetry.data : initialFiles;
  await deleteSmokeFiles(currentFiles, indexedFileIds);
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
  const requireGate3ModelUnavailable = process.argv.includes(
    "--smoke-test-gate3-model-unavailable",
  );
  const requireGate3Retry = process.argv.includes("--smoke-test-gate3-retry");
  const requireGate3Cancellation = process.argv.includes(
    "--smoke-test-gate3-cancel",
  );
  const requireGate3Partial = process.argv.includes(
    "--smoke-test-gate3-partial",
  );
  const requireGate3SidecarExit = process.argv.includes(
    "--smoke-test-gate3-sidecar-exit",
  );
  const requireGate3LargeFile = process.argv.includes(
    "--smoke-test-gate3-large-file",
  );
  const requireGate3Delete =
    process.argv.includes("--smoke-test-gate3") || requireGate3Formats;
  const requireNonEmptyFixture =
    process.argv.includes("--smoke-test-nonempty") ||
    requireGate3Delete ||
    requireGate3ModelUnavailable ||
    requireGate3Retry ||
    requireGate3Cancellation ||
    requireGate3Partial ||
    requireGate3SidecarExit ||
    requireGate3DiskFull ||
    requireGate3DatabaseLock ||
    requireGate3LargeFile;
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
      const initialFiles = files.ok ? files.data : [];
      if (requireGate3ModelUnavailable) {
        await runGate3ModelUnavailableSmoke();
      } else if (requireGate3Retry) {
        await runGate3RetrySmoke(initialFiles);
      } else if (requireGate3Partial) {
        await runGate3PartialFailureSmoke(initialFiles);
      } else if (requireGate3SidecarExit) {
        await runGate3SidecarInterruptionSmoke(initialFiles);
      } else if (requireGate3DiskFull) {
        await runGate3DiskFullSmoke(initialFiles);
      } else if (requireGate3DatabaseLock) {
        await runGate3DatabaseLockSmoke(initialFiles);
      } else if (requireGate3LargeFile) {
        await runGate3LargeFileSmoke(initialFiles);
      } else if (requireGate3Cancellation) {
        await runGate3CancellationSmoke(initialFiles);
      } else if (requireGate3Delete) {
        await runGate3IndexAndDeleteSmoke(initialFiles, requireGate3Formats);
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

import { readFile } from "node:fs/promises";
import path from "node:path";

import {
  app,
  BrowserWindow,
  ipcMain,
  protocol,
  session,
  type IpcMainInvokeEvent,
} from "electron";

import { contentTypeFor, resolveAppAsset } from "./protocol";
import { RuntimeStatus, SidecarManager } from "./sidecar-manager";

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

const sidecar = new SidecarManager({
  appPath: app.getAppPath(),
  isPackaged: app.isPackaged,
  resourcesPath: process.resourcesPath,
  onStatus: (status) => broadcastRuntimeStatus(status),
});

function broadcastRuntimeStatus(status: RuntimeStatus): void {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("runtime:status", status);
  }
}

function trustedSender(event: IpcMainInvokeEvent): boolean {
  return event.senderFrame?.url.startsWith("mara://app/") ?? false;
}

function registerIpc(): void {
  ipcMain.handle("runtime:get-status", (event) => {
    if (!trustedSender(event)) {
      throw new Error("Untrusted IPC sender");
    }
    return sidecar.getStatus();
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
  createWindow();
  const status = await sidecar.start();
  if (process.argv.includes("--smoke-test")) {
    if (status.state !== "healthy") {
      process.exitCode = 1;
    }
    app.quit();
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

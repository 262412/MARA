import { contextBridge, ipcRenderer } from "electron";

import type { RuntimeStatus } from "./sidecar-manager";

contextBridge.exposeInMainWorld("maraDesktop", {
  getRuntimeStatus: (): Promise<RuntimeStatus> =>
    ipcRenderer.invoke("runtime:get-status"),
  onRuntimeStatus: (listener: (status: RuntimeStatus) => void): (() => void) => {
    const handler = (_event: Electron.IpcRendererEvent, status: RuntimeStatus) => {
      listener(status);
    };
    ipcRenderer.on("runtime:status", handler);
    return () => ipcRenderer.removeListener("runtime:status", handler);
  },
  platform: process.platform,
});

import { contextBridge, ipcRenderer } from "electron";

import type { DoctorPayload } from "../shared/doctor-contracts";
import type { FileRecord } from "../shared/file-contracts";
import type {
  DesktopResult,
  RuntimeStatus,
} from "../shared/runtime-contracts";
import type { SessionSummary } from "../shared/session-contracts";

contextBridge.exposeInMainWorld("desktop", {
  getRuntimeStatus: (): Promise<RuntimeStatus> =>
    ipcRenderer.invoke("desktop:get-runtime-status"),
  getDoctor: (): Promise<DesktopResult<DoctorPayload>> =>
    ipcRenderer.invoke("desktop:get-doctor"),
  listFiles: (): Promise<DesktopResult<FileRecord[]>> =>
    ipcRenderer.invoke("desktop:list-files"),
  listSessions: (): Promise<DesktopResult<SessionSummary[]>> =>
    ipcRenderer.invoke("desktop:list-sessions"),
  onRuntimeStatus: (listener: (status: RuntimeStatus) => void): (() => void) => {
    const handler = (_event: Electron.IpcRendererEvent, status: RuntimeStatus) => {
      listener(status);
    };
    ipcRenderer.on("runtime:status", handler);
    return () => ipcRenderer.removeListener("runtime:status", handler);
  },
  platform: process.platform,
});

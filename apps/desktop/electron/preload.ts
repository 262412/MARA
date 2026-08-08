import { contextBridge, ipcRenderer } from "electron";

import type { DoctorPayload } from "../shared/doctor-contracts";
import type { FileRecord } from "../shared/file-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
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
  importFiles: (): Promise<DesktopResult<IndexTask | null>> =>
    ipcRenderer.invoke("desktop:import-files"),
  getLatestIndexTask: (): Promise<DesktopResult<IndexTask | null>> =>
    ipcRenderer.invoke("desktop:get-latest-index-task"),
  cancelIndexTask: (taskId: string): Promise<DesktopResult<IndexTask>> =>
    ipcRenderer.invoke("desktop:cancel-index-task", taskId),
  retryIndexTask: (taskId: string): Promise<DesktopResult<IndexTask>> =>
    ipcRenderer.invoke("desktop:retry-index-task", taskId),
  deleteFile: (fileId: string): Promise<DesktopResult<string[]>> =>
    ipcRenderer.invoke("desktop:delete-file", fileId),
  deleteFiles: (fileIds: string[]): Promise<DesktopResult<string[]>> =>
    ipcRenderer.invoke("desktop:delete-files", fileIds),
  onRuntimeStatus: (listener: (status: RuntimeStatus) => void): (() => void) => {
    const handler = (_event: Electron.IpcRendererEvent, status: RuntimeStatus) => {
      listener(status);
    };
    ipcRenderer.on("runtime:status", handler);
    return () => ipcRenderer.removeListener("runtime:status", handler);
  },
  onIndexTaskStatus: (listener: (task: IndexTask) => void): (() => void) => {
    const handler = (_event: Electron.IpcRendererEvent, task: IndexTask) => {
      listener(task);
    };
    ipcRenderer.on("index-task:status", handler);
    return () => ipcRenderer.removeListener("index-task:status", handler);
  },
  platform: process.platform,
});

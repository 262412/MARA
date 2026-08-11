import { contextBridge, ipcRenderer, webUtils } from "electron";

import type { DoctorPayload } from "../shared/doctor-contracts";
import type { FileRecord } from "../shared/file-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
import type {
  ModelSettingsInput,
  ModelSettingsStatus,
} from "../shared/model-contracts";
import type {
  QueryTask,
  QueryTaskCreateRequest,
} from "../shared/query-contracts";
import type {
  DesktopResult,
  RuntimeStatus,
} from "../shared/runtime-contracts";
import type {
  SessionDetail,
  SessionSummary,
} from "../shared/session-contracts";
import { resolveDroppedFilePaths } from "./dropped-file-import";

contextBridge.exposeInMainWorld("desktop", {
  getRuntimeStatus: (): Promise<RuntimeStatus> =>
    ipcRenderer.invoke("desktop:get-runtime-status"),
  getDoctor: (): Promise<DesktopResult<DoctorPayload>> =>
    ipcRenderer.invoke("desktop:get-doctor"),
  listFiles: (): Promise<DesktopResult<FileRecord[]>> =>
    ipcRenderer.invoke("desktop:list-files"),
  listSessions: (): Promise<DesktopResult<SessionSummary[]>> =>
    ipcRenderer.invoke("desktop:list-sessions"),
  getSession: (conversationId: string): Promise<DesktopResult<SessionDetail>> =>
    ipcRenderer.invoke("desktop:get-session", conversationId),
  createSession: (): Promise<DesktopResult<SessionDetail>> =>
    ipcRenderer.invoke("desktop:create-session"),
  renameSession: (
    conversationId: string,
    name: string,
  ): Promise<DesktopResult<SessionDetail>> =>
    ipcRenderer.invoke("desktop:rename-session", conversationId, name),
  deleteSession: (conversationId: string): Promise<DesktopResult<string>> =>
    ipcRenderer.invoke("desktop:delete-session", conversationId),
  importFiles: (): Promise<DesktopResult<IndexTask | null>> =>
    ipcRenderer.invoke("desktop:import-files"),
  importDroppedFiles: (files: File[]): Promise<DesktopResult<IndexTask>> => {
    const filePaths = resolveDroppedFilePaths(files, (file) =>
      webUtils.getPathForFile(file),
    );
    return ipcRenderer.invoke("desktop:import-dropped-files", filePaths);
  },
  openEmbeddingConfiguration: (): Promise<DesktopResult<boolean>> =>
    ipcRenderer.invoke("desktop:open-embedding-configuration"),
  getModelSettings: (): Promise<DesktopResult<ModelSettingsStatus>> =>
    ipcRenderer.invoke("desktop:get-model-settings"),
  saveModelSettings: (
    settings: ModelSettingsInput,
  ): Promise<DesktopResult<ModelSettingsStatus>> =>
    ipcRenderer.invoke("desktop:save-model-settings", settings),
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
  submitQuestion: (
    payload: QueryTaskCreateRequest,
  ): Promise<DesktopResult<QueryTask>> =>
    ipcRenderer.invoke("desktop:submit-question", payload),
  getLatestAnswerTask: (): Promise<DesktopResult<QueryTask | null>> =>
    ipcRenderer.invoke("desktop:get-latest-answer-task"),
  cancelAnswer: (taskId: string): Promise<DesktopResult<QueryTask>> =>
    ipcRenderer.invoke("desktop:cancel-answer", taskId),
  retryAnswer: (taskId: string): Promise<DesktopResult<QueryTask>> =>
    ipcRenderer.invoke("desktop:retry-answer", taskId),
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
  onAnswerTaskStatus: (listener: (task: QueryTask) => void): (() => void) => {
    const handler = (_event: Electron.IpcRendererEvent, task: QueryTask) => {
      listener(task);
    };
    ipcRenderer.on("answer-task:status", handler);
    return () => ipcRenderer.removeListener("answer-task:status", handler);
  },
  platform: process.platform,
});

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

type DesktopBridge = {
  getRuntimeStatus(): Promise<RuntimeStatus>;
  getDoctor(): Promise<DesktopResult<DoctorPayload>>;
  listFiles(): Promise<DesktopResult<FileRecord[]>>;
  listSessions(): Promise<DesktopResult<SessionSummary[]>>;
  getSession(conversationId: string): Promise<DesktopResult<SessionDetail>>;
  createSession(): Promise<DesktopResult<SessionDetail>>;
  renameSession(
    conversationId: string,
    name: string,
  ): Promise<DesktopResult<SessionDetail>>;
  deleteSession(conversationId: string): Promise<DesktopResult<string>>;
  importFiles(): Promise<DesktopResult<IndexTask | null>>;
  importDroppedFiles(files: File[]): Promise<DesktopResult<IndexTask>>;
  openEmbeddingConfiguration(): Promise<DesktopResult<boolean>>;
  getModelSettings(): Promise<DesktopResult<ModelSettingsStatus>>;
  saveModelSettings(
    settings: ModelSettingsInput,
  ): Promise<DesktopResult<ModelSettingsStatus>>;
  getLatestIndexTask(): Promise<DesktopResult<IndexTask | null>>;
  cancelIndexTask(taskId: string): Promise<DesktopResult<IndexTask>>;
  retryIndexTask(taskId: string): Promise<DesktopResult<IndexTask>>;
  deleteFile(fileId: string): Promise<DesktopResult<string[]>>;
  deleteFiles(fileIds: string[]): Promise<DesktopResult<string[]>>;
  submitQuestion(payload: QueryTaskCreateRequest): Promise<DesktopResult<QueryTask>>;
  getLatestAnswerTask(): Promise<DesktopResult<QueryTask | null>>;
  cancelAnswer(taskId: string): Promise<DesktopResult<QueryTask>>;
  retryAnswer(taskId: string): Promise<DesktopResult<QueryTask>>;
  onRuntimeStatus(listener: (status: RuntimeStatus) => void): () => void;
  onIndexTaskStatus(listener: (task: IndexTask) => void): () => void;
  onAnswerTaskStatus(listener: (task: QueryTask) => void): () => void;
  platform: NodeJS.Platform;
};

declare global {
  interface Window {
    desktop?: DesktopBridge;
  }
}

export {};

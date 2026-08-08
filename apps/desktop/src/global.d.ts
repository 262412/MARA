import type { DoctorPayload } from "../shared/doctor-contracts";
import type { FileRecord } from "../shared/file-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
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
  importFiles(): Promise<DesktopResult<IndexTask | null>>;
  importDroppedFiles(files: File[]): Promise<DesktopResult<IndexTask>>;
  getLatestIndexTask(): Promise<DesktopResult<IndexTask | null>>;
  cancelIndexTask(taskId: string): Promise<DesktopResult<IndexTask>>;
  retryIndexTask(taskId: string): Promise<DesktopResult<IndexTask>>;
  deleteFile(fileId: string): Promise<DesktopResult<string[]>>;
  deleteFiles(fileIds: string[]): Promise<DesktopResult<string[]>>;
  onRuntimeStatus(listener: (status: RuntimeStatus) => void): () => void;
  onIndexTaskStatus(listener: (task: IndexTask) => void): () => void;
  platform: NodeJS.Platform;
};

declare global {
  interface Window {
    desktop?: DesktopBridge;
  }
}

export {};

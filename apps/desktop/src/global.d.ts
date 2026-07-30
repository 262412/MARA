import type { DoctorPayload } from "../shared/doctor-contracts";
import type { FileRecord } from "../shared/file-contracts";
import type {
  DesktopResult,
  RuntimeStatus,
} from "../shared/runtime-contracts";
import type { SessionSummary } from "../shared/session-contracts";

type DesktopBridge = {
  getRuntimeStatus(): Promise<RuntimeStatus>;
  getDoctor(): Promise<DesktopResult<DoctorPayload>>;
  listFiles(): Promise<DesktopResult<FileRecord[]>>;
  listSessions(): Promise<DesktopResult<SessionSummary[]>>;
  onRuntimeStatus(listener: (status: RuntimeStatus) => void): () => void;
  platform: NodeJS.Platform;
};

declare global {
  interface Window {
    desktop?: DesktopBridge;
  }
}

export {};

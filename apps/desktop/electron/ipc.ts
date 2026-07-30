import type {
  DoctorPayload,
} from "../shared/doctor-contracts";
import type { FileRecord } from "../shared/file-contracts";
import type {
  DesktopResult,
  RuntimeStatus,
} from "../shared/runtime-contracts";
import type { SessionSummary } from "../shared/session-contracts";
import type { IpcMain } from "electron";

type IpcEvent = {
  senderFrame?: {
    url: string;
  } | null;
};
type IpcHandler<T> = (event: IpcEvent, ...args: unknown[]) => Promise<T>;

export type DesktopIpcOperations = {
  getRuntimeStatus(): RuntimeStatus;
  getDoctor(): Promise<DesktopResult<DoctorPayload>>;
  listFiles(): Promise<DesktopResult<FileRecord[]>>;
  listSessions(): Promise<DesktopResult<SessionSummary[]>>;
};

export function createTrustedIpcHandler<T>(
  operation: () => T | Promise<T>,
): IpcHandler<T> {
  return async (event, ...args) => {
    if (!event.senderFrame?.url.startsWith("mara://app/")) {
      throw new Error("Untrusted IPC sender");
    }
    if (args.length !== 0) {
      throw new Error("Desktop IPC method does not accept arguments");
    }
    return operation();
  };
}

export function registerDesktopIpc(
  registrar: IpcMain,
  operations: DesktopIpcOperations,
): void {
  registrar.handle(
    "desktop:get-runtime-status",
    createTrustedIpcHandler(() => operations.getRuntimeStatus()),
  );
  registrar.handle(
    "desktop:get-doctor",
    createTrustedIpcHandler(() => operations.getDoctor()),
  );
  registrar.handle(
    "desktop:list-files",
    createTrustedIpcHandler(() => operations.listFiles()),
  );
  registrar.handle(
    "desktop:list-sessions",
    createTrustedIpcHandler(() => operations.listSessions()),
  );
}

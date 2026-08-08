import type {
  DoctorPayload,
} from "../shared/doctor-contracts";
import type { FileRecord } from "../shared/file-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
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
  importFiles(): Promise<DesktopResult<IndexTask | null>>;
  getLatestIndexTask(): Promise<DesktopResult<IndexTask | null>>;
  cancelIndexTask(taskId: string): Promise<DesktopResult<IndexTask>>;
  retryIndexTask(taskId: string): Promise<DesktopResult<IndexTask>>;
  deleteFile(fileId: string): Promise<DesktopResult<string[]>>;
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

export function createTrustedIdentifierIpcHandler<T>(
  operation: (identifier: string) => T | Promise<T>,
): IpcHandler<T> {
  return async (event, ...args) => {
    if (!event.senderFrame?.url.startsWith("mara://app/")) {
      throw new Error("Untrusted IPC sender");
    }
    if (args.length !== 1 || typeof args[0] !== "string") {
      throw new Error("Desktop IPC method requires exactly one identifier");
    }
    const identifier = args[0];
    if (!/^[A-Za-z0-9._-]{1,128}$/.test(identifier)) {
      throw new Error("Desktop IPC received an invalid identifier");
    }
    return operation(identifier);
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
  registrar.handle(
    "desktop:import-files",
    createTrustedIpcHandler(() => operations.importFiles()),
  );
  registrar.handle(
    "desktop:get-latest-index-task",
    createTrustedIpcHandler(() => operations.getLatestIndexTask()),
  );
  registrar.handle(
    "desktop:cancel-index-task",
    createTrustedIdentifierIpcHandler((taskId) =>
      operations.cancelIndexTask(taskId),
    ),
  );
  registrar.handle(
    "desktop:retry-index-task",
    createTrustedIdentifierIpcHandler((taskId) =>
      operations.retryIndexTask(taskId),
    ),
  );
  registrar.handle(
    "desktop:delete-file",
    createTrustedIdentifierIpcHandler((fileId) => operations.deleteFile(fileId)),
  );
}

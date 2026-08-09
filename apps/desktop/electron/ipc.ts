import path from "node:path";

import type { IpcMain } from "electron";

import type { DoctorPayload } from "../shared/doctor-contracts";
import type { FileRecord } from "../shared/file-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
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
  getSession(conversationId: string): Promise<DesktopResult<SessionDetail>>;
  createSession(): Promise<DesktopResult<SessionDetail>>;
  renameSession(
    conversationId: string,
    name: string,
  ): Promise<DesktopResult<SessionDetail>>;
  deleteSession(conversationId: string): Promise<DesktopResult<string>>;
  importFiles(): Promise<DesktopResult<IndexTask | null>>;
  importDroppedFiles(filePaths: string[]): Promise<DesktopResult<IndexTask>>;
  getLatestIndexTask(): Promise<DesktopResult<IndexTask | null>>;
  cancelIndexTask(taskId: string): Promise<DesktopResult<IndexTask>>;
  retryIndexTask(taskId: string): Promise<DesktopResult<IndexTask>>;
  deleteFile(fileId: string): Promise<DesktopResult<string[]>>;
  deleteFiles(fileIds: string[]): Promise<DesktopResult<string[]>>;
  submitQuestion(payload: QueryTaskCreateRequest): Promise<DesktopResult<QueryTask>>;
  getLatestAnswerTask(): Promise<DesktopResult<QueryTask | null>>;
  cancelAnswer(taskId: string): Promise<DesktopResult<QueryTask>>;
  retryAnswer(taskId: string): Promise<DesktopResult<QueryTask>>;
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

export function createTrustedIdentifierListIpcHandler<T>(
  operation: (identifiers: string[]) => T | Promise<T>,
): IpcHandler<T> {
  return async (event, ...args) => {
    if (!event.senderFrame?.url.startsWith("mara://app/")) {
      throw new Error("Untrusted IPC sender");
    }
    if (
      args.length !== 1 ||
      !Array.isArray(args[0]) ||
      args[0].length === 0 ||
      args[0].length > 1_000
    ) {
      throw new Error("Desktop IPC requires one non-empty identifier list");
    }
    const identifiers = args[0];
    if (
      identifiers.some(
        (identifier) =>
          typeof identifier !== "string" ||
          !/^[A-Za-z0-9._-]{1,128}$/.test(identifier),
      ) ||
      new Set(identifiers).size !== identifiers.length
    ) {
      throw new Error("Desktop IPC received an invalid identifier list");
    }
    return operation(identifiers);
  };
}

export function createTrustedSessionRenameIpcHandler<T>(
  operation: (conversationId: string, name: string) => T | Promise<T>,
): IpcHandler<T> {
  return async (event, ...args) => {
    if (!event.senderFrame?.url.startsWith("mara://app/")) {
      throw new Error("Untrusted IPC sender");
    }
    if (
      args.length !== 2 ||
      typeof args[0] !== "string" ||
      typeof args[1] !== "string"
    ) {
      throw new Error(
        "Desktop IPC requires exactly one identifier and one name",
      );
    }
    const [conversationId, rawName] = args;
    const name = rawName.trim();
    if (
      !/^[A-Za-z0-9._-]{1,128}$/.test(conversationId) ||
      name.length === 0 ||
      Array.from(name).length > 200
    ) {
      throw new Error("Desktop IPC received an invalid session rename");
    }
    return operation(conversationId, name);
  };
}

export function createTrustedQuestionIpcHandler<T>(
  operation: (payload: QueryTaskCreateRequest) => T | Promise<T>,
): IpcHandler<T> {
  return async (event, ...args) => {
    if (!event.senderFrame?.url.startsWith("mara://app/")) {
      throw new Error("Untrusted IPC sender");
    }
    if (args.length !== 1 || !args[0] || typeof args[0] !== "object") {
      throw new Error("Desktop IPC received an invalid question");
    }
    const payload = args[0] as Record<string, unknown>;
    const keys = Object.keys(payload).sort();
    const prompt = typeof payload.prompt === "string" ? payload.prompt.trim() : "";
    const selectedFileIds = payload.selected_file_ids;
    if (
      keys.join(",") !== "conversation_id,prompt,selected_file_ids" ||
      typeof payload.conversation_id !== "string" ||
      !/^[A-Za-z0-9._-]{1,128}$/.test(payload.conversation_id) ||
      prompt.length === 0 ||
      Array.from(prompt).length > 20_000 ||
      !Array.isArray(selectedFileIds) ||
      selectedFileIds.length === 0 ||
      selectedFileIds.length > 1_000 ||
      selectedFileIds.some(
        (fileId) =>
          typeof fileId !== "string" ||
          !/^[A-Za-z0-9._-]{1,128}$/.test(fileId),
      ) ||
      new Set(selectedFileIds).size !== selectedFileIds.length
    ) {
      throw new Error("Desktop IPC received an invalid question");
    }
    return operation({
      conversation_id: payload.conversation_id,
      prompt,
      selected_file_ids: selectedFileIds,
    });
  };
}

export function createTrustedPathListIpcHandler<T>(
  operation: (filePaths: string[]) => T | Promise<T>,
): IpcHandler<T> {
  return async (event, ...args) => {
    if (!event.senderFrame?.url.startsWith("mara://app/")) {
      throw new Error("Untrusted IPC sender");
    }
    if (
      args.length !== 1 ||
      !Array.isArray(args[0]) ||
      args[0].length === 0 ||
      args[0].length > 64
    ) {
      throw new Error("Desktop IPC requires one non-empty file list");
    }
    const filePaths = args[0];
    if (
      filePaths.some(
        (filePath) =>
          typeof filePath !== "string" ||
          !path.isAbsolute(filePath) ||
          filePath.includes("\0") ||
          filePath.length > 32_768,
      ) ||
      new Set(filePaths).size !== filePaths.length
    ) {
      throw new Error("Desktop IPC received an invalid file list");
    }
    return operation(filePaths);
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
    "desktop:get-session",
    createTrustedIdentifierIpcHandler((conversationId) =>
      operations.getSession(conversationId),
    ),
  );
  registrar.handle(
    "desktop:create-session",
    createTrustedIpcHandler(() => operations.createSession()),
  );
  registrar.handle(
    "desktop:rename-session",
    createTrustedSessionRenameIpcHandler((conversationId, name) =>
      operations.renameSession(conversationId, name),
    ),
  );
  registrar.handle(
    "desktop:delete-session",
    createTrustedIdentifierIpcHandler((conversationId) =>
      operations.deleteSession(conversationId),
    ),
  );
  registrar.handle(
    "desktop:import-files",
    createTrustedIpcHandler(() => operations.importFiles()),
  );
  registrar.handle(
    "desktop:import-dropped-files",
    createTrustedPathListIpcHandler((filePaths) =>
      operations.importDroppedFiles(filePaths),
    ),
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
  registrar.handle(
    "desktop:delete-files",
    createTrustedIdentifierListIpcHandler((fileIds) =>
      operations.deleteFiles(fileIds),
    ),
  );
  registrar.handle(
    "desktop:submit-question",
    createTrustedQuestionIpcHandler((payload) =>
      operations.submitQuestion(payload),
    ),
  );
  registrar.handle(
    "desktop:get-latest-answer-task",
    createTrustedIpcHandler(() => operations.getLatestAnswerTask()),
  );
  registrar.handle(
    "desktop:cancel-answer",
    createTrustedIdentifierIpcHandler((taskId) =>
      operations.cancelAnswer(taskId),
    ),
  );
  registrar.handle(
    "desktop:retry-answer",
    createTrustedIdentifierIpcHandler((taskId) =>
      operations.retryAnswer(taskId),
    ),
  );
}

import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomBytes, randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import path from "node:path";

import type {
  DoctorPayload,
  DoctorResponse,
} from "../shared/doctor-contracts";
import type {
  FileBatchDeleteRequest,
  FileDeleteResponse,
  FileListResponse,
  FileRecord,
  ImportCapabilities,
  ImportCapabilitiesResponse,
} from "../shared/file-contracts";
import type {
  IndexTask,
  IndexTaskResponse,
  LatestIndexTaskResponse,
} from "../shared/index-task-contracts";
import {
  SIDECAR_PROTOCOL_VERSION,
  type DesktopResult,
  type RuntimeStatus,
  type SidecarError,
} from "../shared/runtime-contracts";
import type {
  SessionListResponse,
  SessionSummary,
} from "../shared/session-contracts";

export type SidecarReadyMessage = {
  type: "ready";
  protocol: number;
  port: number;
  pid: number;
};

type SidecarManagerOptions = {
  appPath: string;
  dataRoot: string;
  isPackaged: boolean;
  resourcesPath: string;
  smokeFault?: "disk_full" | "database_locked";
  onStatus?: (status: RuntimeStatus) => void;
};

class SidecarRequestFailure extends Error {
  constructor(readonly contract: SidecarError) {
    super(contract.message);
  }
}

function sidecarNotReadyFailure(): SidecarRequestFailure {
  return new SidecarRequestFailure({
    code: "sidecar_not_ready",
    message: "The MARA Sidecar is not ready.",
    details: null,
    retryable: true,
    request_id: randomUUID(),
  });
}

const SIDECAR_RESTART_DELAYS_MS = [250, 500, 1_000] as const;
const DEFAULT_REQUEST_TIMEOUT_MS = 30_000;
const FILE_DELETE_TIMEOUT_MS = 300_000;

export function sidecarRestartDelay(attempt: number): number | undefined {
  return SIDECAR_RESTART_DELAYS_MS[attempt];
}

export function sidecarRequestTimeout(
  pathname: string,
  method = "GET",
): number {
  return (method === "DELETE" && pathname.startsWith("/v1/files/")) ||
    (method === "POST" && pathname === "/v1/file-deletions")
    ? FILE_DELETE_TIMEOUT_MS
    : DEFAULT_REQUEST_TIMEOUT_MS;
}

export function batchFileDeleteRequest(
  fileIds: string[],
  idempotencyKey: string,
): RequestInit {
  const payload: FileBatchDeleteRequest = { file_ids: fileIds };
  return {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify(payload),
  };
}

export async function waitForRequestReadiness(
  getStatus: () => RuntimeStatus,
  startup?: Promise<RuntimeStatus>,
): Promise<void> {
  if (startup) {
    await startup;
  }
  if (getStatus().state !== "healthy") {
    throw sidecarNotReadyFailure();
  }
}

export function parseReadyMessage(line: string): SidecarReadyMessage {
  const value: unknown = JSON.parse(line);
  if (!value || typeof value !== "object") {
    throw new Error("Sidecar ready message must be an object");
  }

  const message = value as Record<string, unknown>;
  if (
    message.type !== "ready" ||
    message.protocol !== SIDECAR_PROTOCOL_VERSION ||
    !Number.isInteger(message.port) ||
    Number(message.port) < 1024 ||
    Number(message.port) > 65535 ||
    !Number.isInteger(message.pid) ||
    Number(message.pid) <= 0
  ) {
    throw new Error("Sidecar ready message is invalid or incompatible");
  }
  return message as SidecarReadyMessage;
}

export function parseIndexTaskEvent(
  block: string,
  expectedRequestId?: string,
): IndexTask {
  const lines = block.split(/\r?\n/);
  if (!lines.includes("event: task")) {
    throw new Error("Sidecar task stream returned an unexpected event");
  }
  const data = lines
    .filter((line) => line.startsWith("data: "))
    .map((line) => line.slice(6))
    .join("\n");
  const payload: unknown = JSON.parse(data);
  if (!isIndexTaskResponse(payload)) {
    throw new Error("Sidecar task stream returned an invalid task response");
  }
  if (expectedRequestId && payload.request_id !== expectedRequestId) {
    throw new Error("Sidecar task stream returned a mismatched response");
  }
  return payload.task;
}

export class SidecarManager {
  private child?: ChildProcessWithoutNullStreams;
  private token?: string;
  private port?: number;
  private startup?: Promise<RuntimeStatus>;
  private restartTimer?: ReturnType<typeof setTimeout>;
  private restartAttempts = 0;
  private stopping = false;
  private status: RuntimeStatus = {
    state: "stopped",
    protocol: SIDECAR_PROTOCOL_VERSION,
    capabilities: [],
  };

  constructor(private readonly options: SidecarManagerOptions) {}

  getStatus(): RuntimeStatus {
    return { ...this.status, capabilities: [...this.status.capabilities] };
  }

  async getDoctor(): Promise<DesktopResult<DoctorPayload>> {
    return this.runRequest(async () => {
      await waitForRequestReadiness(() => this.getStatus(), this.startup);
      const response = await this.requestJson<DoctorResponse>("/v1/doctor", {}, true);
      return response.doctor;
    });
  }

  async listFiles(): Promise<DesktopResult<FileRecord[]>> {
    return this.runRequest(async () => {
      await waitForRequestReadiness(() => this.getStatus(), this.startup);
      const response = await this.requestJson<FileListResponse>("/v1/files", {}, true);
      return response.files;
    });
  }

  async getImportCapabilities(): Promise<DesktopResult<ImportCapabilities>> {
    return this.runRequest(async () => {
      await waitForRequestReadiness(() => this.getStatus(), this.startup);
      const response = await this.requestJson<ImportCapabilitiesResponse>(
        "/v1/import-capabilities",
        {},
        true,
      );
      return response.import_capabilities;
    });
  }

  async listSessions(): Promise<DesktopResult<SessionSummary[]>> {
    return this.runRequest(async () => {
      await waitForRequestReadiness(() => this.getStatus(), this.startup);
      const response = await this.requestJson<SessionListResponse>(
        "/v1/sessions",
        {},
        true,
      );
      return response.sessions;
    });
  }

  async createIndexTask(paths: string[]): Promise<DesktopResult<IndexTask>> {
    return this.runRequest(async () => {
      await waitForRequestReadiness(() => this.getStatus(), this.startup);
      const response = await this.requestJson<IndexTaskResponse>(
        "/v1/index-tasks",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": randomUUID(),
          },
          body: JSON.stringify({ paths, reindex: false }),
        },
        true,
      );
      return response.task;
    });
  }

  async getIndexTask(taskId: string): Promise<DesktopResult<IndexTask>> {
    return this.runRequest(async () => {
      await waitForRequestReadiness(() => this.getStatus(), this.startup);
      const response = await this.requestJson<IndexTaskResponse>(
        `/v1/index-tasks/${encodeURIComponent(taskId)}`,
        {},
        true,
      );
      return response.task;
    });
  }

  async getLatestIndexTask(): Promise<DesktopResult<IndexTask | null>> {
    return this.runRequest(async () => {
      await waitForRequestReadiness(() => this.getStatus(), this.startup);
      const response = await this.requestJson<LatestIndexTaskResponse>(
        "/v1/index-tasks/latest",
        {},
        true,
      );
      return response.task;
    });
  }

  async cancelIndexTask(taskId: string): Promise<DesktopResult<IndexTask>> {
    return this.mutateIndexTask(taskId, "cancel");
  }

  async retryIndexTask(taskId: string): Promise<DesktopResult<IndexTask>> {
    return this.mutateIndexTask(taskId, "retry", true);
  }

  async deleteFile(fileId: string): Promise<DesktopResult<string[]>> {
    return this.runRequest(async () => {
      await waitForRequestReadiness(() => this.getStatus(), this.startup);
      const response = await this.requestJson<FileDeleteResponse>(
        `/v1/files/${encodeURIComponent(fileId)}`,
        {
          method: "DELETE",
          headers: { "Idempotency-Key": randomUUID() },
        },
        true,
      );
      return response.deleted_file_ids;
    });
  }

  async deleteFiles(fileIds: string[]): Promise<DesktopResult<string[]>> {
    return this.runRequest(async () => {
      await waitForRequestReadiness(() => this.getStatus(), this.startup);
      const response = await this.requestJson<FileDeleteResponse>(
        "/v1/file-deletions",
        batchFileDeleteRequest(fileIds, randomUUID()),
        true,
      );
      return response.deleted_file_ids;
    });
  }

  async watchIndexTask(
    taskId: string,
    onTask: (task: IndexTask) => void,
  ): Promise<void> {
    await waitForRequestReadiness(() => this.getStatus(), this.startup);
    while (this.getStatus().state === "healthy") {
      try {
        if (await this.consumeIndexTaskEvents(taskId, onTask)) {
          return;
        }
      } catch {
        // The authenticated status request below is the reconnect fallback.
      }
      const current = await this.getIndexTask(taskId);
      if (!current.ok) {
        return;
      }
      onTask(current.data);
      if (isTerminalIndexTask(current.data)) {
        return;
      }
      await new Promise<void>((resolve) => setTimeout(resolve, 500));
    }
  }

  start(): Promise<RuntimeStatus> {
    if (this.startup) {
      return this.startup;
    }
    if (this.status.state === "healthy") {
      return Promise.resolve(this.getStatus());
    }
    if (this.status.state === "stopped" && !this.restartTimer) {
      this.restartAttempts = 0;
    }

    const startup = this.launch();
    this.startup = startup;
    startup.then(
      () => this.clearStartup(startup),
      () => this.clearStartup(startup),
    );
    return startup;
  }

  private clearStartup(startup: Promise<RuntimeStatus>): void {
    if (this.startup === startup) {
      this.startup = undefined;
    }
  }

  private async launch(): Promise<RuntimeStatus> {
    if (this.child) {
      return this.getStatus();
    }

    this.stopping = false;
    this.setStatus({
      state: "starting",
      protocol: SIDECAR_PROTOCOL_VERSION,
      capabilities: [],
    });

    const token = randomBytes(32).toString("hex");
    const command = this.sidecarCommand();
    const child = spawn(command.executable, command.args, {
      env: {
        ...process.env,
        KH_APP_DATA_DIR: path.join(
          this.options.dataRoot,
          "state",
          "ktem_app_data",
        ),
        MARA_DESKTOP_DATA_DIR: this.options.dataRoot,
        MARA_DESKTOP_TOKEN: token,
        MARA_DESKTOP_SMOKE_FAULT: this.options.smokeFault ?? "",
      },
      cwd: this.options.isPackaged ? undefined : this.options.appPath,
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });
    this.child = child;
    this.token = token;

    child.stderr.setEncoding("utf8");
    child.stderr.on("data", (chunk: string) => {
      process.stderr.write(`[mara-sidecar] ${chunk}`);
    });
    child.once("exit", (code, signal) => {
      this.child = undefined;
      this.port = undefined;
      this.token = undefined;
      if (!this.stopping) {
        this.setStatus({
          state: "failed",
          protocol: SIDECAR_PROTOCOL_VERSION,
          capabilities: [],
          message: `Sidecar exited unexpectedly (${signal ?? code ?? "unknown"}).`,
        });
        this.scheduleRestart();
      }
    });

    try {
      const ready = await this.waitForReady(child);
      if (ready.pid !== child.pid) {
        throw new Error("Sidecar reported a different process identifier");
      }
      this.port = ready.port;
      const health = await this.requestJson<Record<string, unknown>>("/health");
      this.setStatus({
        state: "healthy",
        protocol: ready.protocol,
        version: String(health.version ?? ""),
        capabilities: Array.isArray(health.capabilities)
          ? health.capabilities.map(String)
          : [],
      });
      return this.getStatus();
    } catch (error) {
      child.kill();
      const message = error instanceof Error ? error.message : String(error);
      this.setStatus({
        state: "failed",
        protocol: SIDECAR_PROTOCOL_VERSION,
        capabilities: [],
        message,
      });
      return this.getStatus();
    }
  }

  async crashForSmoke(): Promise<void> {
    const child = this.child;
    if (!child) {
      throw new Error("Sidecar is not running for the interruption smoke");
    }
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        child.off("exit", onExit);
        reject(new Error("Sidecar did not exit during the interruption smoke"));
      }, 5_000);
      const onExit = () => {
        clearTimeout(timer);
        resolve();
      };
      child.once("exit", onExit);
      if (!child.kill("SIGKILL")) {
        clearTimeout(timer);
        child.off("exit", onExit);
        reject(new Error("Sidecar could not be terminated for the smoke"));
      }
    });
    if (this.child) {
      throw new Error("Sidecar process remained attached after termination");
    }
  }

  private scheduleRestart(): void {
    if (this.stopping || this.child || this.restartTimer) {
      return;
    }
    const delay = sidecarRestartDelay(this.restartAttempts);
    if (delay === undefined) {
      this.setStatus({
        state: "failed",
        protocol: SIDECAR_PROTOCOL_VERSION,
        capabilities: [],
        message: "Sidecar automatic restart budget was exhausted.",
      });
      return;
    }
    this.restartAttempts += 1;
    this.restartTimer = setTimeout(() => {
      this.restartTimer = undefined;
      if (!this.stopping && !this.child) {
        void this.start();
      }
    }, delay);
  }

  async stop(): Promise<void> {
    this.stopping = true;
    if (this.restartTimer) {
      clearTimeout(this.restartTimer);
      this.restartTimer = undefined;
    }
    const child = this.child;
    if (!child) {
      this.restartAttempts = 0;
      this.setStatus({
        state: "stopped",
        protocol: SIDECAR_PROTOCOL_VERSION,
        capabilities: [],
      });
      return;
    }

    try {
      await this.requestJson("/shutdown", { method: "POST" });
      await Promise.race([
        new Promise<void>((resolve) => child.once("exit", () => resolve())),
        new Promise<void>((resolve) => setTimeout(resolve, 2_000)),
      ]);
    } catch {
      // The final kill below is the bounded shutdown fallback.
    }
    if (this.child) {
      child.kill();
    }
    this.child = undefined;
    this.port = undefined;
    this.token = undefined;
    this.restartAttempts = 0;
    this.setStatus({
      state: "stopped",
      protocol: SIDECAR_PROTOCOL_VERSION,
      capabilities: [],
    });
  }

  private sidecarCommand(): { executable: string; args: string[] } {
    if (this.options.isPackaged) {
      const executableName =
        process.platform === "win32" ? "mara-desktop-sidecar.exe" : "mara-desktop-sidecar";
      return {
        executable: path.join(
          this.options.resourcesPath,
          "sidecar",
          "mara-desktop-sidecar",
          executableName,
        ),
        args: [],
      };
    }

    return {
      executable: this.developmentPython(),
      args: ["-m", "sidecar.server"],
    };
  }

  private developmentPython(): string {
    if (process.env.MARA_DESKTOP_PYTHON) {
      return process.env.MARA_DESKTOP_PYTHON;
    }
    const workspacePython = path.resolve(
      this.options.appPath,
      "..",
      "..",
      ".venv",
      process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
    );
    if (existsSync(workspacePython)) {
      return workspacePython;
    }
    return process.platform === "win32" ? "python" : "python3";
  }

  private waitForReady(
    child: ChildProcessWithoutNullStreams,
  ): Promise<SidecarReadyMessage> {
    return new Promise((resolve, reject) => {
      let buffer = "";
      const timer = setTimeout(() => {
        cleanup();
        reject(new Error("Sidecar startup timed out"));
      }, 20_000);

      const cleanup = () => {
        clearTimeout(timer);
        child.stdout.off("data", onData);
        child.off("error", onError);
        child.off("exit", onExit);
      };
      const onError = (error: Error) => {
        cleanup();
        reject(error);
      };
      const onExit = (code: number | null) => {
        cleanup();
        reject(new Error(`Sidecar exited during startup (${code ?? "unknown"})`));
      };
      const onData = (chunk: Buffer) => {
        buffer += chunk.toString("utf8");
        const newline = buffer.indexOf("\n");
        if (newline === -1) {
          if (buffer.length > 8_192) {
            cleanup();
            reject(new Error("Sidecar ready message exceeded the limit"));
          }
          return;
        }
        cleanup();
        try {
          resolve(parseReadyMessage(buffer.slice(0, newline).trim()));
        } catch (error) {
          reject(error);
        }
      };

      child.stdout.on("data", onData);
      child.once("error", onError);
      child.once("exit", onExit);
    });
  }

  private async requestJson<T>(
    pathname: string,
    init: RequestInit = {},
    requireMatchingRequestId = false,
  ): Promise<T> {
    if (!this.port || !this.token) {
      throw sidecarNotReadyFailure();
    }
    const requestId = randomUUID();
    const response = await fetch(`http://127.0.0.1:${this.port}${pathname}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${this.token}`,
        "X-Request-ID": requestId,
        ...init.headers,
      },
      signal: AbortSignal.timeout(sidecarRequestTimeout(pathname, init.method)),
    });
    const payload: unknown = await response.json();
    if (!response.ok) {
      throw new SidecarRequestFailure(
        isSidecarError(payload)
          ? payload
          : {
              code: "invalid_sidecar_error",
              message: "The MARA Sidecar returned an invalid error response.",
              details: { status: response.status },
              retryable: true,
              request_id: requestId,
            },
      );
    }
    if (
      requireMatchingRequestId &&
      (!payload ||
        typeof payload !== "object" ||
        (payload as Record<string, unknown>).request_id !== requestId)
    ) {
      throw new SidecarRequestFailure({
        code: "request_id_mismatch",
        message: "The MARA Sidecar returned a mismatched response.",
        details: null,
        retryable: true,
        request_id: requestId,
      });
    }
    return payload as T;
  }

  private async mutateIndexTask(
    taskId: string,
    action: "cancel" | "retry",
    idempotent = false,
  ): Promise<DesktopResult<IndexTask>> {
    return this.runRequest(async () => {
      await waitForRequestReadiness(() => this.getStatus(), this.startup);
      const response = await this.requestJson<IndexTaskResponse>(
        `/v1/index-tasks/${encodeURIComponent(taskId)}/${action}`,
        {
          method: "POST",
          headers: idempotent ? { "Idempotency-Key": randomUUID() } : {},
        },
        true,
      );
      return response.task;
    });
  }

  private async consumeIndexTaskEvents(
    taskId: string,
    onTask: (task: IndexTask) => void,
  ): Promise<boolean> {
    if (!this.port || !this.token) {
      throw sidecarNotReadyFailure();
    }
    const requestId = randomUUID();
    const response = await fetch(
      `http://127.0.0.1:${this.port}/v1/index-tasks/${encodeURIComponent(taskId)}/events`,
      {
        headers: {
          Accept: "text/event-stream",
          Authorization: `Bearer ${this.token}`,
          "X-Request-ID": requestId,
        },
      },
    );
    if (!response.ok || !response.body) {
      throw new Error("Sidecar task event stream is unavailable");
    }
    if (response.headers.get("X-Request-ID") !== requestId) {
      throw new Error("Sidecar task event stream returned a mismatched response");
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const block = buffer.slice(0, boundary).trim();
        buffer = buffer.slice(boundary + 2);
        if (block) {
          const task = parseIndexTaskEvent(block, requestId);
          onTask(task);
          if (isTerminalIndexTask(task)) {
            return true;
          }
        }
        boundary = buffer.indexOf("\n\n");
      }
      if (done) {
        return false;
      }
    }
  }

  private async runRequest<T>(
    operation: () => Promise<T>,
  ): Promise<DesktopResult<T>> {
    try {
      return { ok: true, data: await operation() };
    } catch (error) {
      if (error instanceof SidecarRequestFailure) {
        return { ok: false, error: error.contract };
      }
      return {
        ok: false,
        error: {
          code: "sidecar_unavailable",
          message: "The MARA Sidecar could not complete the request.",
          details: null,
          retryable: true,
          request_id: randomUUID(),
        },
      };
    }
  }

  private setStatus(status: RuntimeStatus): void {
    this.status = status;
    this.options.onStatus?.(this.getStatus());
  }
}

function isSidecarError(value: unknown): value is SidecarError {
  if (!value || typeof value !== "object") {
    return false;
  }
  const error = value as Record<string, unknown>;
  return (
    typeof error.code === "string" &&
    typeof error.message === "string" &&
    typeof error.retryable === "boolean" &&
    typeof error.request_id === "string" &&
    Object.hasOwn(error, "details")
  );
}

function isIndexTaskResponse(value: unknown): value is IndexTaskResponse {
  if (!value || typeof value !== "object") {
    return false;
  }
  const response = value as Record<string, unknown>;
  return typeof response.request_id === "string" && isIndexTask(response.task);
}

function isIndexTask(value: unknown): value is IndexTask {
  if (!value || typeof value !== "object") {
    return false;
  }
  const task = value as Record<string, unknown>;
  const statuses = new Set([
    "queued",
    "running",
    "partial",
    "success",
    "failed",
    "cancelled",
  ]);
  return (
    typeof task.task_id === "string" &&
    typeof task.status === "string" &&
    statuses.has(task.status) &&
    typeof task.stage === "string" &&
    typeof task.completed_files === "number" &&
    typeof task.total_files === "number" &&
    Array.isArray(task.file_names) &&
    typeof task.success_count === "number" &&
    typeof task.failure_count === "number" &&
    Array.isArray(task.failures) &&
    (task.error === null || typeof task.error === "object") &&
    typeof task.retryable === "boolean" &&
    typeof task.created_at === "string" &&
    typeof task.updated_at === "string" &&
    typeof task.version === "number"
  );
}

function isTerminalIndexTask(task: IndexTask): boolean {
  return ["partial", "success", "failed", "cancelled"].includes(task.status);
}

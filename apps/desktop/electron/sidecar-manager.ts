import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomBytes } from "node:crypto";
import path from "node:path";

export const SIDECAR_PROTOCOL_VERSION = 1;

export type SidecarReadyMessage = {
  type: "ready";
  protocol: number;
  port: number;
  pid: number;
};

export type RuntimeStatus = {
  state: "starting" | "healthy" | "failed" | "stopped";
  protocol: number;
  version?: string;
  capabilities: string[];
  message?: string;
};

type SidecarManagerOptions = {
  appPath: string;
  isPackaged: boolean;
  resourcesPath: string;
  onStatus?: (status: RuntimeStatus) => void;
};

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

export class SidecarManager {
  private child?: ChildProcessWithoutNullStreams;
  private token?: string;
  private port?: number;
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

  async start(): Promise<RuntimeStatus> {
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
        MARA_DESKTOP_TOKEN: token,
      },
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
      }
    });

    try {
      const ready = await this.waitForReady(child);
      if (ready.pid !== child.pid) {
        throw new Error("Sidecar reported a different process identifier");
      }
      this.port = ready.port;
      const health = await this.requestJson("/health");
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

  async stop(): Promise<void> {
    const child = this.child;
    if (!child) {
      this.setStatus({
        state: "stopped",
        protocol: SIDECAR_PROTOCOL_VERSION,
        capabilities: [],
      });
      return;
    }

    this.stopping = true;
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
      executable:
        process.env.MARA_DESKTOP_PYTHON ??
        (process.platform === "win32" ? "python" : "python3"),
      args: [path.join(this.options.appPath, "sidecar", "server.py")],
    };
  }

  private waitForReady(
    child: ChildProcessWithoutNullStreams,
  ): Promise<SidecarReadyMessage> {
    return new Promise((resolve, reject) => {
      let buffer = "";
      const timer = setTimeout(() => {
        cleanup();
        reject(new Error("Sidecar startup timed out"));
      }, 8_000);

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

  private async requestJson(
    pathname: string,
    init: RequestInit = {},
  ): Promise<Record<string, unknown>> {
    if (!this.port || !this.token) {
      throw new Error("Sidecar is not ready");
    }
    const response = await fetch(`http://127.0.0.1:${this.port}${pathname}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${this.token}`,
        ...init.headers,
      },
      signal: AbortSignal.timeout(2_000),
    });
    if (!response.ok) {
      throw new Error(`Sidecar request failed with status ${response.status}`);
    }
    return (await response.json()) as Record<string, unknown>;
  }

  private setStatus(status: RuntimeStatus): void {
    this.status = status;
    this.options.onStatus?.(this.getStatus());
  }
}

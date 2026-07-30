export const SIDECAR_PROTOCOL_VERSION = 1;

export type RuntimeStatus = {
  state: "starting" | "healthy" | "failed" | "stopped";
  protocol: number;
  version?: string;
  capabilities: string[];
  message?: string;
};

export type SidecarError = {
  code: string;
  message: string;
  details: unknown | null;
  retryable: boolean;
  request_id: string;
};

export type DesktopResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: SidecarError };

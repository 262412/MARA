import type { SidecarError } from "./api-contracts.generated";

export const SIDECAR_PROTOCOL_VERSION = 1;

export type RuntimeStatus = {
  state: "starting" | "healthy" | "failed" | "stopped";
  protocol: number;
  version?: string;
  capabilities: string[];
  message?: string;
};

export type { SidecarError } from "./api-contracts.generated";

export type DesktopResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: SidecarError };

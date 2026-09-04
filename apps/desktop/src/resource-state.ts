import type { SidecarError } from "../shared/runtime-contracts";

export type ResourceState<T> =
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "failed"; message: string; error?: SidecarError };

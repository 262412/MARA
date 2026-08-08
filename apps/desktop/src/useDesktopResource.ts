import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import type {
  DesktopResult,
} from "../shared/runtime-contracts";
import type { ResourceState } from "./resource-state";

export function useDesktopResource<T>(
  loader: () => Promise<DesktopResult<T>>,
): {
  resource: ResourceState<T>;
  retry: () => void;
} {
  const [resource, setResource] = useState<ResourceState<T>>({
    status: "loading",
  });
  const requestGeneration = useRef(0);

  const load = useCallback(async () => {
    const generation = ++requestGeneration.current;
    setResource({ status: "loading" });
    let result: DesktopResult<T>;
    try {
      result = await loader();
    } catch {
      result = {
        ok: false,
        error: {
          code: "desktop_request_failed",
          message: "Desktop 请求未能完成。",
          details: null,
          retryable: true,
          request_id: "renderer-request",
        },
      };
    }
    if (generation !== requestGeneration.current) {
      return;
    }
    setResource(
      result.ok
        ? { status: "success", data: result.data }
        : {
            status: "failed",
            message: result.error.message,
            error: result.error,
          },
    );
  }, [loader]);

  useEffect(() => {
    void load();
    return () => {
      requestGeneration.current += 1;
    };
  }, [load]);

  return {
    resource,
    retry: load,
  };
}

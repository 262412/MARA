import assert from "node:assert/strict";
import test from "node:test";

import {
  createQueryPersistenceSmokeEnvironment,
  createStartupDelaySmokeEnvironment,
  mergeSidecarEnvironment,
} from "./smoke-environment";

test("ordinary Sidecar startup removes inherited Desktop smoke variables", () => {
  const inherited = {
    MARA_DESKTOP_CHAT_MODEL: "configured-model",
    MARA_DESKTOP_QUERY_SMOKE_FAULT_MARKER: "inherited-marker",
    MARA_DESKTOP_QUERY_SMOKE_FAULT_TOKEN: "inherited-token",
    MARA_DESKTOP_QUERY_SMOKE_MODE: "query_persistence",
    MARA_DESKTOP_SMOKE_FAULT: "disk_full",
    MARA_DESKTOP_SMOKE_STARTUP_DELAY_MS: "30000",
    mara_desktop_query_smoke_fault_marker: "windows-case-alias",
  };

  assert.deepEqual(mergeSidecarEnvironment(inherited, {}), {
    MARA_DESKTOP_CHAT_MODEL: "configured-model",
  });
});

test("startup delay is forwarded only for its explicit smoke mode", () => {
  assert.deepEqual(
    createStartupDelaySmokeEnvironment({ enabled: false, value: "1500" }),
    {},
  );
  assert.deepEqual(
    createStartupDelaySmokeEnvironment({ enabled: true, value: "1500" }),
    { MARA_DESKTOP_SMOKE_STARTUP_DELAY_MS: "1500" },
  );
  assert.throws(() =>
    createStartupDelaySmokeEnvironment({ enabled: true, value: "unbounded" }),
  );
});

test("only explicit Main smoke configuration can reintroduce query fault state", () => {
  const disabled = createQueryPersistenceSmokeEnvironment({
    enabled: false,
    markerPath: "ignored-marker",
    token: "ignored-token",
  });
  const enabled = createQueryPersistenceSmokeEnvironment({
    enabled: true,
    markerPath: "owned-marker",
    token: "fresh-token",
  });

  assert.deepEqual(disabled, {});
  assert.deepEqual(
    mergeSidecarEnvironment(
      {
        MARA_DESKTOP_QUERY_SMOKE_FAULT_MARKER: "inherited-marker",
        MARA_DESKTOP_QUERY_SMOKE_FAULT_TOKEN: "inherited-token",
      },
      enabled,
    ),
    {
      MARA_DESKTOP_QUERY_SMOKE_FAULT_MARKER: "owned-marker",
      MARA_DESKTOP_QUERY_SMOKE_FAULT_TOKEN: "fresh-token",
      MARA_DESKTOP_QUERY_SMOKE_MODE: "query_persistence",
    },
  );
});

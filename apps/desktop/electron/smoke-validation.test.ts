import assert from "node:assert/strict";
import test from "node:test";

import type { DesktopResult, RuntimeStatus } from "../shared/runtime-contracts";
import type { DoctorPayload } from "../shared/doctor-contracts";
import type { FileRecord } from "../shared/file-contracts";
import type { SessionSummary } from "../shared/session-contracts";
import {
  GATE2_SMOKE_FILE_ID,
  GATE2_SMOKE_SESSION_ID,
  assertPackagedSmoke,
} from "./smoke-validation";

const status: RuntimeStatus = {
  state: "healthy",
  protocol: 1,
  version: "0.2.0",
  capabilities: ["doctor", "files", "sessions"],
};
const doctor: DesktopResult<DoctorPayload> = {
  ok: true,
  data: {
    ok: true,
    app_name: "MARA",
    default_user_id: "default",
    index_name: "File Collection",
    index_id: 1,
    llm_default: "openai",
    embedding_default: "openai",
    file_count: 1,
    session_count: 1,
    graph_cache_dir: "/private/runtime/path",
    issues: [],
    warnings: [],
  },
};
const files: DesktopResult<FileRecord[]> = {
  ok: true,
  data: [
    {
      file_id: GATE2_SMOKE_FILE_ID,
      name: "gate2-smoke.txt",
      size: 24,
      tokens: 4,
      loader: "TextReader",
      date_created: "2026-07-30T12:00:00+00:00",
    },
  ],
};
const sessions: DesktopResult<SessionSummary[]> = {
  ok: true,
  data: [
    {
      conversation_id: GATE2_SMOKE_SESSION_ID,
      name: "Gate 2 smoke session",
      message_count: 2,
      graph_source_count: 1,
      origin: "desktop-gate2-smoke",
      is_public: false,
      date_created: "2026-07-30T12:00:00+00:00",
      date_updated: "2026-07-30T12:00:00+00:00",
    },
  ],
};

test("accepts the deterministic non-empty packaged smoke snapshot", () => {
  assert.doesNotThrow(() =>
    assertPackagedSmoke({ status, doctor, files, sessions }, true),
  );
});

test("rejects empty data when the packaged smoke requires real records", () => {
  assert.throws(
    () =>
      assertPackagedSmoke(
        {
          status,
          doctor: {
            ok: true,
            data: { ...doctor.data, file_count: 0, session_count: 0 },
          },
          files: { ok: true, data: [] },
          sessions: { ok: true, data: [] },
        },
        true,
      ),
    /non-empty Gate 2 fixture/,
  );
});

test("rejects a file response that exposes a local path", () => {
  const leakedFiles = {
    ok: true as const,
    data: [{ ...files.data[0], path: "/private/source/gate2-smoke.txt" }],
  } as unknown as DesktopResult<FileRecord[]>;

  assert.throws(
    () => assertPackagedSmoke({ status, doctor, files: leakedFiles, sessions }, true),
    /local path/,
  );
});

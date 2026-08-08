import assert from "node:assert/strict";
import test from "node:test";

import type { DesktopResult, RuntimeStatus } from "../shared/runtime-contracts";
import type { DoctorPayload } from "../shared/doctor-contracts";
import type { FileRecord } from "../shared/file-contracts";
import type { ImportCapabilities } from "../shared/file-contracts";
import type { SessionSummary } from "../shared/session-contracts";
import {
  GATE2_SMOKE_FILE_ID,
  GATE2_SMOKE_SESSION_ID,
  GATE3_FORMAT_RECORD_NAMES,
  assertGate3DeleteSmoke,
  assertGate3IndexSmoke,
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
const importCapabilities: DesktopResult<ImportCapabilities> = {
  ok: true,
  data: {
    supported_extensions: [".pdf", ".docx", ".txt", ".md", ".zip"],
  },
};

test("accepts the deterministic non-empty packaged smoke snapshot", () => {
  assert.doesNotThrow(() =>
    assertPackagedSmoke(
      { status, doctor, files, sessions, importCapabilities },
      true,
    ),
  );
});

test("accepts an additional CLI-indexed file in the shared smoke data", () => {
  const cliFiles: DesktopResult<FileRecord[]> = {
    ok: true,
    data: [
      ...files.data,
      {
        file_id: "cli-indexed-file",
        name: "gate3-cli-compat.txt",
        size: 31,
        tokens: 5,
        loader: "TextReader",
        date_created: "2026-08-08T11:00:00+00:00",
      },
    ],
  };
  const cliDoctor: DesktopResult<DoctorPayload> = {
    ok: true,
    data: { ...doctor.data, file_count: 2 },
  };

  assert.doesNotThrow(() =>
    assertPackagedSmoke(
      { status, doctor: cliDoctor, files: cliFiles, sessions, importCapabilities },
      true,
    ),
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
          importCapabilities,
        },
        true,
      ),
    /non-empty Gate 2 fixture:.*"doctor_file_count":0.*"file_ids":\[\]/,
  );
});

test("rejects a file response that exposes a local path", () => {
  const leakedFiles = {
    ok: true as const,
    data: [{ ...files.data[0], path: "/private/source/gate2-smoke.txt" }],
  } as unknown as DesktopResult<FileRecord[]>;

  assert.throws(
    () =>
      assertPackagedSmoke(
        { status, doctor, files: leakedFiles, sessions, importCapabilities },
        true,
      ),
    /local path/,
  );
});

test("rejects packaged smoke without the configured import format contract", () => {
  assert.throws(
    () =>
      assertPackagedSmoke(
        {
          status,
          doctor,
          files,
          sessions,
          importCapabilities: { ok: true, data: { supported_extensions: [] } },
        },
        true,
      ),
    /import capabilities/,
  );
});

test("accepts packaged deletion only when the real fixture disappears", () => {
  assert.doesNotThrow(() =>
    assertGate3DeleteSmoke(
      { ok: true, data: [GATE2_SMOKE_FILE_ID] },
      { ok: true, data: [] },
    ),
  );
  assert.throws(
    () =>
      assertGate3DeleteSmoke(
        { ok: true, data: [GATE2_SMOKE_FILE_ID] },
        files,
      ),
    /still present/,
  );
});

test("accepts a successful packaged background index and refreshed Files", () => {
  const created = {
    ok: true as const,
    data: {
      task_id: "gate3-task",
      status: "queued" as const,
      stage: "queued",
      completed_files: 0,
      total_files: 1,
      file_names: ["gate3-index-smoke.txt"],
      success_count: 0,
      failure_count: 0,
      failures: [],
      error: null,
      retryable: false,
      created_at: "2026-08-08T10:00:00Z",
      updated_at: "2026-08-08T10:00:00Z",
      version: 1,
    },
  };
  const terminal = {
    ok: true as const,
    data: {
      ...created.data,
      status: "success" as const,
      stage: "completed",
      completed_files: 1,
      success_count: 1,
      version: 3,
    },
  };
  const indexedFiles: DesktopResult<FileRecord[]> = {
    ok: true,
    data: [
      ...files.data,
      {
        file_id: "gate3-indexed-file",
        name: "gate3-index-smoke.txt",
        size: 32,
        tokens: 5,
        loader: "TextReader",
        date_created: "2026-08-08T10:00:02Z",
      },
    ],
  };

  assert.deepEqual(
    assertGate3IndexSmoke(created, terminal, indexedFiles),
    ["gate3-indexed-file"],
  );
  assert.throws(
    () =>
      assertGate3IndexSmoke(
        created,
        { ...terminal, data: { ...terminal.data, status: "failed" } },
        indexedFiles,
      ),
    /did not succeed/,
  );
});

test("requires every lightweight format record in the packaged matrix", () => {
  const formatFiles: DesktopResult<FileRecord[]> = {
    ok: true,
    data: GATE3_FORMAT_RECORD_NAMES.map((name, index) => ({
      file_id: `format-${index}`,
      name,
      size: 32,
      tokens: 5,
      loader: "fixture-loader",
      date_created: "2026-08-08T10:00:02Z",
    })),
  };
  const created = {
    ok: true as const,
    data: {
      task_id: "format-task",
      status: "queued" as const,
      stage: "queued",
      completed_files: 0,
      total_files: 6,
      file_names: ["format fixtures"],
      success_count: 0,
      failure_count: 0,
      failures: [],
      error: null,
      retryable: false,
      created_at: "2026-08-08T10:00:00Z",
      updated_at: "2026-08-08T10:00:00Z",
      version: 1,
    },
  };
  const terminal = {
    ok: true as const,
    data: {
      ...created.data,
      status: "success" as const,
      stage: "completed",
      completed_files: 6,
      success_count: 6,
    },
  };

  assert.equal(
    assertGate3IndexSmoke(
      created,
      terminal,
      formatFiles,
      GATE3_FORMAT_RECORD_NAMES,
    ).length,
    GATE3_FORMAT_RECORD_NAMES.length,
  );
  assert.throws(
    () =>
      assertGate3IndexSmoke(
        created,
        terminal,
        { ok: true, data: formatFiles.data.slice(0, -1) },
        GATE3_FORMAT_RECORD_NAMES,
      ),
    /fixtures are missing/,
  );
});

import type { DoctorPayload } from "../shared/doctor-contracts";
import type {
  FileRecord,
  ImportCapabilities,
} from "../shared/file-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
import type {
  DesktopResult,
  RuntimeStatus,
} from "../shared/runtime-contracts";
import type { SessionSummary } from "../shared/session-contracts";

export const GATE2_SMOKE_FILE_ID = "gate2-smoke-file";
export const GATE2_SMOKE_SESSION_ID = "gate2-smoke-session";
export const GATE3_MODEL_UNAVAILABLE_INPUT_NAME =
  "gate3-model-unavailable.txt";
export const GATE3_CANCEL_INPUT_NAMES = [
  "gate3-cancel-first.txt",
  "gate3-cancel-second.txt",
] as const;
export const GATE3_CANCEL_BLOCK_MARKER_NAME = "gate3-embedding-block";
export const GATE3_CANCEL_REQUEST_MARKER_NAME = "gate3-embedding-request";
export const GATE3_FORMAT_INPUT_NAMES = [
  "gate3-format.md",
  "gate3-format.csv",
  "gate3-format.html",
  "gate3-format.mhtml",
  "gate3-format.zip",
] as const;
export const GATE3_FORMAT_RECORD_NAMES = [
  "gate3-index-smoke.txt",
  "gate3-format.md",
  "gate3-format.csv",
  "gate3-format.html",
  "gate3-format.mhtml",
  "gate3-zip-note.md",
] as const;

type PackagedSmokeSnapshot = {
  status: RuntimeStatus;
  doctor: DesktopResult<DoctorPayload>;
  files: DesktopResult<FileRecord[]>;
  importCapabilities: DesktopResult<ImportCapabilities>;
  sessions: DesktopResult<SessionSummary[]>;
};

export function assertPackagedSmoke(
  snapshot: PackagedSmokeSnapshot,
  requireNonEmptyFixture: boolean,
): void {
  const { status, doctor, files, importCapabilities, sessions } = snapshot;
  if (status.state !== "healthy") {
    throw new Error(`Sidecar did not become healthy: ${status.state}`);
  }
  if (!doctor.ok) {
    throw new Error(`Doctor request failed: ${doctor.error.code}`);
  }
  if (!files.ok) {
    throw new Error(`Files request failed: ${files.error.code}`);
  }
  if (!sessions.ok) {
    throw new Error(`Sessions request failed: ${sessions.error.code}`);
  }
  if (
    !importCapabilities.ok ||
    !importCapabilities.data.supported_extensions.includes(".txt")
  ) {
    throw new Error("Packaged app did not load the import capabilities");
  }
  if (files.data.some((record) => Object.hasOwn(record, "path"))) {
    throw new Error("Files response exposed a local path");
  }
  if (!requireNonEmptyFixture) {
    return;
  }

  const fixtureFile = files.data.find(
    (record) => record.file_id === GATE2_SMOKE_FILE_ID,
  );
  const fixtureSession = sessions.data.find(
    (record) => record.conversation_id === GATE2_SMOKE_SESSION_ID,
  );
  if (
    !doctor.data.ok ||
    doctor.data.file_count !== files.data.length ||
    doctor.data.session_count !== sessions.data.length ||
    files.data.length < 1 ||
    sessions.data.length !== 1 ||
    !fixtureFile ||
    !fixtureSession
  ) {
    const diagnostic = {
      doctor_ok: doctor.data.ok,
      doctor_file_count: doctor.data.file_count,
      doctor_session_count: doctor.data.session_count,
      doctor_issue_count: doctor.data.issues.length,
      file_ids: files.data.map((record) => record.file_id),
      session_ids: sessions.data.map((record) => record.conversation_id),
    };
    throw new Error(
      `Packaged app did not load the non-empty Gate 2 fixture: ${JSON.stringify(diagnostic)}`,
    );
  }
}

export function assertGate3DeleteSmoke(
  deleted: DesktopResult<string[]>,
  filesAfterDelete: DesktopResult<FileRecord[]>,
  expectedFileId = GATE2_SMOKE_FILE_ID,
): void {
  if (!deleted.ok) {
    throw new Error(`Gate 3 delete failed: ${deleted.error.code}`);
  }
  if (!deleted.data.includes(expectedFileId)) {
    throw new Error("Gate 3 delete did not return the fixture file ID");
  }
  if (!filesAfterDelete.ok) {
    throw new Error(`Gate 3 Files refresh failed: ${filesAfterDelete.error.code}`);
  }
  if (
    filesAfterDelete.data.some(
      (record) => record.file_id === expectedFileId,
    )
  ) {
    throw new Error("Gate 3 fixture is still present after deletion");
  }
}

export function assertGate3IndexSmoke(
  created: DesktopResult<IndexTask>,
  terminal: DesktopResult<IndexTask>,
  filesAfterIndex: DesktopResult<FileRecord[]>,
  expectedFileNames: readonly string[] = ["gate3-index-smoke.txt"],
): string[] {
  if (!created.ok) {
    throw new Error(`Gate 3 index task creation failed: ${created.error.code}`);
  }
  if (!terminal.ok || terminal.data.status !== "success") {
    const state = terminal.ok ? terminal.data.status : terminal.error.code;
    throw new Error(`Gate 3 index task did not succeed: ${state}`);
  }
  if (terminal.data.task_id !== created.data.task_id) {
    throw new Error("Gate 3 index task identity changed while running");
  }
  if (!filesAfterIndex.ok) {
    throw new Error(`Gate 3 Files refresh failed: ${filesAfterIndex.error.code}`);
  }
  const indexed: FileRecord[] = [];
  for (const name of expectedFileNames) {
    const record = filesAfterIndex.data.find((candidate) => candidate.name === name);
    if (!record) {
      const foundNames = filesAfterIndex.data.map((candidate) => candidate.name);
      throw new Error(
        `Gate 3 indexed fixtures are missing after Files refresh: ${JSON.stringify(foundNames)}`,
      );
    }
    if (Object.hasOwn(record, "path")) {
      throw new Error("Gate 3 indexed fixture exposed a local path");
    }
    indexed.push(record);
  }
  return indexed.map((record) => record.file_id);
}

export function assertGate3ModelUnavailableSmoke(
  created: DesktopResult<IndexTask>,
  terminal: DesktopResult<IndexTask>,
): string {
  if (!created.ok) {
    throw new Error(`Gate 3 fault task creation failed: ${created.error.code}`);
  }
  if (!terminal.ok) {
    throw new Error(`Gate 3 fault task request failed: ${terminal.error.code}`);
  }
  const task = terminal.data;
  if (task.task_id !== created.data.task_id) {
    throw new Error("Gate 3 fault task identity changed while running");
  }
  if (
    task.status !== "failed" ||
    task.error?.code !== "index_failed" ||
    !task.retryable ||
    task.completed_files !== 1 ||
    task.success_count !== 0 ||
    task.failure_count !== 1 ||
    task.file_names[0] !== GATE3_MODEL_UNAVAILABLE_INPUT_NAME ||
    task.failures[0]?.name !== GATE3_MODEL_UNAVAILABLE_INPUT_NAME
  ) {
    throw new Error("Gate 3 model-unavailable fault was not reported safely");
  }
  return task.task_id;
}

export function assertGate3RetrySource(
  latest: DesktopResult<IndexTask | null>,
): string {
  if (!latest.ok) {
    throw new Error(`Gate 3 retry source request failed: ${latest.error.code}`);
  }
  if (
    latest.data === null ||
    latest.data.status !== "failed" ||
    !latest.data.retryable ||
    latest.data.file_names[0] !== GATE3_MODEL_UNAVAILABLE_INPUT_NAME
  ) {
    throw new Error("Gate 3 retry did not find the model-unavailable task");
  }
  return latest.data.task_id;
}

export function assertGate3CancellationSmoke(
  created: DesktopResult<IndexTask>,
  cancelling: DesktopResult<IndexTask>,
  terminal: DesktopResult<IndexTask>,
  filesAfterCancel: DesktopResult<FileRecord[]>,
): string {
  if (!created.ok || !cancelling.ok || !terminal.ok) {
    throw new Error("Gate 3 cancellation task request failed");
  }
  const task = terminal.data;
  if (
    cancelling.data.task_id !== created.data.task_id ||
    cancelling.data.status !== "running" ||
    cancelling.data.stage !== "cancelling" ||
    task.task_id !== created.data.task_id ||
    task.status !== "cancelled" ||
    task.error?.code !== "index_cancelled" ||
    !task.retryable ||
    task.completed_files !== 1 ||
    task.success_count !== 1 ||
    task.failure_count !== 0 ||
    task.file_names.join(",") !== GATE3_CANCEL_INPUT_NAMES.join(",")
  ) {
    throw new Error("Gate 3 task did not cancel at the file boundary");
  }
  if (!filesAfterCancel.ok) {
    throw new Error(`Gate 3 cancel refresh failed: ${filesAfterCancel.error.code}`);
  }
  const first = filesAfterCancel.data.find(
    (record) => record.name === GATE3_CANCEL_INPUT_NAMES[0],
  );
  const second = filesAfterCancel.data.find(
    (record) => record.name === GATE3_CANCEL_INPUT_NAMES[1],
  );
  if (!first || second || Object.hasOwn(first, "path")) {
    throw new Error("Gate 3 cancellation crossed the expected file boundary");
  }
  return first.file_id;
}

export function assertGate3CancelRetrySmoke(
  retried: DesktopResult<IndexTask>,
  terminal: DesktopResult<IndexTask>,
  filesAfterRetry: DesktopResult<FileRecord[]>,
): string[] {
  if (
    !retried.ok ||
    retried.data.total_files !== 1 ||
    retried.data.file_names[0] !== GATE3_CANCEL_INPUT_NAMES[1]
  ) {
    throw new Error("Gate 3 cancellation retry selected the wrong files");
  }
  return assertGate3IndexSmoke(
    retried,
    terminal,
    filesAfterRetry,
    GATE3_CANCEL_INPUT_NAMES,
  );
}

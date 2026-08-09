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
import type {
  SessionDetail,
  SessionSummary,
} from "../shared/session-contracts";

export {
  GATE3_FORMAT_INPUT_NAMES,
  GATE3_FORMAT_RECORD_NAMES,
} from "./smoke-format-fixtures";

export const GATE2_SMOKE_FILE_ID = "gate2-smoke-file";
export const GATE2_SMOKE_SESSION_ID = "gate2-smoke-session";
export const GATE3_RENAMED_SESSION_NAME = "Gate 3 renamed session";
export const GATE3_MODEL_UNAVAILABLE_INPUT_NAME =
  "gate3-model-unavailable.txt";
export const GATE3_PARTIAL_INPUT_NAMES = [
  "gate3-partial-already-indexed.txt",
  "gate3-partial-success.txt",
] as const;
export const GATE3_INTERRUPTED_INPUT_NAME = "gate3-sidecar-interrupted.txt";
export const GATE3_LARGE_FILE_INPUT_NAME = "gate3-large-file.txt";
export const GATE3_LARGE_FILE_BYTES = 5 * 1024 * 1024;
export const GATE3_DISK_FULL_INPUT_NAME = "gate3-disk-full.txt";
export const GATE3_DATABASE_LOCKED_INPUT_NAME = "gate3-database-locked.txt";
export const GATE3_CANCEL_INPUT_NAMES = [
  "gate3-cancel-first.txt",
  "gate3-cancel-second.txt",
] as const;
export const GATE3_CANCEL_BLOCK_MARKER_NAME = "gate3-embedding-block";
export const GATE3_CANCEL_REQUEST_MARKER_NAME = "gate3-embedding-request";
type PackagedSmokeSnapshot = {
  status: RuntimeStatus;
  doctor: DesktopResult<DoctorPayload>;
  files: DesktopResult<FileRecord[]>;
  importCapabilities: DesktopResult<ImportCapabilities>;
  session: DesktopResult<SessionDetail | null>;
  sessions: DesktopResult<SessionSummary[]>;
};

export function assertPackagedSmoke(
  snapshot: PackagedSmokeSnapshot,
  requireNonEmptyFixture: boolean,
): void {
  const { status, doctor, files, importCapabilities, session, sessions } =
    snapshot;
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
  if (!session.ok) {
    throw new Error(`Session detail request failed: ${session.error.code}`);
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
    !fixtureSession ||
    !session.data ||
    session.data.conversation_id !== GATE2_SMOKE_SESSION_ID ||
    session.data.messages.length !== 2 ||
    session.data.messages[0]?.role !== "user" ||
    session.data.messages[1]?.role !== "assistant" ||
    Object.hasOwn(session.data, "data_source") ||
    Object.hasOwn(session.data, "user_id")
  ) {
    const diagnostic = {
      doctor_ok: doctor.data.ok,
      doctor_file_count: doctor.data.file_count,
      doctor_session_count: doctor.data.session_count,
      doctor_issue_count: doctor.data.issues.length,
      file_ids: files.data.map((record) => record.file_id),
      session_ids: sessions.data.map((record) => record.conversation_id),
      session_detail_id: session.data?.conversation_id,
      session_message_count: session.data?.messages.length,
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

export function assertGate3SessionMutationSmoke(
  created: DesktopResult<SessionDetail>,
  createdReloaded: DesktopResult<SessionDetail>,
  sessionsAfterCreate: DesktopResult<SessionSummary[]>,
  createdDeleted: DesktopResult<string>,
  renamed: DesktopResult<SessionDetail>,
  reloaded: DesktopResult<SessionDetail>,
  sessionsAfterRename: DesktopResult<SessionSummary[]>,
  deleted: DesktopResult<string>,
  sessionsAfterDelete: DesktopResult<SessionSummary[]>,
): void {
  if (!created.ok || !createdReloaded.ok || !sessionsAfterCreate.ok) {
    throw new Error("Gate 3 session creation request failed");
  }
  const createdSummary = sessionsAfterCreate.data.find(
    (candidate) => candidate.conversation_id === created.data.conversation_id,
  );
  if (
    !/^[A-Za-z0-9._-]{1,128}$/.test(created.data.conversation_id) ||
    createdReloaded.data.conversation_id !== created.data.conversation_id ||
    created.data.messages.length !== 0 ||
    !createdSummary ||
    Object.hasOwn(created.data, "path") ||
    Object.hasOwn(created.data, "data_source") ||
    Object.hasOwn(created.data, "user_id")
  ) {
    throw new Error("Gate 3 session creation did not persist safely");
  }
  if (
    !createdDeleted.ok ||
    createdDeleted.data !== created.data.conversation_id
  ) {
    throw new Error("Gate 3 created session cleanup failed");
  }
  if (!renamed.ok || !reloaded.ok || !sessionsAfterRename.ok) {
    throw new Error("Gate 3 session rename request failed");
  }
  const renamedSummary = sessionsAfterRename.data.find(
    (candidate) => candidate.conversation_id === GATE2_SMOKE_SESSION_ID,
  );
  if (
    renamed.data.conversation_id !== GATE2_SMOKE_SESSION_ID ||
    renamed.data.name !== GATE3_RENAMED_SESSION_NAME ||
    reloaded.data.name !== GATE3_RENAMED_SESSION_NAME ||
    renamedSummary?.name !== GATE3_RENAMED_SESSION_NAME ||
    Object.hasOwn(renamed.data, "path") ||
    Object.hasOwn(renamed.data, "data_source") ||
    Object.hasOwn(renamed.data, "user_id")
  ) {
    throw new Error("Gate 3 session rename did not persist safely");
  }
  if (!deleted.ok || deleted.data !== GATE2_SMOKE_SESSION_ID) {
    throw new Error("Gate 3 session delete did not return the fixture ID");
  }
  if (!sessionsAfterDelete.ok) {
    throw new Error(
      `Gate 3 Sessions refresh failed: ${sessionsAfterDelete.error.code}`,
    );
  }
  if (
    sessionsAfterDelete.data.some(
      (candidate) =>
        candidate.conversation_id === GATE2_SMOKE_SESSION_ID ||
        candidate.conversation_id === created.data.conversation_id,
    )
  ) {
    throw new Error("Gate 3 fixture session is still present after deletion");
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
    if (record.tokens < 1 || record.loader.trim().length === 0) {
      throw new Error("Gate 3 indexed fixture has no parsed content");
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

export function assertGate3PartialSmoke(
  created: DesktopResult<IndexTask>,
  terminal: DesktopResult<IndexTask>,
  filesAfterPartial: DesktopResult<FileRecord[]>,
): string {
  if (!created.ok || !terminal.ok) {
    throw new Error("Gate 3 partial-failure task request failed");
  }
  const task = terminal.data;
  if (
    task.task_id !== created.data.task_id ||
    task.status !== "partial" ||
    task.error?.code !== "index_partial_failure" ||
    !task.retryable ||
    task.completed_files !== 2 ||
    task.success_count !== 1 ||
    task.failure_count !== 1 ||
    task.file_names.join(",") !== GATE3_PARTIAL_INPUT_NAMES.join(",") ||
    task.failures.length !== 1 ||
    task.failures[0]?.name !== GATE3_PARTIAL_INPUT_NAMES[0] ||
    !task.failures[0]?.retryable
  ) {
    const diagnostic = {
      status: task.status,
      error_code: task.error?.code ?? null,
      completed_files: task.completed_files,
      success_count: task.success_count,
      failure_count: task.failure_count,
      file_names: task.file_names,
      failure_names: task.failures.map((failure) => failure.name),
    };
    throw new Error(
      `Gate 3 partial failure was not reported safely: ${JSON.stringify(diagnostic)}`,
    );
  }
  if (!filesAfterPartial.ok) {
    throw new Error(
      `Gate 3 partial refresh failed: ${filesAfterPartial.error.code}`,
    );
  }
  const existing = filesAfterPartial.data.find(
    (record) => record.name === GATE3_PARTIAL_INPUT_NAMES[0],
  );
  const succeeded = filesAfterPartial.data.find(
    (record) => record.name === GATE3_PARTIAL_INPUT_NAMES[1],
  );
  if (
    !existing ||
    !succeeded ||
    Object.hasOwn(existing, "path") ||
    Object.hasOwn(succeeded, "path")
  ) {
    throw new Error("Gate 3 partial failure did not preserve both file records");
  }
  return task.task_id;
}

export function assertGate3PartialRetrySmoke(
  retried: DesktopResult<IndexTask>,
  terminal: DesktopResult<IndexTask>,
  filesAfterRetry: DesktopResult<FileRecord[]>,
): string[] {
  if (
    !retried.ok ||
    retried.data.total_files !== 1 ||
    retried.data.file_names[0] !== GATE3_PARTIAL_INPUT_NAMES[0]
  ) {
    throw new Error("Gate 3 partial retry selected the wrong files");
  }
  return assertGate3IndexSmoke(
    retried,
    terminal,
    filesAfterRetry,
    GATE3_PARTIAL_INPUT_NAMES,
  );
}

export function assertGate3InterruptedSmoke(
  created: DesktopResult<IndexTask>,
  failedRuntime: RuntimeStatus,
  restartedRuntime: RuntimeStatus,
  latest: DesktopResult<IndexTask | null>,
): string {
  if (!created.ok || !latest.ok || latest.data === null) {
    throw new Error("Gate 3 interrupted task request failed");
  }
  const task = latest.data;
  if (
    failedRuntime.state !== "failed" ||
    restartedRuntime.state !== "healthy" ||
    task.task_id !== created.data.task_id ||
    task.status !== "failed" ||
    task.stage !== "interrupted" ||
    task.error?.code !== "index_interrupted" ||
    !task.retryable ||
    task.completed_files !== 0 ||
    task.total_files !== 1 ||
    task.success_count !== 0 ||
    task.failure_count !== 0 ||
    task.failures.length !== 0 ||
    task.file_names[0] !== GATE3_INTERRUPTED_INPUT_NAME
  ) {
    throw new Error("Gate 3 Sidecar interruption was not restored safely");
  }
  return task.task_id;
}

export function assertGate3InterruptedRetrySmoke(
  retried: DesktopResult<IndexTask>,
  terminal: DesktopResult<IndexTask>,
  filesAfterRetry: DesktopResult<FileRecord[]>,
): string[] {
  if (
    !retried.ok ||
    retried.data.total_files !== 1 ||
    retried.data.file_names[0] !== GATE3_INTERRUPTED_INPUT_NAME
  ) {
    throw new Error("Gate 3 interrupted retry selected the wrong files");
  }
  return assertGate3IndexSmoke(
    retried,
    terminal,
    filesAfterRetry,
    [GATE3_INTERRUPTED_INPUT_NAME],
  );
}

export function assertGate3LargeFileSmoke(
  created: DesktopResult<IndexTask>,
  terminal: DesktopResult<IndexTask>,
  filesAfterIndex: DesktopResult<FileRecord[]>,
): string[] {
  const fileIds = assertGate3IndexSmoke(
    created,
    terminal,
    filesAfterIndex,
    [GATE3_LARGE_FILE_INPUT_NAME],
  );
  if (!filesAfterIndex.ok) {
    throw new Error("Gate 3 large-file refresh failed");
  }
  const record = filesAfterIndex.data.find(
    (candidate) => candidate.name === GATE3_LARGE_FILE_INPUT_NAME,
  );
  if (!record || record.size !== GATE3_LARGE_FILE_BYTES) {
    throw new Error("Gate 3 large-file record size changed");
  }
  return fileIds;
}

export function assertGate3DiskFullSmoke(
  failed: DesktopResult<IndexTask>,
): void {
  if (
    failed.ok ||
    failed.error.code !== "index_storage_full" ||
    !failed.error.retryable ||
    JSON.stringify(failed.error).includes("/private")
  ) {
    throw new Error("Gate 3 disk-full fault was not reported safely");
  }
}

export function assertGate3DatabaseLockedSmoke(
  created: DesktopResult<IndexTask>,
  terminal: DesktopResult<IndexTask>,
): string {
  if (!created.ok || !terminal.ok) {
    throw new Error("Gate 3 database-lock task request failed");
  }
  const task = terminal.data;
  if (
    task.task_id !== created.data.task_id ||
    task.status !== "failed" ||
    task.error?.code !== "index_database_locked" ||
    !task.retryable ||
    task.completed_files !== 1 ||
    task.success_count !== 0 ||
    task.failure_count !== 1 ||
    task.file_names[0] !== GATE3_DATABASE_LOCKED_INPUT_NAME ||
    task.failures[0]?.code !== "index_database_locked" ||
    task.failures[0]?.name !== GATE3_DATABASE_LOCKED_INPUT_NAME ||
    JSON.stringify(task).includes("/private")
  ) {
    throw new Error("Gate 3 database-lock fault was not reported safely");
  }
  return task.task_id;
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

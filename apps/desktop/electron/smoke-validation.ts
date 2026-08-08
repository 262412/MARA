import type { DoctorPayload } from "../shared/doctor-contracts";
import type { FileRecord } from "../shared/file-contracts";
import type { IndexTask } from "../shared/index-task-contracts";
import type {
  DesktopResult,
  RuntimeStatus,
} from "../shared/runtime-contracts";
import type { SessionSummary } from "../shared/session-contracts";

export const GATE2_SMOKE_FILE_ID = "gate2-smoke-file";
export const GATE2_SMOKE_SESSION_ID = "gate2-smoke-session";

type PackagedSmokeSnapshot = {
  status: RuntimeStatus;
  doctor: DesktopResult<DoctorPayload>;
  files: DesktopResult<FileRecord[]>;
  sessions: DesktopResult<SessionSummary[]>;
};

export function assertPackagedSmoke(
  snapshot: PackagedSmokeSnapshot,
  requireNonEmptyFixture: boolean,
): void {
  const { status, doctor, files, sessions } = snapshot;
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
    doctor.data.file_count !== 1 ||
    doctor.data.session_count !== 1 ||
    files.data.length !== 1 ||
    sessions.data.length !== 1 ||
    !fixtureFile ||
    !fixtureSession
  ) {
    throw new Error("Packaged app did not load the non-empty Gate 2 fixture");
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
): string {
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
  const indexed = filesAfterIndex.data.find(
    (record) => record.name === "gate3-index-smoke.txt",
  );
  if (!indexed) {
    throw new Error("Gate 3 indexed fixture is missing after Files refresh");
  }
  if (Object.hasOwn(indexed, "path")) {
    throw new Error("Gate 3 indexed fixture exposed a local path");
  }
  return indexed.file_id;
}

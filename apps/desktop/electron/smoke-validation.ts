import type { DoctorPayload } from "../shared/doctor-contracts";
import type { FileRecord } from "../shared/file-contracts";
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

import type { DoctorPayload } from "../../shared/doctor-contracts";
import type { FileRecord } from "../../shared/file-contracts";
import type { QueryTask } from "../../shared/query-contracts";
import type { RuntimeStatus } from "../../shared/runtime-contracts";
import { useLanguage } from "../i18n";
import type { ResourceState } from "../resource-state";
import { Icon } from "./Icon";

export type InspectorTab = "preview" | "sources" | "run";

type InspectorProps = {
  activeTab: InspectorTab;
  answerTask?: QueryTask;
  doctor: ResourceState<DoctorPayload>;
  files: ResourceState<FileRecord[]>;
  onClose: () => void;
  onRetryDoctor: () => void;
  onRetryFiles: () => void;
  onSelectTab: (tab: InspectorTab) => void;
  onToggleSource: (fileId: string) => void;
  runtime: RuntimeStatus;
  selectedSourceIds: string[];
};

export function Inspector({
  activeTab,
  answerTask,
  doctor,
  files,
  onClose,
  onRetryDoctor,
  onRetryFiles,
  onSelectTab,
  onToggleSource,
  runtime,
  selectedSourceIds,
}: InspectorProps) {
  const { t } = useLanguage();
  return (
    <aside className="inspector" aria-label={t("inspector.context")}>
      <div className="inspector-tabs" role="tablist" aria-label={t("inspector.view")}>
        {([
          ["preview", t("inspector.preview")],
          ["sources", t("inspector.sources")],
          ["run", t("inspector.run")],
        ] as const).map(([id, label]) => (
          <button
            aria-selected={activeTab === id}
            className={activeTab === id ? "active" : ""}
            key={id}
            onClick={() => onSelectTab(id)}
            role="tab"
            type="button"
          >
            {label}
          </button>
        ))}
        <button
          aria-label={t("inspector.close")}
          className="inspector-close"
          onClick={onClose}
          type="button"
        >
          <Icon name="panel" size={16} />
        </button>
      </div>

      {activeTab === "preview" ? (
        <Preview files={files} selectedSourceIds={selectedSourceIds} />
      ) : null}
      {activeTab === "sources" ? (
        <Sources
          files={files}
          onRetryFiles={onRetryFiles}
          onToggleSource={onToggleSource}
          selectedSourceIds={selectedSourceIds}
        />
      ) : null}
      {activeTab === "run" ? (
        <RunStatus
          doctor={doctor}
          answerTask={answerTask}
          onRetryDoctor={onRetryDoctor}
          runtime={runtime}
        />
      ) : null}
    </aside>
  );
}

function Preview({
  files,
  selectedSourceIds,
}: {
  files: ResourceState<FileRecord[]>;
  selectedSourceIds: string[];
}) {
  const { t } = useLanguage();
  const selected =
    files.status === "success"
      ? files.data.filter((file) => selectedSourceIds.includes(file.file_id))
      : [];
  return (
    <div className="inspector-content preview-content" role="tabpanel">
      <div className="preview-unavailable">
        <Icon name="files" size={22} />
        <h2>{t("inspector.previewUnavailable")}</h2>
        <p>{t("inspector.previewDetail")}</p>
        {selected.length > 0 ? (
          <ul>
            {selected.map((file) => <li key={file.file_id}>{file.name}</li>)}
          </ul>
        ) : (
          <span>{t("inspector.selectSources")}</span>
        )}
      </div>
    </div>
  );
}

function Sources({
  files,
  onRetryFiles,
  onToggleSource,
  selectedSourceIds,
}: {
  files: ResourceState<FileRecord[]>;
  onRetryFiles: () => void;
  onToggleSource: (fileId: string) => void;
  selectedSourceIds: string[];
}) {
  const { t } = useLanguage();
  return (
    <div className="inspector-content sources-content" role="tabpanel">
      <div className="section-heading">
        <div>
          <h2>{t("inspector.currentSources")}</h2>
          <p>{t("inspector.selectedSources", { count: selectedSourceIds.length })}</p>
        </div>
      </div>
      {files.status === "loading" ? (
        <InspectorState>{t("inspector.loadingSources")}</InspectorState>
      ) : null}
      {files.status === "failed" ? (
        <InspectorState role="alert">
          <span>{files.message}</span>
          <button className="small-button" onClick={onRetryFiles} type="button">
            {t("common.retry")}
          </button>
        </InspectorState>
      ) : null}
      {files.status === "success" && files.data.length === 0 ? (
        <InspectorState>{t("inspector.noIndexedFiles")}</InspectorState>
      ) : null}
      {files.status === "success"
        ? files.data.map((file, index) => {
            const selected = selectedSourceIds.includes(file.file_id);
            return (
              <label className={`source-row${selected ? " selected" : ""}`} key={file.file_id}>
                <input
                  checked={selected}
                  onChange={() => onToggleSource(file.file_id)}
                  type="checkbox"
                />
                <span className="source-index">{index + 1}</span>
                <span>
                  <strong>{file.name || t("common.unnamedFile")}</strong>
                  <small>
                    {t("common.tokensAndLoader", {
                      tokens: file.tokens.toLocaleString(),
                      loader: file.loader || t("common.unknown"),
                    })}
                  </small>
                </span>
                <span className="indexed">
                  {selected ? t("inspector.selected") : t("inspector.indexed")}
                </span>
              </label>
            );
          })
        : null}
    </div>
  );
}

function InspectorState({
  children,
  role,
}: {
  children: React.ReactNode;
  role?: "alert";
}) {
  return <div className="inspector-state" role={role}>{children}</div>;
}

function RunStatus({
  runtime,
  doctor,
  answerTask,
  onRetryDoctor,
}: {
  runtime: RuntimeStatus;
  doctor: ResourceState<DoctorPayload>;
  answerTask?: QueryTask;
  onRetryDoctor: () => void;
}) {
  const { t } = useLanguage();
  return (
    <div className="inspector-content run-content" role="tabpanel">
      <div className="runtime-card">
        <span className={`status-dot ${runtime.state === "healthy" ? "healthy" : ""}`} />
        <div>
          <strong>{t("inspector.sidecar")}</strong>
          <span>
            {runtime.state === "healthy"
              ? t("inspector.runningNormally")
              : runtime.message ?? runtime.state}
          </span>
        </div>
        <code>v{runtime.version ?? "—"}</code>
      </div>
      <h2>Doctor</h2>
      {doctor.status === "loading" ? (
        <p className="doctor-state">{t("inspector.loadingDoctor")}</p>
      ) : null}
      {doctor.status === "failed" ? (
        <div className="doctor-state failed" role="alert">
          <strong>{doctor.message}</strong>
          <span>
            {doctor.error?.request_id
              ? t("common.requestId", { id: doctor.error.request_id })
              : t("inspector.checkSidecar")}
          </span>
          <button className="small-button" onClick={onRetryDoctor} type="button">
            {t("common.retry")}
          </button>
        </div>
      ) : null}
      {doctor.status === "success" ? <DoctorSummary doctor={doctor.data} /> : null}
      {answerTask?.error?.persistence ? (
        <QueryPersistenceSummary task={answerTask} />
      ) : null}
      <button className="diagnostics-button" disabled type="button">
        {t("inspector.diagnosticsUnavailable")}
      </button>
    </div>
  );
}

function QueryPersistenceSummary({ task }: { task: QueryTask }) {
  const { t } = useLanguage();
  const diagnostic = task.error?.persistence;
  if (!diagnostic) {
    return null;
  }
  return (
    <section
      className="query-persistence-diagnostic"
      aria-label={t("inspector.answerDiagnostics")}
    >
      <strong>{t("inspector.answerDiagnostics")}</strong>
      <code>{diagnostic.fingerprint}</code>
      <small>{t("inspector.persistenceTask", { id: task.task_id })}</small>
      <small>
        {diagnostic.operation} · errno {diagnostic.errno ?? "—"} · WinError{" "}
        {diagnostic.winerror ?? "—"} · retry {diagnostic.retry_count} · probe{" "}
        {diagnostic.post_failure_probe} · smoke {String(diagnostic.smoke_mode)}
      </small>
    </section>
  );
}

function DoctorSummary({ doctor }: { doctor: DoctorPayload }) {
  const { t } = useLanguage();
  return (
    <div className={doctor.ok ? "doctor-summary" : "doctor-summary degraded"}>
      <strong>
        {doctor.ok ? t("inspector.doctorPassed") : t("inspector.doctorIssues")}
      </strong>
      <dl>
        <div><dt>{t("common.file")}</dt><dd>{doctor.file_count}</dd></div>
        <div><dt>{t("common.session")}</dt><dd>{doctor.session_count}</dd></div>
        <div><dt>{t("common.llm")}</dt><dd>{doctor.llm_default || t("inspector.notConfigured")}</dd></div>
        <div><dt>{t("common.embedding")}</dt><dd>{doctor.embedding_default || t("inspector.notConfigured")}</dd></div>
      </dl>
      {doctor.issues.map((issue) => <p className="doctor-issue" key={issue}>{issue}</p>)}
      {doctor.warnings.map((warning) => <p className="doctor-warning" key={warning}>{warning}</p>)}
    </div>
  );
}

import type { DoctorPayload } from "../../shared/doctor-contracts";
import type { FileRecord } from "../../shared/file-contracts";
import type { QueryTask } from "../../shared/query-contracts";
import type { RuntimeStatus } from "../../shared/runtime-contracts";
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
  return (
    <aside className="inspector" aria-label="上下文检查器">
      <div className="inspector-tabs" role="tablist" aria-label="检查器视图">
        {([
          ["preview", "Preview"],
          ["sources", "Sources"],
          ["run", "Run"],
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
          aria-label="关闭检查器"
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
  const selected =
    files.status === "success"
      ? files.data.filter((file) => selectedSourceIds.includes(file.file_id))
      : [];
  return (
    <div className="inspector-content preview-content" role="tabpanel">
      <div className="preview-unavailable">
        <Icon name="files" size={22} />
        <h2>预览尚未接入</h2>
        <p>本切片只显示真实来源身份；原生文档预览将在后续 Gate 3 切片实现。</p>
        {selected.length > 0 ? (
          <ul>
            {selected.map((file) => <li key={file.file_id}>{file.name}</li>)}
          </ul>
        ) : (
          <span>请先在 Sources 中选择文件。</span>
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
  return (
    <div className="inspector-content sources-content" role="tabpanel">
      <div className="section-heading">
        <div>
          <h2>当前来源</h2>
          <p>已选择 {selectedSourceIds.length} 个来源</p>
        </div>
      </div>
      {files.status === "loading" ? <InspectorState>正在读取来源…</InspectorState> : null}
      {files.status === "failed" ? (
        <InspectorState role="alert">
          <span>{files.message}</span>
          <button className="small-button" onClick={onRetryFiles} type="button">重试</button>
        </InspectorState>
      ) : null}
      {files.status === "success" && files.data.length === 0 ? (
        <InspectorState>还没有已索引文件。请先从 Files 导入并完成索引。</InspectorState>
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
                  <strong>{file.name || "未命名文件"}</strong>
                  <small>{file.tokens.toLocaleString()} tokens · {file.loader || "未知读取器"}</small>
                </span>
                <span className="indexed">{selected ? "已选择" : "已索引"}</span>
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
  return (
    <div className="inspector-content run-content" role="tabpanel">
      <div className="runtime-card">
        <span className={`status-dot ${runtime.state === "healthy" ? "healthy" : ""}`} />
        <div>
          <strong>Python Sidecar</strong>
          <span>{runtime.state === "healthy" ? "运行正常" : runtime.message ?? runtime.state}</span>
        </div>
        <code>v{runtime.version ?? "—"}</code>
      </div>
      <h2>Doctor</h2>
      {doctor.status === "loading" ? (
        <p className="doctor-state">正在运行 Doctor…</p>
      ) : null}
      {doctor.status === "failed" ? (
        <div className="doctor-state failed" role="alert">
          <strong>{doctor.message}</strong>
          <span>
            {doctor.error?.request_id
              ? `请求 ID：${doctor.error.request_id}`
              : "请检查 Sidecar 后重试。"}
          </span>
          <button className="small-button" onClick={onRetryDoctor} type="button">
            重试
          </button>
        </div>
      ) : null}
      {doctor.status === "success" ? <DoctorSummary doctor={doctor.data} /> : null}
      {answerTask?.error?.persistence ? (
        <QueryPersistenceSummary task={answerTask} />
      ) : null}
      <button className="diagnostics-button" disabled type="button">诊断中心将在后续切片启用</button>
    </div>
  );
}

function QueryPersistenceSummary({ task }: { task: QueryTask }) {
  const diagnostic = task.error?.persistence;
  if (!diagnostic) {
    return null;
  }
  return (
    <section className="query-persistence-diagnostic" aria-label="回答状态诊断">
      <strong>回答状态诊断</strong>
      <code>{diagnostic.fingerprint}</code>
      <small>任务 ID：{task.task_id}</small>
      <small>
        {diagnostic.operation} · errno {diagnostic.errno ?? "—"} · WinError{" "}
        {diagnostic.winerror ?? "—"} · retry {diagnostic.retry_count} · probe{" "}
        {diagnostic.post_failure_probe} · smoke {String(diagnostic.smoke_mode)}
      </small>
    </section>
  );
}

function DoctorSummary({ doctor }: { doctor: DoctorPayload }) {
  return (
    <div className={doctor.ok ? "doctor-summary" : "doctor-summary degraded"}>
      <strong>{doctor.ok ? "Doctor 通过" : "Doctor 发现问题"}</strong>
      <dl>
        <div><dt>文件</dt><dd>{doctor.file_count}</dd></div>
        <div><dt>会话</dt><dd>{doctor.session_count}</dd></div>
        <div><dt>LLM</dt><dd>{doctor.llm_default || "未配置"}</dd></div>
        <div><dt>Embedding</dt><dd>{doctor.embedding_default || "未配置"}</dd></div>
      </dl>
      {doctor.issues.map((issue) => <p className="doctor-issue" key={issue}>{issue}</p>)}
      {doctor.warnings.map((warning) => <p className="doctor-warning" key={warning}>{warning}</p>)}
    </div>
  );
}

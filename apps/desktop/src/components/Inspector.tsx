import type { DoctorPayload } from "../../shared/doctor-contracts";
import type { RuntimeStatus } from "../../shared/runtime-contracts";
import type { ResourceState } from "../resource-state";
import { Icon } from "./Icon";

export type InspectorTab = "preview" | "sources" | "run";

type InspectorProps = {
  activeTab: InspectorTab;
  onClose: () => void;
  onSelectTab: (tab: InspectorTab) => void;
  runtime: RuntimeStatus;
  doctor: ResourceState<DoctorPayload>;
  onRetryDoctor: () => void;
};

export function Inspector({
  activeTab,
  onClose,
  onSelectTab,
  runtime,
  doctor,
  onRetryDoctor,
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

      {activeTab === "preview" ? <Preview /> : null}
      {activeTab === "sources" ? <Sources /> : null}
      {activeTab === "run" ? (
        <RunStatus
          doctor={doctor}
          onRetryDoctor={onRetryDoctor}
          runtime={runtime}
        />
      ) : null}
    </aside>
  );
}

function Preview() {
  return (
    <div className="inspector-content preview-content" role="tabpanel">
      <div className="file-heading">
        <span className="file-type">PDF</span>
        <div>
          <strong>agent_verifiable_trajectories.pdf</strong>
          <span>第 4 页，共 18 页</span>
        </div>
        <button aria-label="在文件管理器中显示" className="icon-button" type="button">
          <Icon name="files" size={16} />
        </button>
      </div>
      <div className="preview-toolbar">
        <button type="button">−</button>
        <span>84%</span>
        <button type="button">＋</button>
        <span className="page-control">4 / 18</span>
      </div>
      <div className="document-stage">
        <article className="paper">
          <div className="paper-kicker">RESEARCH OVERVIEW</div>
          <h2>Verifiable Interactive Trajectories for Generalist Agents</h2>
          <p className="paper-authors">MARA Research Collection · 2026</p>
          <h3>2. Verification across the execution chain</h3>
          <p>
            Reliable evaluation requires stable identities for the source,
            action, observation and evidence attached to every step.
          </p>
          <p className="highlight">
            Trajectory verification should connect formal constraints,
            executable outcomes and evidence provenance.
          </p>
          <p>
            This identity chain allows failures to be attributed to planning,
            tool execution, environment response or the evaluator itself.
          </p>
        </article>
      </div>
    </div>
  );
}

function Sources() {
  return (
    <div className="inspector-content sources-content" role="tabpanel">
      <div className="section-heading">
        <div>
          <h2>当前来源</h2>
          <p>8 个文件已选择，全部索引完成</p>
        </div>
        <button className="small-button" type="button">管理</button>
      </div>
      {[
        ["agent_verifiable_trajectories.pdf", "18 页 · PDF"],
        ["long_horizon_synthesis.docx", "24 页 · DOCX"],
        ["multi_agent_coordination.pdf", "31 页 · PDF"],
        ["recursive_agents_notes.md", "6 页 · Markdown"],
      ].map(([name, detail], index) => (
        <button className="source-row" key={name} type="button">
          <span className="source-index">{index + 1}</span>
          <span>
            <strong>{name}</strong>
            <small>{detail}</small>
          </span>
          <span className="indexed">已索引</span>
        </button>
      ))}
    </div>
  );
}

function RunStatus({
  runtime,
  doctor,
  onRetryDoctor,
}: {
  runtime: RuntimeStatus;
  doctor: ResourceState<DoctorPayload>;
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
      {doctor.status === "success" ? (
        <DoctorSummary doctor={doctor.data} />
      ) : null}
      <button className="diagnostics-button" type="button">打开诊断中心</button>
    </div>
  );
}

function DoctorSummary({ doctor }: { doctor: DoctorPayload }) {
  return (
    <div className={doctor.ok ? "doctor-summary" : "doctor-summary degraded"}>
      <strong>{doctor.ok ? "Doctor 通过" : "Doctor 发现问题"}</strong>
      <dl>
        <div>
          <dt>文件</dt>
          <dd>{doctor.file_count}</dd>
        </div>
        <div>
          <dt>会话</dt>
          <dd>{doctor.session_count}</dd>
        </div>
        <div>
          <dt>LLM</dt>
          <dd>{doctor.llm_default || "未配置"}</dd>
        </div>
        <div>
          <dt>Embedding</dt>
          <dd>{doctor.embedding_default || "未配置"}</dd>
        </div>
      </dl>
      {doctor.issues.map((issue) => (
        <p className="doctor-issue" key={issue}>{issue}</p>
      ))}
      {doctor.warnings.map((warning) => (
        <p className="doctor-warning" key={warning}>{warning}</p>
      ))}
    </div>
  );
}

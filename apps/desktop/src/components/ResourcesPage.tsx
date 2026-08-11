import type { DoctorPayload } from "../../shared/doctor-contracts";
import type { RuntimeStatus } from "../../shared/runtime-contracts";
import type { ResourceState } from "../resource-state";

type ResourcesPageProps = {
  doctor: ResourceState<DoctorPayload>;
  onOpenSettings: () => void;
  onRetry: () => void;
  runtime: RuntimeStatus;
};

export function ResourcesPage({
  doctor,
  onOpenSettings,
  onRetry,
  runtime,
}: ResourcesPageProps) {
  const data = doctor.status === "success" ? doctor.data : undefined;
  return (
    <main className="standalone-page" id="main-workspace">
      <header className="standalone-header">
        <div>
          <p className="eyebrow">Resources</p>
          <h1 data-page-title tabIndex={-1}>资源状态</h1>
          <p>显示 Desktop 当前真实运行能力，不启用尚未支持的资源。</p>
        </div>
        <button onClick={onRetry} type="button">重新检查</button>
      </header>
      {doctor.status === "loading" ? <PageState>正在读取资源状态…</PageState> : null}
      {doctor.status === "failed" ? (
        <PageState role="alert">
          {doctor.message} · 请求 ID：{doctor.error?.request_id ?? "未知"}
        </PageState>
      ) : null}
      <section className="resource-grid" aria-label="资源能力">
        <ResourceCard
          detail={data ? `${data.index_name} · ${data.file_count} 个文件` : "正在检查"}
          name="Index"
          state={data ? (data.indexing_ready ? "可用" : "未准备") : "未知"}
        />
        <ResourceCard
          detail={data?.query_model || data?.query_message || "正在检查"}
          name="LLM"
          state={data ? (data.query_ready ? data.query_provider || "可用" : "未配置") : "未知"}
        />
        <ResourceCard
          detail={data?.embedding_model || data?.indexing_message || "正在检查"}
          name="Embedding"
          state={data ? (data.indexing_ready ? data.embedding_provider || "可用" : "未配置") : "未知"}
        />
        <ResourceCard
          detail="Desktop 当前未提供 Reranking 配置。"
          name="Reranking"
          state="不支持"
        />
        <ResourceCard detail="Desktop 当前未启用 MCP。" name="MCP" state="不支持" />
        <ResourceCard
          detail="当前 Desktop 使用本地默认用户作用域。"
          name="用户"
          state="不可配置"
        />
      </section>
      <section className="resource-runtime" aria-label="运行状态">
        <h2>运行状态</h2>
        <dl>
          <div><dt>Sidecar</dt><dd>{runtime.state}</dd></div>
          <div><dt>版本</dt><dd>{runtime.version || "未知"}</dd></div>
          <div><dt>Doctor</dt><dd>{data?.ok ? "通过" : "需要处理"}</dd></div>
        </dl>
        <button onClick={onOpenSettings} type="button">打开模型设置</button>
      </section>
    </main>
  );
}

function ResourceCard({
  detail,
  name,
  state,
}: {
  detail: string;
  name: string;
  state: string;
}) {
  return (
    <article className="resource-card">
      <div><h2>{name}</h2><strong>{state}</strong></div>
      <p>{detail}</p>
    </article>
  );
}

function PageState({
  children,
  role,
}: {
  children: React.ReactNode;
  role?: "alert";
}) {
  return <div className="page-state" role={role}>{children}</div>;
}

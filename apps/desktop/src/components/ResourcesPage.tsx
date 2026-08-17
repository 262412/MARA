import type { DoctorPayload } from "../../shared/doctor-contracts";
import type { RuntimeStatus } from "../../shared/runtime-contracts";
import { useLanguage } from "../i18n";
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
  const { t } = useLanguage();
  const data = doctor.status === "success" ? doctor.data : undefined;
  return (
    <main className="standalone-page" id="main-workspace">
      <header className="standalone-header">
        <div>
          <p className="eyebrow">{t("resources.eyebrow")}</p>
          <h1 data-page-title tabIndex={-1}>{t("resources.title")}</h1>
          <p>{t("resources.description")}</p>
        </div>
        <button onClick={onRetry} type="button">{t("resources.retry")}</button>
      </header>
      {doctor.status === "loading" ? <PageState>{t("resources.loading")}</PageState> : null}
      {doctor.status === "failed" ? (
        <PageState role="alert">
          {doctor.message} · {t("common.requestId", {
            id: doctor.error?.request_id ?? t("common.unknown"),
          })}
        </PageState>
      ) : null}
      <section className="resource-grid" aria-label={t("resources.resourceAria")}>
        <ResourceCard
          detail={
            data
              ? t("resources.indexDetail", {
                  name: data.index_name,
                  count: data.file_count,
                })
              : t("common.checking")
          }
          name={t("common.index")}
          state={data
            ? data.indexing_ready
              ? t("common.available")
              : t("common.notReady")
            : t("common.unknown")}
        />
        <ResourceCard
          detail={data?.query_model || data?.query_message || t("common.checking")}
          name={t("common.llm")}
          state={data
            ? data.query_ready
              ? data.query_provider || t("common.available")
              : t("common.notConfigured")
            : t("common.unknown")}
        />
        <ResourceCard
          detail={data?.embedding_model || data?.indexing_message || t("common.checking")}
          name={t("common.embedding")}
          state={data
            ? data.indexing_ready
              ? data.embedding_provider || t("common.available")
              : t("common.notConfigured")
            : t("common.unknown")}
        />
        <ResourceCard
          detail={t("resources.rerankingDetail")}
          name={t("resources.reranking")}
          state={t("common.unsupported")}
        />
        <ResourceCard
          detail={t("resources.mcpDetail")}
          name={t("resources.mcp")}
          state={t("common.unsupported")}
        />
        <ResourceCard
          detail={t("resources.userDetail")}
          name={t("resources.user")}
          state={t("common.notConfigurable")}
        />
      </section>
      <section className="resource-runtime" aria-label={t("resources.runtimeAria")}>
        <h2>{t("resources.runtimeTitle")}</h2>
        <dl>
          <div><dt>Sidecar</dt><dd>{runtime.state}</dd></div>
          <div><dt>{t("resources.version")}</dt><dd>{runtime.version || t("common.unknown")}</dd></div>
          <div><dt>{t("resources.doctor")}</dt><dd>{data?.ok ? t("common.passed") : t("common.needsAttention")}</dd></div>
        </dl>
        <button onClick={onOpenSettings} type="button">{t("resources.openSettings")}</button>
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

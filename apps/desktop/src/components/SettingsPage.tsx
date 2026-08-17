import { useEffect, useState } from "react";

import type { DoctorPayload } from "../../shared/doctor-contracts";
import type {
  ModelProvider,
  ModelRouteInput,
  ModelRouteStatus,
  ModelSettingsInput,
  ModelSettingsStatus,
} from "../../shared/model-contracts";
import type { SidecarError } from "../../shared/runtime-contracts";
import { useLanguage } from "../i18n";
import type { ResourceState } from "../resource-state";

type SettingsPageProps = {
  doctor: ResourceState<DoctorPayload>;
  onRetry: () => void;
  onSave: (settings: ModelSettingsInput) => void;
  saveError?: SidecarError;
  savePending: boolean;
  settings: ResourceState<ModelSettingsStatus>;
};

export function SettingsPage({
  doctor,
  onRetry,
  onSave,
  saveError,
  savePending,
  settings,
}: SettingsPageProps) {
  const { language, setLanguage, t } = useLanguage();
  const [chat, setChat] = useState<ModelRouteInput>(emptyRoute());
  const [embedding, setEmbedding] = useState<ModelRouteInput>(emptyRoute());

  useEffect(() => {
    if (settings.status === "success") {
      setChat(editableRoute(settings.data.chat));
      setEmbedding(editableRoute(settings.data.embedding));
    }
  }, [settings]);

  const status = settings.status === "success" ? settings.data : undefined;
  return (
    <main className="standalone-page settings-page" id="main-workspace">
      <header className="standalone-header">
        <div>
          <p className="eyebrow">{t("settings.eyebrow")}</p>
          <h1 data-page-title tabIndex={-1}>{t("settings.title")}</h1>
          <p>{t("settings.description")}</p>
        </div>
        <button onClick={onRetry} type="button">{t("settings.reload")}</button>
      </header>
      {settings.status === "loading" ? <PageState>{t("settings.loading")}</PageState> : null}
      {settings.status === "failed" ? (
        <PageState role="alert">
          {settings.message} · {t("common.requestId", {
            id: settings.error?.request_id ?? t("common.unknown"),
          })}
        </PageState>
      ) : null}
      {status && !status.secure_storage_available ? (
        <div className="settings-warning" role="status">
          {t("settings.secureStorageWarning")}
        </div>
      ) : null}
      {status?.source === "compatibility" ? (
        <div className="settings-compatibility">
          {t("settings.compatibilityNotice")}
        </div>
      ) : null}
      <section className="language-settings" aria-labelledby="language-settings-title">
        <div>
          <h2 id="language-settings-title">{t("settings.languageTitle")}</h2>
          <p>{t("settings.languageDescription")}</p>
        </div>
        <label htmlFor="language-select">
          {t("settings.languageLabel")}
          <select
            id="language-select"
            name="language"
            onChange={(event) => setLanguage(event.target.value as "en" | "zh")}
            value={language}
          >
            <option value="en">{t("settings.english")}</option>
            <option value="zh">{t("settings.chinese")}</option>
          </select>
        </label>
      </section>
      <ReadinessSummary doctor={doctor} />
      <form
        className="model-settings-form"
        onSubmit={(event) => {
          event.preventDefault();
          onSave({ chat, embedding });
        }}
      >
        <ModelRouteEditor
          kind="chat"
          onChange={setChat}
          route={chat}
          status={status?.chat}
          title={t("settings.chatLlm")}
        />
        <ModelRouteEditor
          kind="embedding"
          onChange={setEmbedding}
          route={embedding}
          status={status?.embedding}
          title={t("settings.embedding")}
        />
        {saveError ? (
          <div className="settings-error" role="alert">
            <strong>{saveError.message}</strong>
            <span>{t("common.requestId", { id: saveError.request_id })}</span>
          </div>
        ) : null}
        <div className="settings-actions">
          <button disabled={savePending || settings.status !== "success"} type="submit">
            {savePending ? t("settings.savePending") : t("settings.save")}
          </button>
        </div>
      </form>
    </main>
  );
}

function ModelRouteEditor({
  kind,
  onChange,
  route,
  status,
  title,
}: {
  kind: "chat" | "embedding";
  onChange: (route: ModelRouteInput) => void;
  route: ModelRouteInput;
  status?: ModelRouteStatus;
  title: string;
}) {
  const { t } = useLanguage();
  const update = (values: Partial<ModelRouteInput>) => onChange({ ...route, ...values });
  return (
    <fieldset className="model-route-card">
      <legend>{title}</legend>
      <label>
        {t("settings.provider")}
        <select
          name={`${kind}.provider`}
          onChange={(event) => onChange(defaultRoute(event.target.value as ModelProvider, kind))}
          value={route.provider}
        >
          <option value="none">{t("settings.notConfigured")}</option>
          <option value="openai_compatible">OpenAI-compatible</option>
          <option value="azure_openai">Azure OpenAI</option>
          <option value="ollama">{t("settings.localOllama")}</option>
        </select>
      </label>
      {route.provider !== "none" ? (
        <>
          <label>
            Base URL
            <input
              name={`${kind}.base_url`}
              onChange={(event) => update({ base_url: event.target.value })}
              required
              type="url"
              value={route.base_url}
            />
          </label>
          <label>
            {route.provider === "azure_openai"
              ? t("settings.deployment")
              : t("settings.model")}
            <input
              name={`${kind}.model`}
              onChange={(event) => update({ model: event.target.value })}
              required
              value={route.model}
            />
          </label>
          {route.provider === "azure_openai" ? (
            <label>
              {t("settings.apiVersion")}
              <input
                name={`${kind}.api_version`}
                onChange={(event) => update({ api_version: event.target.value })}
                required
                value={route.api_version}
              />
            </label>
          ) : null}
          {route.provider !== "ollama" ? (
            <label>
              {t("settings.apiKey")}
              <input
                autoComplete="new-password"
                name={`${kind}.credential`}
                onChange={(event) => update({ credential: event.target.value || null })}
                placeholder={
                  status?.credential_present
                    ? t("settings.savedCredentialPlaceholder")
                    : t("settings.enterCredential")
                }
                type="password"
                value={route.credential ?? ""}
              />
            </label>
          ) : null}
          <small className="credential-state">
            {credentialDescription(status, route.provider, t)}
          </small>
        </>
      ) : (
        <p>{t("settings.failClosed")}</p>
      )}
    </fieldset>
  );
}

function ReadinessSummary({ doctor }: { doctor: ResourceState<DoctorPayload> }) {
  const { t } = useLanguage();
  if (doctor.status === "loading") {
    return <PageState>{t("settings.readinessLoading")}</PageState>;
  }
  if (doctor.status === "failed") {
    return <PageState role="alert">{t("settings.readinessFailed")}</PageState>;
  }
  return (
    <section className="settings-readiness" aria-label={t("settings.readinessAria")}>
      <div>
        <strong>{t("common.query")}</strong>
        <span>{doctor.data.query_ready ? t("settings.prepared") : doctor.data.query_message}</span>
      </div>
      <div>
        <strong>{t("common.index")}</strong>
        <span>{doctor.data.indexing_ready ? t("settings.prepared") : doctor.data.indexing_message}</span>
      </div>
    </section>
  );
}

function defaultRoute(
  provider: ModelProvider,
  kind: "chat" | "embedding",
): ModelRouteInput {
  if (provider === "openai_compatible") {
    return {
      provider,
      base_url: "https://api.openai.com/v1",
      model: kind === "chat" ? "gpt-4o-mini" : "text-embedding-3-small",
      api_version: "",
      credential: null,
    };
  }
  if (provider === "azure_openai") {
    return {
      provider,
      base_url: "",
      model: "",
      api_version: "2024-02-15-preview",
      credential: null,
    };
  }
  if (provider === "ollama") {
    return {
      provider,
      base_url: "http://127.0.0.1:11434/v1",
      model: kind === "chat" ? "qwen2.5:7b" : "nomic-embed-text",
      api_version: "",
      credential: null,
    };
  }
  return emptyRoute();
}

function emptyRoute(): ModelRouteInput {
  return {
    provider: "none",
    base_url: "",
    model: "",
    api_version: "",
    credential: null,
  };
}

function editableRoute(route: ModelRouteStatus): ModelRouteInput {
  return {
    provider: route.provider,
    base_url: route.base_url,
    model: route.model,
    api_version: route.api_version,
    credential: null,
  };
}

function credentialDescription(
  status: ModelRouteStatus | undefined,
  provider: ModelProvider,
  t: ReturnType<typeof useLanguage>["t"],
): string {
  if (provider === "ollama") {
    return t("settings.ollamaNoApiKey");
  }
  if (!status?.credential_present) {
    return t("settings.noCredential");
  }
  return status.credential_storage === "secure"
    ? t("settings.secureCredential")
    : t("settings.sessionCredential");
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

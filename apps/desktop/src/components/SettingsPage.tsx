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
          <p className="eyebrow">Settings</p>
          <h1 data-page-title tabIndex={-1}>模型设置</h1>
          <p>Chat LLM 与 Embedding 独立配置；保存后仅重启 Sidecar。</p>
        </div>
        <button onClick={onRetry} type="button">重新读取</button>
      </header>
      {settings.status === "loading" ? <PageState>正在读取模型设置…</PageState> : null}
      {settings.status === "failed" ? (
        <PageState role="alert">
          {settings.message} · 请求 ID：{settings.error?.request_id ?? "未知"}
        </PageState>
      ) : null}
      {status && !status.secure_storage_available ? (
        <div className="settings-warning" role="status">
          系统安全加密当前不可用。新凭据仅保留到本次应用会话，退出后需要重新输入。
        </div>
      ) : null}
      {status?.source === "compatibility" ? (
        <div className="settings-compatibility">
          现有环境或 Desktop `.env` 仍会兼容读取；保存此页面不会改写旧文件。
        </div>
      ) : null}
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
          title="Chat LLM"
        />
        <ModelRouteEditor
          kind="embedding"
          onChange={setEmbedding}
          route={embedding}
          status={status?.embedding}
          title="Embedding"
        />
        {saveError ? (
          <div className="settings-error" role="alert">
            <strong>{saveError.message}</strong>
            <span>请求 ID：{saveError.request_id}</span>
          </div>
        ) : null}
        <div className="settings-actions">
          <button disabled={savePending || settings.status !== "success"} type="submit">
            {savePending ? "正在保存并重启…" : "保存并应用"}
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
  const update = (values: Partial<ModelRouteInput>) => onChange({ ...route, ...values });
  return (
    <fieldset className="model-route-card">
      <legend>{title}</legend>
      <label>
        Provider
        <select
          name={`${kind}.provider`}
          onChange={(event) => onChange(defaultRoute(event.target.value as ModelProvider, kind))}
          value={route.provider}
        >
          <option value="none">未配置</option>
          <option value="openai_compatible">OpenAI-compatible</option>
          <option value="azure_openai">Azure OpenAI</option>
          <option value="ollama">本地 Ollama</option>
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
            {route.provider === "azure_openai" ? "Deployment" : "Model"}
            <input
              name={`${kind}.model`}
              onChange={(event) => update({ model: event.target.value })}
              required
              value={route.model}
            />
          </label>
          {route.provider === "azure_openai" ? (
            <label>
              API version
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
              API key
              <input
                autoComplete="new-password"
                name={`${kind}.credential`}
                onChange={(event) => update({ credential: event.target.value || null })}
                placeholder={status?.credential_present ? "已安全保存；留空保持不变" : "输入凭据"}
                type="password"
                value={route.credential ?? ""}
              />
            </label>
          ) : null}
          <small className="credential-state">
            {credentialDescription(status, route.provider)}
          </small>
        </>
      ) : (
        <p>该能力保持未配置，相关操作会 fail closed。</p>
      )}
    </fieldset>
  );
}

function ReadinessSummary({ doctor }: { doctor: ResourceState<DoctorPayload> }) {
  if (doctor.status === "loading") {
    return <PageState>正在检查模型 readiness…</PageState>;
  }
  if (doctor.status === "failed") {
    return <PageState role="alert">无法读取 Doctor readiness。</PageState>;
  }
  return (
    <section className="settings-readiness" aria-label="模型准备状态">
      <div>
        <strong>查询</strong>
        <span>{doctor.data.query_ready ? "已准备" : doctor.data.query_message}</span>
      </div>
      <div>
        <strong>索引</strong>
        <span>{doctor.data.indexing_ready ? "已准备" : doctor.data.indexing_message}</span>
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
): string {
  if (provider === "ollama") {
    return "本地 Ollama 不要求 API key。";
  }
  if (!status?.credential_present) {
    return "尚未保存凭据。";
  }
  return status.credential_storage === "secure"
    ? "凭据已由操作系统安全存储保护。"
    : "凭据仅保留到本次应用会话。";
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

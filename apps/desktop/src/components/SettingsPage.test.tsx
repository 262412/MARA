import assert from "node:assert/strict";
import test from "node:test";

import type { DoctorPayload } from "../../shared/doctor-contracts";
import type { ModelSettingsInput, ModelSettingsStatus } from "../../shared/model-contracts";
import type { SidecarError } from "../../shared/runtime-contracts";
import { click, dispatch, renderInDom, setInputValue } from "../test-dom";
import { SettingsPage } from "./SettingsPage";

const status: ModelSettingsStatus = {
  chat: {
    provider: "none",
    base_url: "",
    model: "",
    api_version: "",
    credential_present: false,
    credential_storage: "none",
  },
  embedding: {
    provider: "none",
    base_url: "",
    model: "",
    api_version: "",
    credential_present: false,
    credential_storage: "none",
  },
  secure_storage_available: false,
  source: "compatibility",
};

const doctor = {
  ok: false,
  app_name: "MARA",
  default_user_id: "default",
  index_name: "File Collection",
  index_id: 1,
  llm_default: "",
  embedding_default: "",
  file_count: 0,
  session_count: 0,
  graph_cache_dir: "Desktop managed cache",
  issues: [],
  warnings: [],
  query_ready: false,
  query_issue_code: "llm_not_configured",
  query_message: "Configure a supported chat model before asking questions.",
  query_action: "configure_llm",
  query_retryable: false,
  query_persistence_ready: true,
  query_persistence_issue_code: null,
  query_persistence_message: "Answer state storage is ready.",
  query_persistence_action: "none",
  query_persistence_retryable: false,
  indexing_ready: false,
  indexing_issue_code: "embedding_not_configured",
  indexing_message: "Configure a supported embedding model before indexing files.",
  indexing_action: "configure_embedding",
  indexing_retryable: false,
  query_provider: "",
  query_model: "",
  embedding_provider: "",
  embedding_model: "",
  settings_revision: "",
  sidecar_pid: 4321,
  route_fingerprint: "",
  request_id: "doctor-request",
} as DoctorPayload;

test("Settings saves separate chat and embedding routes through one typed action", async () => {
  const saved: ModelSettingsInput[] = [];
  const rendered = await renderInDom(
    <SettingsPage
      doctor={{ status: "success", data: doctor }}
      onRetry={() => undefined}
      onSave={(settings) => saved.push(settings)}
      savePending={false}
      settings={{ status: "success", data: status }}
    />,
  );
  try {
    const selects = rendered.document.querySelectorAll<HTMLSelectElement>("select");
    assert.equal(selects.length, 3);
    await selectValue(
      rendered.document.querySelector<HTMLSelectElement>("select[name='chat.provider']")!,
      "openai_compatible",
    );
    await selectValue(
      rendered.document.querySelector<HTMLSelectElement>("select[name='embedding.provider']")!,
      "ollama",
    );
    const fields = rendered.document.querySelectorAll<HTMLInputElement>("input");
    await setInputValue(inputByName(fields, "chat.base_url"), "https://api.openai.com/v1");
    await setInputValue(inputByName(fields, "chat.model"), "gpt-4o-mini");
    await setInputValue(inputByName(fields, "chat.credential"), "new-secret");
    await setInputValue(inputByName(fields, "embedding.base_url"), "http://127.0.0.1:11434/v1");
    await setInputValue(inputByName(fields, "embedding.model"), "nomic-embed-text");
    await click(buttonWithText(rendered.document, "Save and apply"));

    assert.deepEqual(saved, [
      {
        chat: {
          provider: "openai_compatible",
          base_url: "https://api.openai.com/v1",
          model: "gpt-4o-mini",
          api_version: "",
          credential: "new-secret",
        },
        embedding: {
          provider: "ollama",
          base_url: "http://127.0.0.1:11434/v1",
          model: "nomic-embed-text",
          api_version: "",
          credential: null,
        },
      },
    ]);
    assert.match(rendered.document.body.textContent ?? "", /remain only for this app session/);
  } finally {
    await rendered.cleanup();
  }
});

test("Settings renders a stable save failure and request id without a secret", async () => {
  const error: SidecarError = {
    code: "model_settings_apply_failed",
    message: "MARA Desktop could not save and apply the model settings.",
    details: null,
    retryable: false,
    request_id: "settings-request-1",
  };
  const rendered = await renderInDom(
    <SettingsPage
      doctor={{ status: "success", data: doctor }}
      onRetry={() => undefined}
      onSave={() => undefined}
      saveError={error}
      savePending={false}
      settings={{ status: "success", data: status }}
    />,
  );
  try {
    const body = rendered.document.body.textContent ?? "";
    assert.match(body, /could not save and apply/);
    assert.match(body, /settings-request-1/);
    assert.doesNotMatch(body, /new-secret/);
  } finally {
    await rendered.cleanup();
  }
});

async function selectValue(select: HTMLSelectElement, value: string): Promise<void> {
  select.value = value;
  await dispatch(select, new window.Event("change", { bubbles: true }));
}

function inputByName(
  fields: NodeListOf<HTMLInputElement>,
  name: string,
): HTMLInputElement {
  const field = Array.from(fields).find((input) => input.name === name);
  assert.ok(field, `Missing field ${name}`);
  return field;
}

function buttonWithText(document: Document, text: string): HTMLButtonElement {
  const button = Array.from(document.querySelectorAll("button")).find(
    (candidate) => candidate.textContent?.includes(text),
  );
  assert.ok(button, `Missing button ${text}`);
  return button;
}

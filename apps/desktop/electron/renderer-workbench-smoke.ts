import type { WebContents } from "electron";

type RendererWebContents = Pick<WebContents, "executeJavaScript">;

export type RendererWorkbenchSmokeMode =
  | "navigation"
  | "blocked"
  | "query"
  | "settings";

export type RendererWorkbenchSettingsInput = {
  baseUrl: string;
  provider?: "ollama" | "openai_compatible";
  credential?: string;
};

type RendererWorkbenchSmokeResult = {
  altEnterOk: boolean;
  blockedTaskEmpty: boolean;
  configurationActionVisible: boolean;
  draftEditable: boolean;
  draftPromptPreserved: boolean;
  imeAndRepeatBlocked: boolean;
  modelSettingsApplied: boolean;
  modelSettingsRedacted: boolean;
  modelSettingsReady: boolean;
  navigationOk: boolean;
  queryCitationCount: number;
  queryCitationMarkersOk: boolean;
  queryConversationId: string | null;
  queryMarkdownOk: boolean;
  queryMessageCount: number;
  queryStatus: string | null;
  queryUnsafeContentBlocked: boolean;
  sessionDelta: number;
};

function rendererWorkbenchSmokeScript(
  mode: RendererWorkbenchSmokeMode,
  settingsInput?: RendererWorkbenchSettingsInput,
): string {
  const expectedPrompt = "MARA Desktop renderer keyboard smoke question";
  return `
    (async () => {
      const mode = ${JSON.stringify(mode)};
      const settingsInput = ${JSON.stringify(settingsInput ?? null)};
      const expectedPrompt = ${JSON.stringify(expectedPrompt)};
      const bridge = window.desktop;
      if (!bridge) return {};
      const wait = (milliseconds) => new Promise((resolve) =>
        setTimeout(resolve, milliseconds),
      );
      const button = (label) => Array.from(document.querySelectorAll("button"))
        .find((candidate) => candidate.textContent?.trim() === label);
      const inputValue = (input, value) => {
        const setter = Object.getOwnPropertyDescriptor(
          HTMLTextAreaElement.prototype,
          "value",
        )?.set;
        setter?.call(input, value);
        input.dispatchEvent(new Event("input", { bubbles: true }));
      };
      const formInputValue = (input, value) => {
        const setter = Object.getOwnPropertyDescriptor(
          HTMLInputElement.prototype,
          "value",
        )?.set;
        setter?.call(input, value);
        input.dispatchEvent(new Event("input", { bubbles: true }));
      };
      const selectValue = (select, value) => {
        const setter = Object.getOwnPropertyDescriptor(
          HTMLSelectElement.prototype,
          "value",
        )?.set;
        setter?.call(select, value);
        select.dispatchEvent(new Event("change", { bubbles: true }));
      };
      for (let attempt = 0; attempt < 200; attempt += 1) {
        if (document.querySelector("#task-input") && button("Resources")) break;
        await wait(25);
      }
      const sessionsBefore = mode === "settings"
        ? { ok: true, data: [] }
        : await bridge.listSessions();
      const latestBefore = mode === "settings"
        ? { ok: true, data: null }
        : await bridge.getLatestAnswerTask();
      const pages = [
        ["Resources", "资源状态", "Resources"],
        ["Help", "帮助与快捷键", "Help"],
        ["Settings", "模型设置", "Settings"],
      ];
      let navigationOk = true;
      for (const [label, heading, title] of pages) {
        const navigation = button(label);
        navigation?.click();
        await wait(25);
        const pageHeading = document.querySelector("[data-page-title]");
        navigationOk &&=
          navigation?.getAttribute("aria-current") === "page" &&
          pageHeading?.textContent?.includes(heading) === true &&
          document.title.includes(title) &&
          document.activeElement === pageHeading;
      }
      const modelSettings = await bridge.getModelSettings();
      const serializedSettings = JSON.stringify(
        modelSettings?.ok ? modelSettings.data : {},
      );
      const modelSettingsRedacted =
        modelSettings?.ok === true &&
        !serializedSettings.includes('"credential":') &&
        !serializedSettings.includes("mara-desktop-smoke");
      button("工作台")?.click();
      await wait(25);
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        ctrlKey: true,
        key: ",",
      }));
      await wait(25);
      navigationOk &&=
        button("Settings")?.getAttribute("aria-current") === "page";
      let modelSettingsApplied = mode !== "settings";
      let modelSettingsReady = mode !== "settings";
      if (mode === "settings" && settingsInput?.baseUrl) {
        const selectedProvider = settingsInput.provider ?? "ollama";
        const selectedCredential = settingsInput.credential ?? null;
        const configureRoute = async (kind, model) => {
          const provider = document.querySelector(
            'select[name="' + kind + '.provider"]',
          );
          if (!(provider instanceof HTMLSelectElement)) return false;
          selectValue(provider, selectedProvider);
          await wait(25);
          const baseUrl = document.querySelector(
            'input[name="' + kind + '.base_url"]',
          );
          const modelInput = document.querySelector(
            'input[name="' + kind + '.model"]',
          );
          if (
            !(baseUrl instanceof HTMLInputElement) ||
            !(modelInput instanceof HTMLInputElement)
          ) return false;
          formInputValue(baseUrl, settingsInput.baseUrl);
          formInputValue(modelInput, model);
          if (selectedProvider !== "ollama") {
            const credential = document.querySelector(
              'input[name="' + kind + '.credential"]',
            );
            if (!(credential instanceof HTMLInputElement)) return false;
            formInputValue(credential, selectedCredential ?? "");
          }
          await wait(0);
          return true;
        };
        const chatConfigured = await configureRoute("chat", "gpt-5.6-luna");
        const embeddingConfigured = await configureRoute(
          "embedding",
          "smoke-embedding",
        );
        button("保存并应用")?.click();
        let savedSettings = null;
        let readyDoctor = null;
        let readyRuntime = null;
        for (let attempt = 0; attempt < 800; attempt += 1) {
          savedSettings = await bridge.getModelSettings();
          readyDoctor = await bridge.getDoctor();
          readyRuntime = await bridge.getRuntimeStatus();
          if (
            savedSettings?.ok &&
            savedSettings.data.source === "desktop" &&
            readyDoctor?.ok &&
            readyDoctor.data.query_ready &&
            readyDoctor.data.indexing_ready &&
            readyRuntime?.state === "healthy"
          ) break;
          await wait(25);
        }
        const savedSerialized = JSON.stringify(
          savedSettings?.ok ? savedSettings.data : {},
        );
        modelSettingsApplied =
          chatConfigured &&
          embeddingConfigured &&
          savedSettings?.ok === true &&
          savedSettings.data.chat.provider === selectedProvider &&
          savedSettings.data.chat.model === "gpt-5.6-luna" &&
          savedSettings.data.embedding.provider === selectedProvider &&
          savedSettings.data.embedding.model === "smoke-embedding" &&
          savedSettings.data.chat.credential_present === Boolean(selectedCredential) &&
          savedSettings.data.embedding.credential_present === Boolean(selectedCredential) &&
          !savedSerialized.includes('"credential":') &&
          (!selectedCredential || !savedSerialized.includes(selectedCredential));
        const expectedProvider = selectedProvider === "openai_compatible"
          ? "openai"
          : selectedProvider;
        modelSettingsReady =
          readyRuntime?.state === "healthy" &&
          readyDoctor?.ok === true &&
          readyDoctor.data.query_ready === true &&
          readyDoctor.data.indexing_ready === true &&
          readyDoctor.data.query_provider === expectedProvider &&
          readyDoctor.data.embedding_provider === expectedProvider;
      }
      button("工作台")?.click();
      await wait(25);
      let input = document.querySelector("#task-input");
      const draftEditable =
        input instanceof HTMLTextAreaElement &&
        !input.disabled &&
        document.querySelector("[data-page-title]")?.textContent?.includes("新任务") === true;
      if (!(input instanceof HTMLTextAreaElement)) return {};
      inputValue(input, "alpha beta");
      await wait(0);
      input.setSelectionRange(5, 6);
      input.dispatchEvent(new KeyboardEvent("keydown", {
        altKey: true,
        bubbles: true,
        cancelable: true,
        key: "Enter",
      }));
      await wait(0);
      const altEnterOk =
        input.value === "alpha\\nbeta" &&
        input.selectionStart === 6 &&
        input.selectionEnd === 6;
      let blockedTaskEmpty = true;
      let configurationActionVisible = true;
      let draftPromptPreserved = true;
      let imeAndRepeatBlocked = true;
      let queryCitationCount = 0;
      let queryCitationMarkersOk = true;
      let queryConversationId = null;
      let queryMarkdownOk = true;
      let queryMessageCount = 0;
      let queryStatus = null;
      let queryUnsafeContentBlocked = true;
      let sessionDelta = 0;
      if (mode === "blocked") {
        inputValue(input, expectedPrompt);
        await wait(0);
        input.dispatchEvent(new KeyboardEvent("keydown", {
          bubbles: true,
          cancelable: true,
          key: "Enter",
        }));
        await wait(50);
        const sessionsAfter = await bridge.listSessions();
        const latestAfter = await bridge.getLatestAnswerTask();
        blockedTaskEmpty =
          sessionsBefore?.ok === true &&
          sessionsAfter?.ok === true &&
          sessionsAfter.data.length === sessionsBefore.data.length &&
          latestAfter?.ok === true &&
          (latestAfter.data === null ||
            latestAfter.data.task_id === latestBefore?.data?.task_id);
        const configure = Array.from(document.querySelectorAll("button"))
          .find((candidate) => candidate.textContent?.includes("配置模型"));
        configurationActionVisible =
          Boolean(configure) && document.body.innerText.includes("llm_not_configured");
        configure?.click();
        await wait(25);
        button("工作台")?.click();
        await wait(25);
        input = document.querySelector("#task-input");
        draftPromptPreserved =
          input instanceof HTMLTextAreaElement && input.value === expectedPrompt;
      }
      if (mode === "query") {
        button("Sources")?.click();
        let source = null;
        for (let attempt = 0; attempt < 200; attempt += 1) {
          source = document.querySelector(".sources-content input[type=checkbox]");
          if (source) break;
          await wait(25);
        }
        if (source instanceof HTMLInputElement && !source.checked) source.click();
        await wait(25);
        input = document.querySelector("#task-input");
        if (!(input instanceof HTMLTextAreaElement)) return {};
        inputValue(input, "IME composition probe");
        await wait(0);
        const composingEnter = new KeyboardEvent("keydown", {
          bubbles: true,
          cancelable: true,
          key: "Enter",
        });
        Object.defineProperty(composingEnter, "isComposing", { value: true });
        input.dispatchEvent(composingEnter);
        input.dispatchEvent(new KeyboardEvent("keydown", {
          bubbles: true,
          cancelable: true,
          key: "Enter",
          repeat: true,
        }));
        await wait(50);
        const latestAfterGuards = await bridge.getLatestAnswerTask();
        imeAndRepeatBlocked =
          latestAfterGuards?.ok === true &&
          (latestAfterGuards.data === null ||
            latestAfterGuards.data.task_id === latestBefore?.data?.task_id);
        inputValue(input, expectedPrompt);
        for (let attempt = 0; attempt < 200; attempt += 1) {
          if (!document.querySelector(".send-button")?.disabled) break;
          await wait(25);
        }
        input.dispatchEvent(new KeyboardEvent("keydown", {
          bubbles: true,
          cancelable: true,
          key: "Enter",
        }));
        input.dispatchEvent(new KeyboardEvent("keydown", {
          bubbles: true,
          cancelable: true,
          key: "Enter",
        }));
        document.querySelector(".send-button")?.click();
        let queryTask = null;
        for (let attempt = 0; attempt < 1_200; attempt += 1) {
          const latest = await bridge.getLatestAnswerTask();
          if (latest?.ok && latest.data?.prompt === expectedPrompt) {
            queryTask = latest.data;
            if (["success", "failed", "cancelled"].includes(queryTask.status)) break;
          }
          await wait(50);
        }
        const sessionsAfter = await bridge.listSessions();
        sessionDelta =
          sessionsBefore?.ok && sessionsAfter?.ok
            ? sessionsAfter.data.length - sessionsBefore.data.length
            : -1;
        queryStatus = queryTask?.status ?? null;
        queryCitationCount = queryTask?.citations?.length ?? 0;
        queryConversationId = queryTask?.conversation_id ?? null;
        if (queryConversationId) {
          const detail = await bridge.getSession(queryConversationId);
          queryMessageCount = detail?.ok ? detail.data.messages.length : 0;
        }
        let answer = null;
        for (let attempt = 0; attempt < 200; attempt += 1) {
          answer = document.querySelector(".current-answer .answer-content");
          if (answer?.querySelector("h1") && answer.querySelector(".katex")) break;
          await wait(25);
        }
        const links = Array.from(answer?.querySelectorAll("a") ?? []);
        queryMarkdownOk =
          answer?.querySelector("h1")?.textContent?.trim() === "Grounded result" &&
          answer.querySelectorAll("ul > li").length === 2 &&
          answer.querySelector("blockquote") !== null &&
          answer.querySelector("table tbody td") !== null &&
          answer.querySelector("pre > code.language-text") !== null &&
          answer.querySelector(".katex") !== null;
        queryCitationMarkersOk =
          answer?.textContent?.includes("【1】【2】") === true;
        queryUnsafeContentBlocked =
          answer?.querySelector("script, img, [onerror]") === null &&
          links.every((link) => {
            const href = link.getAttribute("href") ?? "";
            return href.startsWith("https://") || href.startsWith("http://") || href.startsWith("#");
          }) &&
          !links.some((link) => link.textContent?.trim() === "blocked");
      }
      return {
        altEnterOk,
        blockedTaskEmpty,
        configurationActionVisible,
        draftEditable,
        draftPromptPreserved,
        imeAndRepeatBlocked,
        modelSettingsApplied,
        modelSettingsRedacted,
        modelSettingsReady,
        navigationOk,
        queryCitationCount,
        queryCitationMarkersOk,
        queryConversationId,
        queryMarkdownOk,
        queryMessageCount,
        queryStatus,
        queryUnsafeContentBlocked,
        sessionDelta,
      };
    })()
  `;
}

export async function runRendererWorkbenchSmoke(
  webContents: RendererWebContents,
  mode: RendererWorkbenchSmokeMode,
  reportSuccess: (message: string) => void = console.log,
  settingsInput?: RendererWorkbenchSettingsInput,
): Promise<string | null> {
  const result = (await webContents.executeJavaScript(
    rendererWorkbenchSmokeScript(mode, settingsInput),
  )) as RendererWorkbenchSmokeResult;
  const failures: string[] = [];
  if (!result.navigationOk) failures.push("real page navigation failed");
  if (!result.draftEditable) failures.push("cold-start draft was not editable");
  if (!result.altEnterOk) failures.push("Alt+Enter did not insert one newline");
  if (!result.modelSettingsRedacted) failures.push("model settings were not redacted");
  if (mode === "settings") {
    if (!result.modelSettingsApplied) failures.push("model settings were not saved by the page");
    if (!result.modelSettingsReady) failures.push("Doctor was not ready after Sidecar restart");
  }
  if (mode === "blocked") {
    if (!result.blockedTaskEmpty) failures.push("blocked query created persisted work");
    if (!result.configurationActionVisible) failures.push("model configuration action was missing");
    if (!result.draftPromptPreserved) failures.push("blocked query lost its draft");
  }
  if (mode === "query") {
    if (!result.imeAndRepeatBlocked) failures.push("keyboard guards created work");
    if (result.sessionDelta !== 1) failures.push(`session delta was ${result.sessionDelta}`);
    if (result.queryStatus !== "success") {
      failures.push(`renderer query status was ${result.queryStatus ?? "missing"}`);
    }
    if (result.queryCitationCount < 1) failures.push("renderer query had no citations");
    if (!result.queryCitationMarkersOk) failures.push("citation markers changed in Markdown");
    if (!result.queryMarkdownOk) failures.push("assistant Markdown was not semantic DOM");
    if (!result.queryUnsafeContentBlocked) failures.push("unsafe Markdown content reached the DOM");
    if (result.queryMessageCount < 2) failures.push("renderer query was not persisted");
  }
  if (failures.length > 0) {
    throw new Error(`Packaged renderer interaction smoke failed: ${failures.join("; ")}`);
  }
  reportSuccess(
    `renderer_ui=real-navigation,draft,settings,keyboard mode=${mode} status_success`,
  );
  if (mode === "query") {
    reportSuccess(
      "renderer_markdown=heading,list,table,code,blockquote,katex,citations,safe-links status_success",
    );
  }
  if (mode === "settings") {
    reportSuccess(
      "renderer_model_settings=ui-save,restart,doctor-ready,redacted status_success",
    );
  }
  return result.queryConversationId;
}

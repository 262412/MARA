import { randomUUID } from "node:crypto";
import {
  mkdir,
  readFile,
  rename,
  unlink,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

import type {
  CredentialStorage,
  ModelProvider,
  ModelRouteInput,
  ModelRouteStatus,
  ModelSettingsInput,
  ModelSettingsStatus,
} from "../shared/model-contracts";

export type CredentialProtector = {
  decryptString(value: Buffer): string;
  encryptString(value: string): Buffer;
  isEncryptionAvailable(): boolean;
};

type ElectronSafeStorage = CredentialProtector & {
  getSelectedStorageBackend(): string;
};

export function createDesktopCredentialProtector(
  storage: ElectronSafeStorage,
  platform: NodeJS.Platform,
): CredentialProtector {
  return {
    decryptString: (value) => storage.decryptString(value),
    encryptString: (value) => storage.encryptString(value),
    isEncryptionAvailable: () =>
      storage.isEncryptionAvailable() &&
      !(platform === "linux" && storage.getSelectedStorageBackend() === "basic_text"),
  };
}

type PersistedRoute = Omit<ModelRouteInput, "credential">;
type PersistedModelSettings = {
  version: 1;
  credentials_revision: string;
  chat: PersistedRoute;
  embedding: PersistedRoute;
};
type PersistedCredentials = {
  revision: string;
  chat?: string;
  embedding?: string;
};

const PLACEHOLDER_CREDENTIALS = new Set([
  "",
  "<your_openai_key>",
  "your-key",
  "your_api_key",
  "your_key",
]);
const PROVIDERS = new Set<ModelProvider>([
  "none",
  "openai_compatible",
  "azure_openai",
  "ollama",
]);
const ROUTE_KEYS = [
  "api_version",
  "base_url",
  "credential",
  "model",
  "provider",
];

export class DesktopModelSettingsStore {
  private metadata?: PersistedModelSettings;
  private secrets: Pick<PersistedCredentials, "chat" | "embedding"> = {};

  constructor(
    private readonly dataRoot: string,
    private readonly protector: CredentialProtector,
  ) {}

  async load(): Promise<void> {
    const metadata = await readJsonIfPresent(modelMetadataPath(this.dataRoot));
    if (metadata === undefined) {
      const legacy = await readLegacyModelSettings(this.dataRoot);
      if (legacy) {
        const revision = randomUUID();
        const migrated: PersistedModelSettings = {
          version: 1,
          credentials_revision: revision,
          chat: persistedRoute(legacy.settings.chat),
          embedding: persistedRoute(legacy.settings.embedding),
        };
        const secrets = {
          chat: legacy.settings.chat.credential ?? undefined,
          embedding: legacy.settings.embedding.credential ?? undefined,
        };
        await persistSettings(this.dataRoot, migrated, secrets, this.protector);
        this.metadata = migrated;
        this.secrets = secrets;
      } else {
        this.metadata = undefined;
        this.secrets = {};
      }
      await scrubLegacyModelEnvironment(this.dataRoot);
      return;
    }
    this.metadata = validatePersistedSettings(metadata);
    this.secrets = await this.loadCredentials(this.metadata.credentials_revision);
    await scrubLegacyModelEnvironment(this.dataRoot);
  }

  status(): ModelSettingsStatus {
    const secureStorageAvailable = this.protector.isEncryptionAvailable();
    if (!this.metadata) {
      return {
        chat: emptyRouteStatus(),
        embedding: emptyRouteStatus(),
        secure_storage_available: secureStorageAvailable,
        source: "compatibility",
      };
    }
    return {
      chat: routeStatus(
        this.metadata.chat,
        this.secrets.chat,
        secureStorageAvailable,
      ),
      embedding: routeStatus(
        this.metadata.embedding,
        this.secrets.embedding,
        secureStorageAvailable,
      ),
      secure_storage_available: secureStorageAvailable,
      source: "desktop",
    };
  }

  async save(value: unknown): Promise<ModelSettingsStatus> {
    const input = validateModelSettingsInput(value);
    const metadata: PersistedModelSettings = {
      version: 1,
      credentials_revision: randomUUID(),
      chat: persistedRoute(input.chat),
      embedding: persistedRoute(input.embedding),
    };
    const secrets = {
      chat: resolveSecret(
        input.chat,
        this.metadata?.chat,
        this.secrets.chat,
      ),
      embedding: resolveSecret(
        input.embedding,
        this.metadata?.embedding,
        this.secrets.embedding,
      ),
    };
    await persistSettings(
      this.dataRoot,
      metadata,
      secrets,
      this.protector,
    );
    this.metadata = metadata;
    this.secrets = secrets;
    await scrubLegacyModelEnvironment(this.dataRoot);
    return this.status();
  }

  settingsRevision(): string {
    return this.metadata?.credentials_revision ?? "";
  }

  environment(): Record<string, string> {
    if (!this.metadata) {
      return {};
    }
    return {
      MARA_DESKTOP_MODEL_SETTINGS: "1",
      MARA_DESKTOP_SETTINGS_REVISION: this.metadata.credentials_revision,
      ...routeEnvironment("CHAT", this.metadata.chat, this.secrets.chat),
      ...routeEnvironment(
        "EMBEDDING",
        this.metadata.embedding,
        this.secrets.embedding,
      ),
    };
  }

  private async loadCredentials(
    expectedRevision: string,
  ): Promise<Pick<PersistedCredentials, "chat" | "embedding">> {
    if (!this.protector.isEncryptionAvailable()) {
      return {};
    }
    const encrypted = await readBufferIfPresent(modelCredentialPath(this.dataRoot));
    if (!encrypted) {
      return {};
    }
    const value: unknown = JSON.parse(this.protector.decryptString(encrypted));
    if (!value || typeof value !== "object") {
      throw new Error("Stored model credentials are invalid.");
    }
    const credentials = value as Record<string, unknown>;
    if (credentials.revision !== expectedRevision) {
      return {};
    }
    return {
      chat: optionalStoredSecret(credentials.chat),
      embedding: optionalStoredSecret(credentials.embedding),
    };
  }
}

export function modelMetadataPath(dataRoot: string): string {
  return path.join(path.resolve(dataRoot), "state", "model-settings.json");
}

export function modelCredentialPath(dataRoot: string): string {
  return path.join(path.resolve(dataRoot), "state", "model-credentials.bin");
}

export function validateModelSettingsInput(value: unknown): ModelSettingsInput {
  if (!isRecord(value) || Object.keys(value).sort().join(",") !== "chat,embedding") {
    throw new Error("Desktop model settings require chat and embedding routes.");
  }
  return {
    chat: validateRoute(value.chat, "chat"),
    embedding: validateRoute(value.embedding, "embedding"),
  };
}

function validateRoute(value: unknown, kind: string): ModelRouteInput {
  if (
    !isRecord(value) ||
    Object.keys(value).sort().join(",") !== ROUTE_KEYS.join(",") ||
    typeof value.provider !== "string" ||
    !PROVIDERS.has(value.provider as ModelProvider) ||
    typeof value.base_url !== "string" ||
    typeof value.model !== "string" ||
    typeof value.api_version !== "string" ||
    !(typeof value.credential === "string" || value.credential === null)
  ) {
    throw new Error(`Desktop model settings contain an invalid ${kind} route.`);
  }
  const route = value as ModelRouteInput;
  validateRouteValues(route, kind);
  return {
    provider: route.provider,
    base_url: route.base_url,
    model: route.model,
    api_version: route.api_version,
    credential: route.credential,
  };
}

function validateRouteValues(route: ModelRouteInput, kind: string): void {
  if (route.provider === "none") {
    if (route.base_url || route.model || route.api_version || route.credential) {
      throw new Error(`Desktop model settings contain an invalid ${kind} route.`);
    }
    return;
  }
  validateModelName(route.model, kind);
  validateEndpoint(route.base_url, route.provider, kind);
  if (route.provider === "azure_openai") {
    if (!/^[A-Za-z0-9._-]{1,64}$/.test(route.api_version)) {
      throw new Error(`Desktop model settings contain an invalid ${kind} API version.`);
    }
  } else if (route.api_version) {
    throw new Error(`Desktop model settings contain an invalid ${kind} API version.`);
  }
  if (route.provider === "ollama") {
    if (route.credential !== null) {
      throw new Error(`Desktop model settings contain an invalid ${kind} credential.`);
    }
    return;
  }
  if (route.credential !== null) {
    const credential = route.credential.trim();
    if (
      credential.length > 8_192 ||
      credential.includes("\0") ||
      PLACEHOLDER_CREDENTIALS.has(credential.toLocaleLowerCase())
    ) {
      throw new Error(`Desktop model settings contain an invalid ${kind} credential.`);
    }
  }
}

function validateModelName(model: string, kind: string): void {
  if (
    model.trim().length === 0 ||
    model.length > 256 ||
    /[\0\r\n]/.test(model)
  ) {
    throw new Error(`Desktop model settings contain an invalid ${kind} model.`);
  }
}

function validateEndpoint(
  endpoint: string,
  provider: ModelProvider,
  kind: string,
): void {
  if (endpoint.length === 0 || endpoint.length > 2_048) {
    throw new Error(`Desktop model settings contain an invalid ${kind} endpoint.`);
  }
  let url: URL;
  try {
    url = new URL(endpoint);
  } catch {
    throw new Error(`Desktop model settings contain an invalid ${kind} endpoint.`);
  }
  const loopback = ["127.0.0.1", "::1", "localhost"].includes(url.hostname);
  const allowedProtocol = url.protocol === "https:" || (url.protocol === "http:" && loopback);
  if (
    !allowedProtocol ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    (provider === "ollama" && !loopback) ||
    (provider === "azure_openai" && url.protocol !== "https:")
  ) {
    throw new Error(`Desktop model settings contain an invalid ${kind} endpoint.`);
  }
}

async function persistSettings(
  dataRoot: string,
  metadata: PersistedModelSettings,
  secrets: Pick<PersistedCredentials, "chat" | "embedding">,
  protector: CredentialProtector,
): Promise<void> {
  const metadataPath = modelMetadataPath(dataRoot);
  const credentialPath = modelCredentialPath(dataRoot);
  await mkdir(path.dirname(metadataPath), { recursive: true, mode: 0o700 });
  if (protector.isEncryptionAvailable() && (secrets.chat || secrets.embedding)) {
    const encrypted = protector.encryptString(
      JSON.stringify({ revision: metadata.credentials_revision, ...secrets }),
    );
    await atomicWrite(credentialPath, encrypted);
  } else {
    await unlinkIfPresent(credentialPath);
  }
  await atomicWrite(metadataPath, Buffer.from(`${JSON.stringify(metadata, null, 2)}\n`));
}

async function atomicWrite(destination: string, content: Buffer): Promise<void> {
  const temporary = `${destination}.${randomUUID()}.tmp`;
  try {
    await writeFile(temporary, content, { mode: 0o600, flag: "wx" });
    await rename(temporary, destination);
  } finally {
    await unlinkIfPresent(temporary);
  }
}

function routeEnvironment(
  kind: "CHAT" | "EMBEDDING",
  route: PersistedRoute,
  secret: string | undefined,
): Record<string, string> {
  const prefix = `MARA_DESKTOP_${kind}`;
  const environment: Record<string, string> = {
    [`${prefix}_PROVIDER`]: route.provider,
    [`${prefix}_BASE_URL`]: route.base_url,
    [`${prefix}_MODEL`]: route.model,
    [`${prefix}_API_VERSION`]: route.api_version,
  };
  if (secret) {
    environment[`${prefix}_API_KEY`] = secret;
  }
  return environment;
}

function routeStatus(
  route: PersistedRoute,
  secret: string | undefined,
  secureStorageAvailable: boolean,
): ModelRouteStatus {
  const storage: CredentialStorage = secret
    ? secureStorageAvailable
      ? "secure"
      : "session"
    : "none";
  return {
    ...route,
    credential_present: Boolean(secret),
    credential_storage: storage,
  };
}

function emptyRouteStatus(): ModelRouteStatus {
  return {
    provider: "none",
    base_url: "",
    model: "",
    api_version: "",
    credential_present: false,
    credential_storage: "none",
  };
}

function persistedRoute(route: ModelRouteInput): PersistedRoute {
  return {
    provider: route.provider,
    base_url: route.base_url,
    model: route.model,
    api_version: route.api_version,
  };
}

function resolveSecret(
  route: ModelRouteInput,
  previousRoute: PersistedRoute | undefined,
  previousSecret: string | undefined,
): string | undefined {
  if (route.provider === "none" || route.provider === "ollama") {
    return undefined;
  }
  if (route.credential !== null) {
    return route.credential.trim();
  }
  return previousRoute?.provider === route.provider ? previousSecret : undefined;
}

function validatePersistedSettings(value: unknown): PersistedModelSettings {
  if (!isRecord(value) || value.version !== 1 || typeof value.credentials_revision !== "string") {
    throw new Error("Stored model settings are invalid.");
  }
  return {
    version: 1,
    credentials_revision: value.credentials_revision,
    chat: validatePersistedRoute(value.chat),
    embedding: validatePersistedRoute(value.embedding),
  };
}

function validatePersistedRoute(value: unknown): PersistedRoute {
  if (!isRecord(value)) {
    throw new Error("Stored model settings are invalid.");
  }
  const route = validateRoute({ ...value, credential: null }, "stored");
  return persistedRoute(route);
}

async function readJsonIfPresent(filePath: string): Promise<unknown | undefined> {
  try {
    return JSON.parse(await readFile(filePath, "utf8"));
  } catch (error) {
    if (isMissing(error)) {
      return undefined;
    }
    throw error;
  }
}

async function readBufferIfPresent(filePath: string): Promise<Buffer | undefined> {
  try {
    return await readFile(filePath);
  } catch (error) {
    if (isMissing(error)) {
      return undefined;
    }
    throw error;
  }
}

async function unlinkIfPresent(filePath: string): Promise<void> {
  try {
    await unlink(filePath);
  } catch (error) {
    if (!isMissing(error)) {
      throw error;
    }
  }
}

function optionalStoredSecret(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isMissing(error: unknown): boolean {
  return (
    error instanceof Error &&
    "code" in error &&
    (error as NodeJS.ErrnoException).code === "ENOENT"
  );
}

type LegacyModelSettings = {
  settings: ModelSettingsInput;
};

const LEGACY_MODEL_KEYS = new Set([
  "OPENAI_API_BASE",
  "OPENAI_API_KEY",
  "OPENAI_CHAT_MODEL",
  "OPENAI_EMBEDDINGS_MODEL",
  "AZURE_OPENAI_ENDPOINT",
  "AZURE_OPENAI_API_KEY",
  "OPENAI_API_VERSION",
  "AZURE_OPENAI_CHAT_DEPLOYMENT",
  "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT",
  "KH_OLLAMA_URL",
  "LOCAL_MODEL",
  "LOCAL_MODEL_EMBEDDINGS",
  "MARA_DESKTOP_MODEL_SETTINGS",
  "MARA_DESKTOP_SETTINGS_REVISION",
  "MARA_DESKTOP_CHAT_PROVIDER",
  "MARA_DESKTOP_CHAT_BASE_URL",
  "MARA_DESKTOP_CHAT_MODEL",
  "MARA_DESKTOP_CHAT_API_VERSION",
  "MARA_DESKTOP_CHAT_API_KEY",
  "MARA_DESKTOP_EMBEDDING_PROVIDER",
  "MARA_DESKTOP_EMBEDDING_BASE_URL",
  "MARA_DESKTOP_EMBEDDING_MODEL",
  "MARA_DESKTOP_EMBEDDING_API_VERSION",
  "MARA_DESKTOP_EMBEDDING_API_KEY",
]);

function legacyEnvironmentPath(dataRoot: string): string {
  return path.join(path.resolve(dataRoot), "state", "config", ".env");
}

async function readLegacyModelSettings(
  dataRoot: string,
): Promise<LegacyModelSettings | undefined> {
  const content = await readTextIfPresent(legacyEnvironmentPath(dataRoot));
  if (content === undefined) {
    return undefined;
  }
  const values = parseLegacyEnvironment(content);
  const openAiKey = validLegacyCredential(values.OPENAI_API_KEY);
  const azureKey = validLegacyCredential(values.AZURE_OPENAI_API_KEY);
  const openAiBase = values.OPENAI_API_BASE?.trim() || "https://api.openai.com/v1";
  const azureEndpoint = values.AZURE_OPENAI_ENDPOINT?.trim() || "";
  const ollamaEndpoint = values.KH_OLLAMA_URL?.trim() || "http://127.0.0.1:11434/v1";

  const chat = legacyRoute(
    openAiKey && values.OPENAI_CHAT_MODEL
      ? {
          provider: "openai_compatible",
          base_url: openAiBase,
          model: values.OPENAI_CHAT_MODEL,
          api_version: "",
          credential: openAiKey,
        }
      : azureKey && azureEndpoint && values.AZURE_OPENAI_CHAT_DEPLOYMENT
        ? {
            provider: "azure_openai",
            base_url: azureEndpoint,
            model: values.AZURE_OPENAI_CHAT_DEPLOYMENT,
            api_version: values.OPENAI_API_VERSION || "2024-02-15-preview",
            credential: azureKey,
          }
        : values.LOCAL_MODEL
          ? {
              provider: "ollama",
              base_url: ollamaEndpoint,
              model: values.LOCAL_MODEL,
              api_version: "",
              credential: null,
            }
          : undefined,
  );
  const embedding = legacyRoute(
    openAiKey && values.OPENAI_EMBEDDINGS_MODEL
      ? {
          provider: "openai_compatible",
          base_url: openAiBase,
          model: values.OPENAI_EMBEDDINGS_MODEL,
          api_version: "",
          credential: openAiKey,
        }
      : azureKey && azureEndpoint && values.AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT
        ? {
            provider: "azure_openai",
            base_url: azureEndpoint,
            model: values.AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
            api_version: values.OPENAI_API_VERSION || "2024-02-15-preview",
            credential: azureKey,
          }
        : values.LOCAL_MODEL_EMBEDDINGS
          ? {
              provider: "ollama",
              base_url: ollamaEndpoint,
              model: values.LOCAL_MODEL_EMBEDDINGS,
              api_version: "",
              credential: null,
            }
          : undefined,
  );
  if (chat.provider === "none" && embedding.provider === "none") {
    return undefined;
  }
  return { settings: { chat, embedding } };
}

function legacyRoute(route: ModelRouteInput | undefined): ModelRouteInput {
  if (!route) {
    return {
      provider: "none",
      base_url: "",
      model: "",
      api_version: "",
      credential: null,
    };
  }
  return validateRoute(route, "legacy");
}

function validLegacyCredential(value: string | undefined): string | undefined {
  const credential = value?.trim() || "";
  return credential && !PLACEHOLDER_CREDENTIALS.has(credential.toLowerCase())
    ? credential
    : undefined;
}

function parseLegacyEnvironment(content: string): Record<string, string> {
  const values: Record<string, string> = {};
  for (const line of content.split(/\r?\n/)) {
    const match = line.match(/^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)\s*$/);
    if (!match || !LEGACY_MODEL_KEYS.has(match[1])) {
      continue;
    }
    const raw = match[2].trim();
    values[match[1]] =
      (raw.startsWith('"') && raw.endsWith('"')) ||
      (raw.startsWith("'") && raw.endsWith("'"))
        ? raw.slice(1, -1)
        : raw;
  }
  return values;
}

async function scrubLegacyModelEnvironment(dataRoot: string): Promise<void> {
  const filePath = legacyEnvironmentPath(dataRoot);
  const content = await readTextIfPresent(filePath);
  if (content === undefined) {
    return;
  }
  const retained = content
    .split(/\r?\n/)
    .filter((line) => {
      const match = line.match(/^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=/);
      return !match || !LEGACY_MODEL_KEYS.has(match[1]);
    })
    .join("\n")
    .replace(/^\s+|\s+$/g, "");
  await atomicWrite(
    filePath,
    Buffer.from(retained ? `${retained}\n` : "# Model settings migrated to MARA Desktop Settings.\n"),
  );
}

async function readTextIfPresent(filePath: string): Promise<string | undefined> {
  try {
    return await readFile(filePath, "utf8");
  } catch (error) {
    if (isMissing(error)) {
      return undefined;
    }
    throw error;
  }
}

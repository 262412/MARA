import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import type { ModelSettingsInput } from "../shared/model-contracts";
import {
  DesktopModelSettingsStore,
  createDesktopCredentialProtector,
  modelCredentialPath,
  modelMetadataPath,
  validateModelSettingsInput,
  type CredentialProtector,
} from "./model-settings";

const configured: ModelSettingsInput = {
  chat: {
    provider: "openai_compatible",
    base_url: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
    api_version: "",
    credential: "chat-secret",
  },
  embedding: {
    provider: "ollama",
    base_url: "http://127.0.0.1:11434/v1",
    model: "nomic-embed-text",
    api_version: "",
    credential: null,
  },
};

class TestProtector implements CredentialProtector {
  constructor(private readonly available: boolean) {}

  isEncryptionAvailable(): boolean {
    return this.available;
  }

  encryptString(value: string): Buffer {
    assert.equal(this.available, true);
    return Buffer.from(`encrypted:${Buffer.from(value).toString("base64")}`);
  }

  decryptString(value: Buffer): string {
    assert.equal(this.available, true);
    const encoded = value.toString().replace(/^encrypted:/, "");
    return Buffer.from(encoded, "base64").toString();
  }
}

test("treats Electron basic_text on Linux as session-only storage", () => {
  const storage = {
    decryptString: (value: Buffer) => value.toString(),
    encryptString: (value: string) => Buffer.from(value),
    getSelectedStorageBackend: () => "basic_text",
    isEncryptionAvailable: () => true,
  };

  assert.equal(
    createDesktopCredentialProtector(storage, "linux").isEncryptionAvailable(),
    false,
  );
  assert.equal(
    createDesktopCredentialProtector(storage, "win32").isEncryptionAvailable(),
    true,
  );
});

test("persists only encrypted credentials and returns redacted status", async () => {
  const dataRoot = await mkdtemp(path.join(os.tmpdir(), "mara-model-settings-"));
  const store = new DesktopModelSettingsStore(dataRoot, new TestProtector(true));

  await store.load();
  const status = await store.save(configured);
  const metadata = await readFile(modelMetadataPath(dataRoot), "utf8");
  const credentials = await readFile(modelCredentialPath(dataRoot));

  assert.equal(status.chat.credential_present, true);
  assert.equal(status.chat.credential_storage, "secure");
  assert.equal(status.embedding.credential_present, false);
  assert.equal(status.secure_storage_available, true);
  assert.doesNotMatch(JSON.stringify(status), /chat-secret/);
  assert.doesNotMatch(metadata, /chat-secret/);
  assert.doesNotMatch(credentials.toString(), /chat-secret/);
  assert.equal(store.environment().MARA_DESKTOP_CHAT_API_KEY, "chat-secret");
  assert.equal(store.environment().MARA_DESKTOP_CHAT_PROVIDER, "openai_compatible");
  assert.equal(store.environment().MARA_DESKTOP_EMBEDDING_PROVIDER, "ollama");

  const reloaded = new DesktopModelSettingsStore(
    dataRoot,
    new TestProtector(true),
  );
  await reloaded.load();
  assert.equal(reloaded.status().chat.credential_present, true);
  assert.equal(reloaded.environment().MARA_DESKTOP_CHAT_API_KEY, "chat-secret");
});

test("falls back explicitly to session-only credentials without plaintext persistence", async () => {
  const dataRoot = await mkdtemp(path.join(os.tmpdir(), "mara-model-session-"));
  const store = new DesktopModelSettingsStore(dataRoot, new TestProtector(false));

  await store.load();
  const status = await store.save(configured);

  assert.equal(status.secure_storage_available, false);
  assert.equal(status.chat.credential_storage, "session");
  await assert.rejects(readFile(modelCredentialPath(dataRoot)), /ENOENT/);
  assert.doesNotMatch(
    await readFile(modelMetadataPath(dataRoot), "utf8"),
    /chat-secret/,
  );

  const restarted = new DesktopModelSettingsStore(
    dataRoot,
    new TestProtector(false),
  );
  await restarted.load();
  assert.equal(restarted.status().chat.credential_present, false);
  assert.equal(restarted.environment().MARA_DESKTOP_CHAT_API_KEY, undefined);
});

test("validates exact providers, safe endpoint schemes, models, and credentials", () => {
  assert.deepEqual(validateModelSettingsInput(configured), configured);
  for (const invalid of [
    {
      ...configured,
      chat: { ...configured.chat, credential: "<YOUR_OPENAI_KEY>" },
    },
    {
      ...configured,
      chat: { ...configured.chat, base_url: "http://models.example.com/v1" },
    },
    {
      ...configured,
      chat: { ...configured.chat, provider: "arbitrary-provider" },
    },
    {
      ...configured,
      embedding: { ...configured.embedding, model: "" },
    },
  ]) {
    assert.throws(() => validateModelSettingsInput(invalid), /model settings/i);
  }
});

test("does not read, rewrite, or delete the legacy Desktop env file", async () => {
  const dataRoot = await mkdtemp(path.join(os.tmpdir(), "mara-model-legacy-"));
  const legacyPath = path.join(dataRoot, "state", "config", ".env");
  await mkdir(path.dirname(legacyPath), { recursive: true });
  const legacy = "OPENAI_API_KEY=legacy-secret\n";
  await writeFile(legacyPath, legacy, { encoding: "utf8", mode: 0o600 });
  const store = new DesktopModelSettingsStore(dataRoot, new TestProtector(true));

  await store.load();
  await store.save(configured);

  assert.equal(await readFile(legacyPath, "utf8"), legacy);
});

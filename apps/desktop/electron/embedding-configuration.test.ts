import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  embeddingConfigurationPath,
  prepareEmbeddingConfiguration,
} from "./embedding-configuration";

test("legacy embedding configuration points to secure Desktop Settings", async () => {
  const dataRoot = await mkdtemp(
    path.join(os.tmpdir(), "mara-desktop-config-"),
  );

  const configPath = await prepareEmbeddingConfiguration(dataRoot);
  const content = await readFile(configPath, "utf8");

  assert.equal(configPath, embeddingConfigurationPath(dataRoot));
  assert.ok(configPath.startsWith(`${path.resolve(dataRoot)}${path.sep}`));
  assert.match(content, /MARA Desktop Settings/);
  assert.doesNotMatch(content, /API_KEY|TOKEN|PASSWORD/);
});

test("never overwrites an existing Desktop embedding configuration", async () => {
  const dataRoot = await mkdtemp(
    path.join(os.tmpdir(), "mara-desktop-config-existing-"),
  );
  const configPath = embeddingConfigurationPath(dataRoot);
  await mkdir(path.dirname(configPath), { recursive: true });
  const existing = "OPENAI_API_KEY=existing-secret\n";
  await writeFile(configPath, existing, { encoding: "utf8", mode: 0o600 });

  await prepareEmbeddingConfiguration(dataRoot);

  assert.equal(await readFile(configPath, "utf8"), existing);
});

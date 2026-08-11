import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  excludedSidecarModules,
  requiredSidecarDataDirectories,
  requiredSidecarDataPackages,
  requiredSidecarModules,
  requiredTiktokenEncodings,
  supportedDesktopEmbeddingProviders,
  tiktokenCacheDestination,
} from "./sidecar-bundle-config.mjs";

const desktopRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const buildScript = readFileSync(
  path.join(desktopRoot, "scripts", "build-sidecar.mjs"),
  "utf8",
);

test("excludes optional python-magic from the native Sidecar bundle", () => {
  assert.ok(excludedSidecarModules.includes("magic"));
});

test("excludes optional indexing accelerators and provider SDKs", () => {
  for (const moduleName of [
    "google.generativeai",
    "googleapiclient",
    "llvmlite",
    "numba",
  ]) {
    assert.ok(excludedSidecarModules.includes(moduleName), moduleName);
  }
});

test("declares only providers whose dependencies are native bundle requirements", () => {
  assert.deepEqual(supportedDesktopEmbeddingProviders, [
    {
      module: "openai",
      types: [
        "kotaemon.embeddings.OpenAIEmbeddings",
        "kotaemon.embeddings.AzureOpenAIEmbeddings",
      ],
    },
  ]);
  for (const provider of supportedDesktopEmbeddingProviders) {
    assert.ok(requiredSidecarModules.includes(provider.module), provider.module);
    assert.ok(!excludedSidecarModules.includes(provider.module), provider.module);
  }
});

test("isolates PyInstaller analysis from the source checkout", () => {
  assert.match(buildScript, /mkdtempSync\(\s*path\.join\(tmpdir\(\)/);
  assert.match(
    buildScript,
    /MARA_DESKTOP_BUILD_RUNTIME_ROOT: buildRuntimeRoot/,
  );
  assert.match(
    buildScript,
    /THEFLOW_SETTINGS_MODULE: "sidecar\.build_flowsettings"/,
  );
  assert.doesNotMatch(
    buildScript,
    /THEFLOW_SETTINGS_MODULE: "ktem\.default_flowsettings"/,
  );
  assert.match(buildScript, /THEFLOW_TEMP_PATH: path\.join\(buildRuntimeRoot, "tmp"\)/);
  assert.equal(buildScript.match(/cwd: buildRuntimeRoot/g)?.length, 1);
  assert.match(
    buildScript,
    /cwd: desktopRoot,\s*env: buildRuntimeEnvironment/,
  );
  assert.match(buildScript, /finally \{[\s\S]*rmSync\(buildRuntimeRoot/);
});

test("includes the storage, embedding, and modern Office modules used by Gate 3", () => {
  for (const moduleName of [
    "chromadb",
    "chromadb.api.segment",
    "chromadb.db.impl.sqlite",
    "chromadb.execution.executor.local",
    "chromadb.segment.impl.manager.local",
    "chromadb.segment.impl.metadata.sqlite",
    "chromadb.segment.impl.vector.local_hnsw",
    "chromadb.segment.impl.vector.local_persistent_hnsw",
    "chromadb.telemetry.product.posthog",
    "chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2",
    "docx",
    "ktem.docqa",
    "ktem.index.file.pipelines",
    "ktem.reasoning.prompt_optimization.decompose_question",
    "ktem.reasoning.prompt_optimization.rewrite_question",
    "ktem.reasoning.simple",
    "kotaemon.embeddings.openai",
    "kotaemon.llms",
    "kotaemon.llms.chats.openai",
    "kotaemon.storages.docstores.lancedb",
    "kotaemon.storages.vectorstores.chroma",
    "lancedb",
    "llama_index.vector_stores.chroma",
    "openai",
    "openpyxl",
    "onnxruntime",
    "pandas",
    "pptx",
    "theflow.backends",
    "theflow.cache",
    "theflow.callbacks",
    "theflow.context",
    "theflow.middleware",
    "theflow.storage",
    "tiktoken_ext.openai_public",
    "tokenizers",
    "tqdm",
    "unstructured.partition.auto",
    "unstructured.partition.pptx",
  ]) {
    assert.ok(requiredSidecarModules.includes(moduleName), moduleName);
  }
  for (const moduleName of [
    "chromadb",
    "ktem.docqa",
    "llama_index",
    "openai",
    "onnxruntime",
    "pyarrow",
    "tokenizers",
  ]) {
    assert.ok(!excludedSidecarModules.includes(moduleName), moduleName);
  }
  assert.deepEqual(requiredSidecarDataPackages, ["chromadb", "llama_index.core"]);
  assert.deepEqual(requiredTiktokenEncodings, ["cl100k_base"]);
  assert.equal(tiktokenCacheDestination, "tiktoken_cache");
  assert.deepEqual(requiredSidecarDataDirectories, [
    {
      source: "sidecar/nltk_data/tokenizers/punkt",
      destination: "llama_index/core/_static/nltk_cache/tokenizers/punkt",
    },
  ]);
  for (const { source } of requiredSidecarDataDirectories) {
    assert.ok(existsSync(path.join(desktopRoot, source)), source);
  }
});

import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  excludedSidecarModules,
  requiredSidecarDataDirectories,
  requiredSidecarDataPackages,
  requiredSidecarModules,
  requiredTiktokenEncodings,
  tiktokenCacheDestination,
} from "./sidecar-bundle-config.mjs";

const desktopRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
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

test("includes the storage, embedding, and modern Office modules used by Gate 3", () => {
  for (const moduleName of [
    "chromadb",
    "chromadb.api.segment",
    "chromadb.db.impl.sqlite",
    "chromadb.execution.executor.local",
    "chromadb.ingest.impl.simple_policy",
    "chromadb.segment.impl.manager.local",
    "chromadb.segment.impl.metadata.sqlite",
    "chromadb.segment.impl.vector.local_hnsw",
    "chromadb.segment.impl.vector.local_persistent_hnsw",
    "chromadb.telemetry.product.posthog",
    "chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2",
    "docx",
    "ktem.docqa",
    "ktem.index.file.pipelines",
    "kotaemon.embeddings.openai",
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

import { spawnSync } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const desktopRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(desktopRoot, "..", "..");
const buildRoot = path.join(desktopRoot, "build", "sidecar");
const outputRoot = path.join(desktopRoot, "resources", "sidecar");
const source = path.join(desktopRoot, "sidecar", "server.py");
const workspacePython = path.resolve(
  repositoryRoot,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
const workspacePackageRoots = [
  path.join(repositoryRoot, "libs", "slide_cli"),
  path.join(repositoryRoot, "libs", "ktem"),
  path.join(repositoryRoot, "libs", "kotaemon"),
];
const excludedDevelopmentModules = [
  "IPython",
  "_pytest",
  "_tkinter",
  "black",
  "chromadb",
  "cohere",
  "cryptography",
  "docutils",
  "fsspec",
  "gradio",
  "gradio_client",
  "haystack",
  "huggingface_hub",
  "jedi",
  "keyring",
  "ktem.docqa",
  "llama_index",
  "matplotlib",
  "mistralai",
  "networkx",
  "onnxruntime",
  "openai",
  "opentelemetry",
  "pandas",
  "posthog",
  "pyarrow",
  "pytest",
  "safetensors",
  "scipy",
  "sentence_transformers",
  "sklearn",
  "sphinx",
  "tensorflow",
  "tkinter",
  "tokenizers",
  "torch",
  "transformers",
];

for (const target of [buildRoot, outputRoot]) {
  if (!target.startsWith(`${desktopRoot}${path.sep}`)) {
    throw new Error(`Refusing to clean path outside desktop root: ${target}`);
  }
  rmSync(target, { recursive: true, force: true });
}

const python =
  process.env.MARA_DESKTOP_PYTHON ??
  (existsSync(workspacePython)
    ? workspacePython
    : process.platform === "win32"
      ? "python"
      : "python3");
const result = spawnSync(
  python,
  [
    "-m",
    "PyInstaller",
    "--clean",
    "--noconfirm",
    "--onedir",
    "--name",
    "mara-desktop-sidecar",
    "--distpath",
    outputRoot,
    "--workpath",
    buildRoot,
    "--specpath",
    buildRoot,
    ...[
      "ktem.default_flowsettings",
      "ktem.runtime_defaults",
      "slide_cli.docqa_runtime",
      "theflow.settings.default",
    ].flatMap((moduleName) => ["--hidden-import", moduleName]),
    ...[desktopRoot, ...workspacePackageRoots].flatMap((modulePath) => [
      "--paths",
      modulePath,
    ]),
    ...excludedDevelopmentModules.flatMap((moduleName) => [
      "--exclude-module",
      moduleName,
    ]),
    source,
  ],
  { cwd: desktopRoot, stdio: "inherit" },
);

if (result.error) {
  throw result.error;
}
if (result.status !== 0) {
  throw new Error(
    "Sidecar bundling failed. Install the pinned requirements from sidecar/requirements-build.txt.",
  );
}

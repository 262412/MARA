import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  rmSync,
  statSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

import {
  excludedSidecarModules,
  requiredSidecarDataDirectories,
  requiredSidecarDataPackages,
  requiredSidecarModules,
  requiredTiktokenEncodings,
  tiktokenCacheDestination,
} from "./sidecar-bundle-config.mjs";

const desktopRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(desktopRoot, "..", "..");
const buildRoot = path.join(desktopRoot, "build", "sidecar");
const generatedDataRoot = path.join(desktopRoot, "build", "sidecar-data");
const tiktokenCacheRoot = path.join(generatedDataRoot, "tiktoken-cache");
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
for (const target of [buildRoot, generatedDataRoot, outputRoot]) {
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
const buildRuntimeRoot = mkdtempSync(
  path.join(tmpdir(), "mara-desktop-sidecar-build-"),
);
const buildRuntimeEnvironment = {
  ...process.env,
  MARA_DESKTOP_BUILD_RUNTIME_ROOT: buildRuntimeRoot,
  PYTHONPATH: [desktopRoot, ...workspacePackageRoots, process.env.PYTHONPATH]
    .filter(Boolean)
    .join(path.delimiter),
  THEFLOW_SETTINGS_MODULE: "sidecar.build_flowsettings",
  THEFLOW_TEMP_PATH: path.join(buildRuntimeRoot, "tmp"),
};

try {
  mkdirSync(tiktokenCacheRoot, { recursive: true });
  const cacheResult = spawnSync(
    python,
    [
      "-c",
      "import sys, tiktoken; [tiktoken.get_encoding(name) for name in sys.argv[1:]]",
      ...requiredTiktokenEncodings,
    ],
    {
      cwd: buildRuntimeRoot,
      env: {
        ...buildRuntimeEnvironment,
        TIKTOKEN_CACHE_DIR: tiktokenCacheRoot,
      },
      stdio: "inherit",
    },
  );
  if (cacheResult.error) {
    throw cacheResult.error;
  }
  const cacheFiles = readdirSync(tiktokenCacheRoot).filter(
    (fileName) => statSync(path.join(tiktokenCacheRoot, fileName)).size > 0,
  );
  if (
    cacheResult.status !== 0 ||
    cacheFiles.length < requiredTiktokenEncodings.length
  ) {
    throw new Error("Failed to prepare the checked tiktoken cache for the Sidecar.");
  }
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
      ...requiredSidecarModules.flatMap((moduleName) => [
        "--hidden-import",
        moduleName,
      ]),
      ...requiredSidecarDataPackages.flatMap((packageName) => [
        "--collect-data",
        packageName,
      ]),
      ...requiredSidecarDataDirectories.flatMap(({ source, destination }) => [
        "--add-data",
        `${path.join(desktopRoot, source)}:${destination}`,
      ]),
      "--add-data",
      `${tiktokenCacheRoot}:${tiktokenCacheDestination}`,
      ...[desktopRoot, ...workspacePackageRoots].flatMap((modulePath) => [
        "--paths",
        modulePath,
      ]),
      ...excludedSidecarModules.flatMap((moduleName) => [
        "--exclude-module",
        moduleName,
      ]),
      source,
    ],
    {
      cwd: buildRuntimeRoot,
      env: buildRuntimeEnvironment,
      stdio: "inherit",
    },
  );

  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(
      "Sidecar bundling failed. Install the pinned requirements from sidecar/requirements-build.txt.",
    );
  }
} finally {
  rmSync(buildRuntimeRoot, { recursive: true, force: true });
}

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const desktopRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = path.resolve(desktopRoot, "..", "..");
const workspacePython = path.join(
  repositoryRoot,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
const python =
  process.env.MARA_DESKTOP_PYTHON ??
  (existsSync(workspacePython)
    ? workspacePython
    : process.platform === "win32"
      ? "python"
      : "python3");
const pythonPath = [
  desktopRoot,
  path.join(repositoryRoot, "libs", "ktem"),
  path.join(repositoryRoot, "libs", "kotaemon"),
  path.join(repositoryRoot, "libs", "slide_cli"),
  process.env.PYTHONPATH,
]
  .filter(Boolean)
  .join(path.delimiter);
const result = spawnSync(python, process.argv.slice(2), {
  cwd: desktopRoot,
  env: { ...process.env, PYTHONPATH: pythonPath },
  stdio: "inherit",
});

if (result.error) {
  throw result.error;
}
process.exitCode = result.status ?? 1;

import { spawnSync } from "node:child_process";
import { rmSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const desktopRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const buildRoot = path.join(desktopRoot, "build", "sidecar");
const outputRoot = path.join(desktopRoot, "resources", "sidecar");
const source = path.join(desktopRoot, "sidecar", "server.py");

for (const target of [buildRoot, outputRoot]) {
  if (!target.startsWith(`${desktopRoot}${path.sep}`)) {
    throw new Error(`Refusing to clean path outside desktop root: ${target}`);
  }
  rmSync(target, { recursive: true, force: true });
}

const python =
  process.env.MARA_DESKTOP_PYTHON ??
  (process.platform === "win32" ? "python" : "python3");
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

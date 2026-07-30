import { packager } from "@electron/packager";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const desktopRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const target = process.argv[2];

if (target !== "linux" && target !== "win32") {
  throw new Error("Usage: node scripts/package-app.mjs <linux|win32>");
}

const sourceDirectoryPattern = new RegExp(
  "^/(?:build|dist-tests|electron|node_modules|public|release|resources|scripts|shared|sidecar|src)(?:/|$)",
);
const sourceFilePattern = new RegExp(
  "^/(?:README\\.md|index\\.html|package-lock\\.json|tsconfig(?:\\.electron)?\\.json|vite\\.config\\.ts)$",
);
const compiledTestPattern = new RegExp(
  "^/dist-electron/.+\\.test\\.js$",
);

const appPaths = await packager({
  dir: desktopRoot,
  name: "MARA",
  platform: target,
  arch: "x64",
  out: path.join(desktopRoot, "release"),
  overwrite: true,
  asar: true,
  prune: true,
  extraResource: [path.join(desktopRoot, "resources", "sidecar")],
  ignore: [sourceDirectoryPattern, sourceFilePattern, compiledTestPattern],
});

for (const appPath of appPaths) {
  process.stdout.write(`Packaged MARA Desktop: ${appPath}\n`);
}

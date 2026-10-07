import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import type { Node } from "@oxc-project/types" with { "resolution-mode": "import" };

// This is a launch-owner guard, not a repository-wide dependency framework.
async function dependencies(source: string): Promise<string[]> {
  // Use the parser already installed by the locked Vite/Rolldown toolchain.
  const { parseAst } = await import("rolldown/parseAst");
  const tree = parseAst(source, { lang: "ts" }, "sidecar-launch.ts");
  const found: string[] = [];
  function visit(value: unknown) {
    if (Array.isArray(value)) { value.forEach(visit); return; }
    if (!value || typeof value !== "object") return;
    const node = value as Node;
    if ((node.type === "ImportDeclaration" || node.type === "ExportNamedDeclaration"
      || node.type === "ExportAllDeclaration") && node.source) found.push(node.source.value);
    if (node.type === "TSImportEqualsDeclaration"
      && node.moduleReference.type === "TSExternalModuleReference") {
      found.push(node.moduleReference.expression.value);
    }
    if (node.type === "ImportExpression" && node.source.type === "Literal"
      && typeof node.source.value === "string") found.push(node.source.value);
    if (node.type === "CallExpression" && node.callee.type === "Identifier"
      && node.callee.name === "require" && node.arguments[0]?.type === "Literal"
      && typeof node.arguments[0].value === "string") found.push(node.arguments[0].value);
    Object.values(value).forEach(visit);
  }
  visit(tree);
  return found;
}

async function violations(source: string): Promise<string[]> {
  return (await dependencies(source)).filter((name) => {
    const normalized = path.posix.normalize(name.replaceAll("\\", "/"));
    return ["node:child_process", "child_process", "electron"].includes(normalized)
      || /(?:^|\/)sidecar-manager(?:\.[cm]?[jt]s)?$/.test(normalized);
  });
}

test("launch configuration cannot acquire manager, Electron or process ownership", async () => {
  const source = fs.readFileSync(path.resolve("electron/sidecar-launch.ts"), "utf8");
  assert.deepEqual(await violations(source), []);
  assert.ok((await dependencies(source)).includes("./smoke-environment"));
});

for (const source of [
  'import { SidecarManager } from "./sidecar-manager";',
  'export { SidecarManager } from "./sidecar-manager.js";',
  'const owner = require("./internal/../sidecar-manager");',
  'async function late() { return import("node:child_process"); }',
  'import processOwner = require("child_process");',
  'import type { App } from "electron";',
]) {
  test(`launch boundary rejects ${source}`, async () => {
    assert.equal((await violations(source)).length, 1);
  });
}

test("launch boundary permits environment composition and ignores comments and strings", async () => {
  assert.deepEqual(await violations(`
    import path from "node:path";
    import { mergeSidecarEnvironment } from "./smoke-environment";
    // import { spawn } from "node:child_process";
    const explanation = 'import "electron"';
  `), []);
});

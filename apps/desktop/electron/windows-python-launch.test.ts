import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import test from "node:test";

import { resolveWindowsPythonLaunch } from "./sidecar-launch";

test("Windows venv launch keeps its environment and reports the spawned PID", {
  skip: process.platform !== "win32",
}, () => {
  const python = path.resolve("..", "..", ".venv", "Scripts", "python.exe");
  const launch = resolveWindowsPythonLaunch(python, process.env, false);
  const result = spawnSync(launch.executable, ["-c",
    "import json, os, sys; print(json.dumps({'pid': os.getpid(), 'prefix': sys.prefix, 'executable': sys.executable}))",
  ], { env: launch.environment, encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  const reported = JSON.parse(result.stdout);
  assert.equal(reported.pid, result.pid);
  assert.equal(path.resolve(reported.executable), python);
  assert.equal(path.resolve(reported.prefix), path.resolve("..", "..", ".venv"));
});

test("packaged commands and system interpreters keep their launch identity", () => {
  const environment = { OWNED_SETTING: "kept" };
  assert.deepEqual(resolveWindowsPythonLaunch("mara-desktop-sidecar.exe", environment, true), {
    executable: "mara-desktop-sidecar.exe", environment,
  });
  assert.deepEqual(resolveWindowsPythonLaunch("python", environment, false), {
    executable: "python", environment,
  });
});

import assert from "node:assert/strict";
import childProcess, { type ChildProcessWithoutNullStreams, type SpawnOptions } from "node:child_process";
import { EventEmitter } from "node:events";
import fs from "node:fs";
import path from "node:path";
import { PassThrough } from "node:stream";
import test, { type TestContext } from "node:test";

import { SidecarManager } from "./sidecar-manager";

type Command = { executable: string; args: string[] };
type Seams = {
  sidecarCommand(): Command;
  developmentPython(): string;
  waitForReady(): Promise<never>;
};

function context(t: TestContext, platform: NodeJS.Platform, inherited: NodeJS.ProcessEnv = {}) {
  const originalEnvironment = process.env;
  const originalPlatform = Object.getOwnPropertyDescriptor(process, "platform")!;
  process.env = { ...inherited };
  Object.defineProperty(process, "platform", { value: platform });
  t.after(() => {
    process.env = originalEnvironment;
    Object.defineProperty(process, "platform", originalPlatform);
  });
  const options = {
    appPath: path.resolve("owned workspace 资料", "apps", "desktop"),
    dataRoot: path.resolve("owned data 数据"),
    resourcesPath: path.resolve("owned resources 资源"),
    isPackaged: false,
  };
  const manager = new SidecarManager(options);
  return { options, manager, seams: manager as unknown as Seams };
}

for (const platform of ["win32", "linux"] as const) {
  test(`${platform}: explicit Python truthiness, one workspace lookup, then platform fallback`, (t) => {
    const { options, seams } = context(t, platform, { MARA_DESKTOP_PYTHON: " owned python 资料 " });
    const queries: fs.PathLike[] = [];
    let exists = true;
    t.mock.method(fs, "existsSync", (filename: fs.PathLike) => { queries.push(filename); return exists; });
    assert.equal(seams.developmentPython(), " owned python 资料 ");
    assert.deepEqual(queries, []);
    process.env.MARA_DESKTOP_PYTHON = "";
    const workspace = path.resolve(options.appPath, "..", "..", ".venv",
      platform === "win32" ? "Scripts/python.exe" : "bin/python");
    assert.equal(seams.developmentPython(), workspace);
    assert.deepEqual(queries, [workspace]);
    exists = false;
    assert.equal(seams.developmentPython(), platform === "win32" ? "python" : "python3");
    assert.deepEqual(queries, [workspace, workspace]);
  });

  test(`${platform}: packaged command never consults or falls back to development Python`, (t) => {
    const { options, seams } = context(t, platform);
    options.isPackaged = true;
    t.mock.method(fs, "existsSync", () => { throw new Error("Unexpected existence check"); });
    seams.developmentPython = () => { throw new Error("Unexpected development fallback"); };
    assert.deepEqual(seams.sidecarCommand(), {
      executable: path.join(options.resourcesPath, "sidecar", "mara-desktop-sidecar",
        platform === "win32" ? "mara-desktop-sidecar.exe" : "mara-desktop-sidecar"),
      args: [],
    });
  });
}

test("development command preserves its original developmentPython patch seam", (t) => {
  const { seams } = context(t, process.platform);
  let calls = 0;
  seams.developmentPython = () => { calls += 1; return "patched owned Python"; };
  assert.deepEqual(seams.sidecarCommand(), { executable: "patched owned Python", args: ["-m", "sidecar.server"] });
  assert.equal(calls, 1);
});

function captureLaunch(t: TestContext, isPackaged: boolean) {
  const inherited = {
    PYTHONPATH: "inherited-python-path",
    MARA_DESKTOP_TOKEN: "inherited-fake-token",
    MARA_DESKTOP_SMOKE_STARTUP_DELAY_MS: "9000",
    MARA_DESKTOP_QUERY_SMOKE_FAULT_TOKEN: "untrusted-fake-smoke-token",
    MODEL_SETTING: "inherited-setting",
    UNDEFINED_VALUE: undefined,
  };
  const { options } = context(t, process.platform, inherited);
  options.isPackaged = isPackaged;
  const calls: string[] = [];
  const trusted = Object.freeze({
    PYTHONPATH: "trusted-python-path",
    MARA_DESKTOP_TOKEN: "trusted-fake-token",
    MARA_DESKTOP_DATA_DIR: "untrusted-data-override",
    KH_APP_DATA_DIR: "untrusted-state-override",
    THEFLOW_SETTINGS_MODULE: "untrusted-settings-override",
    KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED: "0",
    MARA_DESKTOP_SMOKE_STARTUP_DELAY_MS: "1500",
    MARA_DESKTOP_SETTINGS_REVISION: "revision-snapshot",
    MODEL_SETTING: "trusted-setting",
  });
  const manager = new SidecarManager({ ...options, smokeFault: "disk_full",
    environment: () => { calls.push("settings"); return trusted; },
    onStatus: (status) => { calls.push(status.state); },
  });
  const seams = manager as unknown as Seams;
  seams.sidecarCommand = () => { calls.push("command"); return { executable: "patched command", args: ["owned argument"] }; };
  seams.waitForReady = async () => { calls.push("ready"); throw new Error("owned handoff sentinel"); };
  const child = Object.assign(new EventEmitter(), {
    pid: 12345, stdout: new PassThrough(), stderr: new PassThrough(), stdin: new PassThrough(),
    exitCode: null as number | null, signalCode: null,
    kill: () => { calls.push("kill"); queueMicrotask(() => { child.exitCode = 0; child.emit("exit", 0, null); }); return true; },
  });
  let captured: SpawnOptions | undefined;
  t.mock.method(childProcess, "spawn", ((command: string, args: string[], spawnOptions: SpawnOptions) => {
    calls.push("spawn");
    assert.equal(command, "patched command");
    assert.deepEqual(args, ["owned argument"]);
    captured = spawnOptions;
    return child as unknown as ChildProcessWithoutNullStreams;
  }) as typeof childProcess.spawn);
  t.mock.method(fs, "mkdirSync", ((directory: fs.PathLike, flags: object) => {
    calls.push("mkdir");
    assert.equal(directory, path.join(options.dataRoot, "tmp"));
    assert.deepEqual(flags, { recursive: true });
    return undefined;
  }) as typeof fs.mkdirSync);
  return { manager, options, calls, inherited, trusted, captured: () => captured! };
}

for (const isPackaged of [false, true]) {
  test(`${isPackaged ? "packaged" : "development"}: launch ordering, environment priority and nonmutation`, async (t) => {
    const setup = captureLaunch(t, isPackaged);
    assert.equal((await setup.manager.start()).state, "failed");
    assert.deepEqual(setup.calls, ["settings", "starting", "command", "mkdir", "spawn", "ready", "kill", "failed"]);
    const launch = setup.captured();
    assert.equal(launch.cwd, path.join(setup.options.dataRoot, "tmp"));
    assert.equal(launch.windowsHide, true);
    assert.deepEqual(launch.stdio, ["pipe", "pipe", "pipe"]);
    const environment = launch.env!;
    assert.equal(environment.MODEL_SETTING, "trusted-setting");
    assert.equal(environment.MARA_DESKTOP_SMOKE_STARTUP_DELAY_MS, "1500");
    assert.equal(environment.MARA_DESKTOP_QUERY_SMOKE_FAULT_TOKEN, undefined);
    assert.equal(environment.UNDEFINED_VALUE, undefined);
    assert.equal(environment.MARA_DESKTOP_SMOKE_FAULT, "disk_full");
    assert.equal(environment.MARA_DESKTOP_DATA_DIR, setup.options.dataRoot);
    assert.equal(environment.KH_APP_DATA_DIR, path.join(setup.options.dataRoot, "state", "ktem_app_data"));
    assert.equal(environment.THEFLOW_SETTINGS_MODULE, "ktem.default_flowsettings");
    assert.equal(environment.KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED, "1");
    assert.ok(/^[a-f0-9]{64}$/.test(environment.MARA_DESKTOP_TOKEN!));
    assert.equal(environment.MARA_DESKTOP_SETTINGS_REVISION, "revision-snapshot");
    const root = path.resolve(setup.options.appPath, "..", "..");
    assert.equal(environment.PYTHONPATH, isPackaged ? "trusted-python-path" : [
      setup.options.appPath, ...["ktem", "kotaemon", "slide_cli"].map((name) => path.join(root, "libs", name)),
      "inherited-python-path",
    ].join(path.delimiter));
    assert.deepEqual(process.env, setup.inherited);
    assert.equal(setup.trusted.MARA_DESKTOP_TOKEN, "trusted-fake-token");
  });
}

test("mkdir failure remains after command selection and before spawn", async (t) => {
  const setup = captureLaunch(t, false);
  t.mock.method(fs, "mkdirSync", () => { setup.calls.push("mkdir failed"); throw new Error("owned mkdir failure"); });
  await assert.rejects(setup.manager.start(), /owned mkdir failure/);
  assert.deepEqual(setup.calls, ["settings", "starting", "command", "mkdir failed"]);
  assert.equal(setup.captured(), undefined);
});

test("packaged startup retains inherited PYTHONPATH when trusted settings omit it", async (t) => {
  const setup = captureLaunch(t, true);
  (setup.manager as unknown as { options: { environment: () => object } }).options.environment = () => ({});
  await setup.manager.start();
  assert.equal(setup.captured().env!.PYTHONPATH, "inherited-python-path");
});

test("development PYTHONPATH omits an empty inherited entry", async (t) => {
  const setup = captureLaunch(t, false);
  process.env.PYTHONPATH = "";
  await setup.manager.start();
  const root = path.resolve(setup.options.appPath, "..", "..");
  assert.equal(setup.captured().env!.PYTHONPATH, [setup.options.appPath,
    ...["ktem", "kotaemon", "slide_cli"].map((name) => path.join(root, "libs", name)),
  ].join(path.delimiter));
});

test("spawn exceptions remain after mkdir without a fake healthy transition", async (t) => {
  const setup = captureLaunch(t, false);
  t.mock.method(childProcess, "spawn", () => { setup.calls.push("spawn failed"); throw new Error("owned spawn failure"); });
  await assert.rejects(setup.manager.start(), /owned spawn failure/);
  assert.deepEqual(setup.calls, ["settings", "starting", "command", "mkdir", "spawn failed"]);
  assert.equal(setup.manager.getStatus().state, "starting");
});

test("settings callback errors remain synchronous and precede starting state", (t) => {
  const { options } = context(t, process.platform);
  const statuses: string[] = [];
  const manager = new SidecarManager({ ...options, onStatus: (status) => statuses.push(status.state),
    environment: () => { throw new Error("owned settings failure"); },
  });
  assert.throws(() => manager.start(), /owned settings failure/);
  assert.deepEqual(statuses, []);
});

test("startup reads settings once, snapshots revision and reuses only the matching explicit revision", async (t) => {
  const { options } = context(t, process.platform);
  let settingsCalls = 0;
  const environment = { MARA_DESKTOP_SETTINGS_REVISION: "revision-one" };
  const manager = new SidecarManager({ ...options, environment: () => { settingsCalls += 1; return { ...environment }; } });
  let finish!: (status: ReturnType<SidecarManager["getStatus"]>) => void;
  (manager as unknown as { launch: (generation: number, revision: string, settings: object) => Promise<ReturnType<SidecarManager["getStatus"]>> }).launch =
    async (_generation, revision, settings) => {
      assert.equal(revision, "revision-one");
      assert.deepEqual(settings, { MARA_DESKTOP_SETTINGS_REVISION: "revision-one" });
      return new Promise((resolve) => { finish = resolve; });
    };
  const first = manager.start();
  environment.MARA_DESKTOP_SETTINGS_REVISION = "revision-two";
  assert.equal(manager.start("revision-one"), first);
  await assert.rejects(manager.start("revision-two"), /different settings revision/);
  // Omitted expectedRevision is not equal to the snapshotted revision in the existing API.
  await assert.rejects(manager.start(), /different settings revision/);
  assert.equal(settingsCalls, 1);
  finish({ state: "healthy", protocol: 1, capabilities: [] });
  await first;
});

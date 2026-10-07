import assert from "node:assert/strict";
import type { ChildProcessWithoutNullStreams } from "node:child_process";
import { once } from "node:events";
import { mkdtempSync, rmSync } from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import test, { type TestContext } from "node:test";

import { SidecarManager } from "./sidecar-manager";

// A real owned process/HTTP peer; it never imports MARA or reads user data.
// Native Sidecar/application-service evidence is provided separately by Gate 2.
const CHILD = String.raw`
const http = require('node:http');
const mode = process.env.OWNED_SIDECAR_MODE;
const revision = process.env.MARA_DESKTOP_SETTINGS_REVISION || null;
const server = http.createServer((request, response) => {
  const requestId = request.headers['x-request-id'];
  response.setHeader('Content-Type', 'application/json');
  if (request.headers.authorization !== 'Bearer ' + process.env.MARA_DESKTOP_TOKEN) {
    response.writeHead(401); response.end('{}'); return;
  }
  let payload;
  if (request.url === '/health') {
    payload = {state:'healthy', protocol:1, version:'owned-fixture', capabilities:['doctor','files'],
      model_settings_revision: mode === 'health-revision' ? 'wrong' : revision, request_id:requestId};
  } else if (request.url === '/v1/doctor') {
    payload = {request_id:requestId, doctor:{sidecar_pid:process.pid,
      settings_revision:mode === 'doctor-revision' ? 'wrong' : revision,
      route_fingerprint:mode === 'fingerprint' ? 'invalid' : 'a'.repeat(64)}};
    if (mode === 'crash-after-ready') setTimeout(() => process.exit(9), 30);
  } else if (request.url === '/v1/files') {
    payload = {request_id:requestId, files:[]};
  } else if (request.url === '/shutdown') {
    payload = {ok:true};
    if (mode !== 'ignore-shutdown') setTimeout(() => process.exit(0), 30);
  } else { response.writeHead(404); payload = {}; }
  response.end(JSON.stringify(payload));
});
server.listen(0, '127.0.0.1', () => {
  const message = JSON.stringify({type:'ready', protocol:mode === 'protocol' ? 999 : 1,
    port:server.address().port, pid:mode === 'pid' ? process.pid + 1 : process.pid}) + '\n';
  const ready = () => {
    if (mode === 'malformed') { process.stdout.write('not-json\n'); return; }
    if (mode === 'exit-before-ready') { process.exit(7); return; }
    if (mode === 'oversize') { process.stdout.write('x'.repeat(8193)); return; }
    process.stdout.write(message.slice(0, 17));
    setImmediate(() => process.stdout.write(message.slice(17)));
  };
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', text => { if (text.trim() === 'ready') ready(); if (text.trim() === 'crash') process.exit(9); });
  process.stdin.on('end', () => process.exit(0));
  process.stderr.write('owned-listening\n');
  if (mode !== 'pending') ready();
});
`;

type Internals = {
  child?: ChildProcessWithoutNullStreams;
  port?: number;
  sidecarCommand(): { executable: string; args: string[] };
};

function alive(pid: number): boolean {
  try { process.kill(pid, 0); return true; }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ESRCH") return false;
    throw error;
  }
}

function fixture(t: TestContext, mode: string) {
  const root = mkdtempSync(path.join(os.tmpdir(), "mara-sidecar 资料 "));
  const statuses: string[] = [];
  const children: ChildProcessWithoutNullStreams[] = [];
  const startsWithLiveChildren: number[][] = [];
  let revision = "owned-revision-1";
  const manager = new SidecarManager({ appPath: root, dataRoot: root, resourcesPath: root,
    isPackaged: true, environment: () => ({ OWNED_SIDECAR_MODE: mode,
      MARA_DESKTOP_SETTINGS_REVISION: revision, HOME: root, USERPROFILE: root,
      XDG_CONFIG_HOME: root, XDG_CACHE_HOME: root, XDG_DATA_HOME: root, TEMP: root, TMP: root }),
    onStatus: (status) => {
      statuses.push(status.state);
      if (status.state === "starting") startsWithLiveChildren.push(children.filter((child) => alive(child.pid!)).map((child) => child.pid!));
    },
  });
  const internal = manager as unknown as Internals;
  internal.sidecarCommand = () => {
    queueMicrotask(() => { if (internal.child && !children.includes(internal.child)) children.push(internal.child); });
    return { executable: process.execPath, args: ["-e", CHILD] };
  };
  t.after(async () => {
    // Cancel automatic restart before disposing only the PIDs this fixture owns.
    const stopping = manager.stop();
    for (const child of children) {
      if (child.exitCode === null && child.signalCode === null) {
        const exited = once(child, "exit");
        child.kill("SIGKILL");
        await exited;
      }
      assert.equal(alive(child.pid!), false);
    }
    await stopping;
    rmSync(root, { recursive: true });
  });
  function start() {
    const startup = manager.start(revision);
    const child = internal.child!;
    assert.ok(child?.pid);
    children.push(child);
    let exited = false;
    const exit = new Promise<void>((resolve) => child.once("exit", () => { exited = true; resolve(); }));
    const listening = new Promise<void>((resolve) => child.stderr.on("data", (chunk: string) => {
      if (String(chunk).includes("owned-listening")) resolve();
    }));
    return { startup, child, exit, listening, exited: () => exited };
  }
  return { manager, internal, start, statuses, children, startsWithLiveChildren,
    setRevision: (value: string) => { revision = value; } };
}

async function until(predicate: () => boolean) {
  const deadline = Date.now() + 8000;
  while (!predicate()) {
    assert.ok(Date.now() < deadline, "owned lifecycle condition did not complete");
    await new Promise<void>((resolve) => setTimeout(resolve, 10));
  }
}

async function portReleased(port: number) {
  const listener = net.createServer();
  listener.listen(port, "127.0.0.1");
  await once(listener, "listening");
  await new Promise<void>((resolve, reject) => listener.close((error) => error ? reject(error) : resolve()));
}

test("real cold start accepts split ready, authenticates requests and releases PID/port", { timeout: 10000 }, async (t) => {
  const f = fixture(t, "normal");
  const run = f.start();
  const files = f.manager.listFiles();
  assert.equal((await run.startup).state, "healthy");
  assert.deepEqual(await files, { ok: true, data: [] });
  const port = f.internal.port!;
  await f.manager.stop();
  assert.equal(run.exited(), true, "stop must wait for the owned process exit event");
  assert.equal(alive(run.child.pid!), false);
  await portReleased(port);
});

test("stop during real startup returns only after the OS process exits", { timeout: 10000 }, async (t) => {
  const f = fixture(t, "pending");
  const run = f.start();
  await run.listening;
  await f.manager.stop();
  assert.equal(run.exited(), true, "stopped status or successful kill is not process exit");
  assert.equal(alive(run.child.pid!), false);
  assert.equal((await run.startup).state, "stopped");
});

test("failed real ready handshake retains ownership until the process exits", { timeout: 10000 }, async (t) => {
  const f = fixture(t, "malformed");
  const run = f.start();
  assert.equal((await run.startup).state, "failed");
  assert.equal(run.exited(), true, "startup failure must reap its child before dropping ownership");
  assert.equal(alive(run.child.pid!), false);
});

for (const mode of ["protocol", "pid", "health-revision", "doctor-revision", "fingerprint", "oversize"]) {
  test(`real ${mode} failure exits before releasing process ownership`, { timeout: 10000 }, async (t) => {
    const f = fixture(t, mode);
    const run = f.start();
    assert.equal((await run.startup).state, "failed");
    assert.equal(run.exited(), true);
    assert.equal(alive(run.child.pid!), false);
    assert.equal(f.internal.child, undefined);
    assert.equal(f.internal.port, undefined);
    assert.ok(!f.statuses.includes("healthy"));
  });
}

test("missing packaged executable reports spawn failure without a Python fallback", { timeout: 10000 }, async (t) => {
  const f = fixture(t, "normal");
  f.internal.sidecarCommand = () => ({ executable: path.join(os.tmpdir(), "owned-nonexistent-sidecar", "missing.exe"), args: [] });
  const startup = f.manager.start("owned-revision-1");
  const child = f.internal.child!;
  assert.equal(child.pid, undefined);
  assert.equal((await startup).state, "failed");
  assert.equal(f.internal.child, undefined);
});

test("real exit before ready is recorded and pending automatic restart can be stopped", { timeout: 10000 }, async (t) => {
  const f = fixture(t, "exit-before-ready");
  const run = f.start();
  assert.equal((await run.startup).state, "failed");
  assert.equal(run.child.exitCode, 7);
  await f.manager.stop();
  assert.equal(f.manager.getStatus().state, "stopped");
  assert.equal(f.children.length, 1);
});

test("original 20-second ready deadline terminates an owned pending process", { timeout: 10000 }, async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const f = fixture(t, "pending");
  const run = f.start();
  await run.listening;
  t.mock.timers.tick(20000);
  const status = await run.startup;
  assert.equal(status.state, "failed");
  assert.match(status.message!, /startup timed out/);
  assert.equal(run.exited(), true);
});

test("concurrent stop and fresh start wait for the old PID; late generation callbacks cannot overwrite", { timeout: 10000 }, async (t) => {
  const f = fixture(t, "pending");
  const old = f.start();
  await old.listening;
  const lateExit = old.child.listeners("exit")[0]!;
  const lateReady = old.child.stdout.listeners("data")[0]!;
  const firstStop = f.manager.stop();
  const secondStop = f.manager.stop();
  f.setRevision("owned-revision-2");
  const starting = f.manager.start("owned-revision-2");
  await Promise.all([firstStop, secondStop]);
  assert.equal(old.exited(), true);
  await until(() => !!f.internal.child && f.internal.child !== old.child);
  const current = f.internal.child!;
  current.stdin.write("ready\n");
  assert.equal((await starting).state, "healthy");
  const port = f.internal.port;
  lateExit(9, null);
  lateReady(Buffer.from('{"type":"ready","protocol":1,"pid":1,"port":8768}\n'));
  assert.equal(f.internal.child, current);
  assert.equal(f.internal.port, port);
  assert.equal(f.manager.getStatus().state, "healthy");
  assert.deepEqual(await f.manager.listFiles(), { ok: true, data: [] });
  assert.ok(f.startsWithLiveChildren.every((pids) => pids.length === 0));
  await old.startup;
});

test("explicit restart queue closes each real PID before launching its successor", { timeout: 10000 }, async (t) => {
  const f = fixture(t, "normal");
  await f.start().startup;
  f.setRevision("owned-revision-2");
  const results = await Promise.all([f.manager.restart("owned-revision-2"), f.manager.restart("owned-revision-2")]);
  assert.ok(results.every((status) => status.state === "healthy"));
  assert.equal(f.children.length, 3);
  assert.ok(f.startsWithLiveChildren.every((pids) => pids.length === 0));
  assert.deepEqual(await f.manager.listFiles(), { ok: true, data: [] });
});

test("automatic restart budget applies to actual crashes without overlapping PIDs", { timeout: 10000 }, async (t) => {
  const f = fixture(t, "crash-after-ready");
  await f.start().startup;
  await until(() => f.manager.getStatus().message?.includes("budget was exhausted") === true);
  assert.equal(f.children.length, 4);
  assert.ok(f.children.every((child) => child.exitCode === 9 && !alive(child.pid!)));
  assert.ok(f.startsWithLiveChildren.every((pids) => pids.length === 0));
});

test("real parent EOF releases the child PID and port", { timeout: 10000 }, async (t) => {
  const f = fixture(t, "normal");
  const run = f.start();
  await run.startup;
  const port = f.internal.port!;
  run.child.stdin.end();
  await run.exit;
  await f.manager.stop();
  assert.equal(run.child.exitCode, 0);
  assert.equal(alive(run.child.pid!), false);
  await portReleased(port);
});

test("termination failure rejects stop and preserves ownership without reporting healthy or stopped", { timeout: 10000 }, async (t) => {
  const f = fixture(t, "ignore-shutdown");
  const run = f.start();
  await run.startup;
  const seam = f.manager as unknown as { terminateChild(child: ChildProcessWithoutNullStreams): Promise<void> };
  const terminate = seam.terminateChild;
  seam.terminateChild = async () => { throw new Error("owned termination failure"); };
  try {
    await assert.rejects(f.manager.stop(), /owned termination failure/);
    assert.equal(f.internal.child, run.child);
    assert.equal(alive(run.child.pid!), true);
    assert.equal(f.manager.getStatus().state, "failed");
  } finally {
    seam.terminateChild = terminate;
  }
});

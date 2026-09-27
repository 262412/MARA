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
  let revision = "owned-revision-1";
  const manager = new SidecarManager({ appPath: root, dataRoot: root, resourcesPath: root,
    isPackaged: true, environment: () => ({ OWNED_SIDECAR_MODE: mode,
      MARA_DESKTOP_SETTINGS_REVISION: revision, HOME: root, USERPROFILE: root,
      XDG_CONFIG_HOME: root, XDG_CACHE_HOME: root, XDG_DATA_HOME: root, TEMP: root, TMP: root }),
    onStatus: (status) => statuses.push(status.state),
  });
  const internal = manager as unknown as Internals;
  const children: ChildProcessWithoutNullStreams[] = [];
  internal.sidecarCommand = () => ({ executable: process.execPath, args: ["-e", CHILD] });
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
  return { manager, internal, start, statuses, children, setRevision: (value: string) => { revision = value; } };
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

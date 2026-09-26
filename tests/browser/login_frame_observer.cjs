// Bounded diagnostics of this owned App. Never replace global frame/timer APIs.
const fs = require('node:fs');
const path = require('node:path');

function install(world) {
  const nativeRAF = window.requestAnimationFrame;
  const nativeCancel = window.cancelAnimationFrame;
  const nativeText = Function.prototype.toString;
  const frames = new Set(), timers = new Set(), records = [];
  const identity = {world, worldToken: crypto.randomUUID(), timeOrigin: performance.timeOrigin,
    installedReadyState: document.readyState};
  let dropped = 0;
  const record = (kind, values = {}) => {
    if (records.length < 128) records.push({kind, at: performance.now(), ...values});
    else dropped++;
  };
  const state = () => ({url: location.href, readyState: document.readyState,
    visibility: document.visibilityState, focus: document.hasFocus(),
    sameRAF: nativeRAF === window.requestAnimationFrame,
    sameCancel: nativeCancel === window.cancelAnimationFrame,
    nativeRAF: nativeText.call(nativeRAF), currentRAF: nativeText.call(window.requestAnimationFrame),
    buttons: [...document.querySelectorAll('button')].filter(node => /Login|登录/.test(node.textContent))
      .map(node => ({rect: node.getBoundingClientRect().toJSON(), disabled: node.disabled,
        display: getComputedStyle(node).display, visibility: getComputedStyle(node).visibility,
        animations: node.getAnimations().map(animation => animation.playState)}))});
  const burst = phase => {
    record('burst', {phase, state: state()});
    for (const [api, request] of [['saved-native', nativeRAF], ['current', window.requestAnimationFrame]]) {
      const id = request.call(window, time => {
        frames.delete(id);
        record('raf-callback', {phase, api, id, time});
      });
      frames.add(id);
      record('raf-request', {phase, api, id});
    }
    for (const delay of [100, 1500, 15000, 29000]) {
      const id = setTimeout(() => {
        timers.delete(id);
        record('timer', {phase, delay, state: state()});
      }, delay);
      timers.add(id);
    }
  };
  const events = ['visibilitychange', 'freeze', 'resume', 'pagehide', 'pageshow', 'focus', 'blur'];
  const listener = event => record('lifecycle', {type: event.type, persisted: event.persisted});
  for (const name of events) window.addEventListener(name, listener, true);
  const snapshot = () => ({identity, records: records.slice(), state: state(), dropped,
    pendingRAF: [...frames], pendingTimers: [...timers]});
  window.ownedLoginFrameProbe = {burst, snapshot,
    stop: () => {
      for (const id of frames) { nativeCancel.call(window, id); record('raf-cancel', {id}); }
      for (const id of timers) { clearTimeout(id); record('timer-cancel', {id}); }
      frames.clear(); timers.clear();
      for (const name of events) window.removeEventListener(name, listener, true);
      return snapshot();
    }};
  burst('probe-install');
}

async function bounded(operation, ms = 2000) {
  let timer;
  try {
    return await Promise.race([operation, new Promise((_, reject) => {
      timer = setTimeout(() => reject(Error('Login observation deadline')), ms);
    })]);
  } finally { clearTimeout(timer); }
}

async function attach(page, output, options) {
  const cdp = await bounded(page.context().newCDPSession(page));
  const contexts = new Map(), events = [], snapshots = [];
  const listeners = [];
  let droppedEvents = 0;
  const name = `login-frames-${options.ordinal}.json`;
  const save = () => fs.writeFileSync(path.join(output, name), JSON.stringify({options, events, snapshots, droppedEvents}, null, 2));
  const on = (event, action) => {
    const listener = params => {
      if (events.length < 512) events.push({event, at: Date.now(), params});
      else droppedEvents++;
      if (action) action(params);
    };
    listeners.push([event, listener]); cdp.on(event, listener);
  };
  on('Runtime.executionContextCreated', ({context}) => contexts.set(context.id, context));
  on('Runtime.executionContextDestroyed', ({executionContextId}) => contexts.delete(executionContextId));
  on('Runtime.executionContextsCleared', () => contexts.clear());
  for (const name of ['Page.frameAttached', 'Page.frameDetached', 'Page.frameNavigated',
    'Page.lifecycleEvent', 'Page.frameStartedLoading', 'Page.frameStoppedLoading',
    'Debugger.paused', 'Debugger.resumed', 'Inspector.targetCrashed']) on(name);
  await bounded(cdp.send('Page.enable'));
  await bounded(cdp.send('Page.setLifecycleEventsEnabled', {enabled: true}));
  await bounded(cdp.send('Runtime.enable'));
  await bounded(cdp.send('Debugger.enable')); // No breakpoints or pause/resume commands.
  options.browser = await bounded(cdp.send('Browser.getVersion'));
  options.createdWorlds = [];
  options.extraUniversalAccess = false;
  save();
  const evaluate = async (contextId, expression) => {
    const value = await bounded(cdp.send('Runtime.evaluate', {
      contextId, expression, returnByValue: true, timeout: 1000,
    }));
    if (value.exceptionDetails) throw Error(JSON.stringify(value.exceptionDetails));
    return value.result.value;
  };
  const snapshot = async (phase, burst = false) => {
    const row = {phase, at: Date.now(), worlds: []};
    snapshots.push(row);
    try {
      const {frameTree} = await bounded(cdp.send('Page.getFrameTree'));
      row.frame = frameTree.frame;
      for (const context of contexts.values()) {
        if (context.auxData?.frameId !== row.frame.id) continue;
        const main = context.auxData.isDefault;
        // The installed 1.61.1 Chromium adapter uses this name for its real utility world.
        const utility = context.name.startsWith('__playwright_utility_world_');
        if (!main && !utility) continue;
        if (utility) await evaluate(context.id,
          `window.ownedLoginFrameProbe || (${install.toString()})('actual-playwright-utility')`);
        if (burst) await evaluate(context.id, `window.ownedLoginFrameProbe.burst(${JSON.stringify(phase)})`);
        row.worlds.push({context, probe: await evaluate(context.id, 'window.ownedLoginFrameProbe?.snapshot()')});
      }
    } catch (error) { row.error = String(error); }
    save();
    return row;
  };
  let stopped = false;
  return {snapshot, async stop() {
    if (stopped) return;
    stopped = true;
    await snapshot('observer-stop');
    for (const context of contexts.values()) {
      if (!context.auxData?.isDefault && !context.name.startsWith('__playwright_utility_world_')) continue;
      try {
        const probe = await evaluate(context.id, 'window.ownedLoginFrameProbe?.stop()');
        if (probe) events.push({event: 'observer-stopped', context, probe});
      }
      catch (error) { events.push({event: 'observer-stop-error', error: String(error)}); }
    }
    for (const [event, listener] of listeners) cdp.off(event, listener);
    await bounded(cdp.detach()); save();
  }};
}

module.exports = {install, attach, bounded};

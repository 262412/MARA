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

// This diagnostic is tied to the installed 1.61.1 generated code, not a guessed URL.
const STABILITY_CORE_SHA256 = '6be5c2ea035554e9b184b1dbc7aa5e7f1fb428dd1b5c202022858dcfae9bee27';
const sha256 = value => require('node:crypto').createHash('sha256').update(value).digest('hex');

function stabilitySources() {
  const root = path.dirname(require.resolve('playwright-core/package.json'));
  if (JSON.parse(fs.readFileSync(path.join(root, 'package.json'))).version !== '1.61.1') {
    throw Error('Actual stability observation requires Playwright 1.61.1');
  }
  const file = path.join(root, 'lib/coreBundle.js');
  const core = fs.readFileSync(file, 'utf8');
  if (sha256(core) !== STABILITY_CORE_SHA256) throw Error('Unrecognized Playwright generated bundle');
  const literal = core.match(/\bsource4 = ('(?:\\.|[^'\\])*');/g);
  if (literal?.length !== 1) throw Error('Generated injected source is not unique');
  // Evaluate only the hash-verified string literal, never the injected program.
  const injected = require('node:vm').runInNewContext(literal[0].slice('source4 = '.length, -1), {}, {timeout: 1000});
  return {file, core, injected, coreSha256: sha256(core), injectedSha256: sha256(injected)};
}

function uniquePoint(code, start, end, needle) {
  const begin = code.indexOf(start), finish = code.indexOf(end, begin + start.length);
  if (begin < 0 || finish < 0) throw Error('Missing logpoint scope');
  const offset = code.indexOf(needle, begin);
  const next = code.indexOf(needle, offset + needle.length);
  if (offset < begin || offset >= finish || next !== -1 && next < finish) throw Error('Nonunique scoped logpoint');
  const before = code.slice(0, offset).split('\n');
  return {lineNumber: before.length - 1, columnNumber: before.at(-1).length};
}

function logCondition(key, phase, call) {
  return `(()=>{try{globalThis.${key}?.${call}}catch(e){globalThis.${key}?.gap(${JSON.stringify(phase)},String(e))}return false})()`;
}

function injectedStabilityPoints(code, injected) {
  const offset = code.indexOf(injected);
  if (offset < 0 || code.indexOf(injected, offset + injected.length) !== -1) throw Error('Loaded injected source mismatch');
  const prefix = code.slice(0, offset).replace(/\s/g, '');
  const suffix = code.slice(offset + injected.length).match(/^\s*return new \(module\.exports\.InjectedScript\(\)\)\(globalThis, ([^\n]+)\);\s*\}\)\(\);\s*$/);
  if (prefix !== '(()=>{constmodule={};' || !suffix || !JSON.parse(suffix[1]).isUtilityWorld) {
    throw Error('Unrecognized actual utility injection wrapper');
  }
  const states = 'async checkElementStates(node, states) {', stable = 'async _checkElementIsStable(node) {';
  const end = '_createAriaRefEngine() {';
  const definitions = [
    ['states-enter', states, stable, 'if (states.includes("stable")) {', '{states}'],
    ['stable-awaited', states, stable, 'if (stableResult === false)', '{stableResult}'],
    ['other-state-result', states, stable, 'if (result.received === "error:notconnected")', '{state,result}'],
    ['stable-enter', stable, end, 'const continuePolling = Symbol("continuePolling");', '{required:this._stableRafCount}'],
    ['retarget-result', stable, end, 'if (!element)', '{connected:!!element,nodeConnected:node.isConnected}'],
    ['rect', stable, end, 'if (lastRect) {', '{rect,lastRect,stableRafCounter,lastTime}'],
    ['raf-enter', stable, end, 'const success = check();', '{stableRafCounter,lastTime,lastRect}'],
    ['check-result', stable, end, 'if (success !== continuePolling)', '{success:success===continuePolling?"continuePolling":success,stableRafCounter,lastRect}'],
    ['resolve', stable, end, 'fulfill(success);', '{success}'],
    ['reject', stable, end, 'reject(e);', '{error:String(e).slice(0,500)}'],
    ['raf-next', stable, end, '          this.utils.builtins.requestAnimationFrame(raf);', '{stableRafCounter}'],
    ['raf-first', stable, end, '    this.utils.builtins.requestAnimationFrame(raf);\n    return result;', '{required:this._stableRafCount,rafText:Function.prototype.toString.call(this.utils.builtins.requestAnimationFrame),sameCurrent:this.utils.builtins.requestAnimationFrame===globalThis.requestAnimationFrame}'],
    ['promise-return', stable, end, 'return result;', '{promise:result instanceof Promise}'],
  ];
  return {options: JSON.parse(suffix[1]), points: definitions.map(([phase, start, stop, needle, values]) => ({
    phase, ...uniquePoint(code, start, stop, needle),
    condition: logCondition('__maraActualStability', phase, `record(${JSON.stringify(phase)},node,${values})`),
  }))};
}

function installStabilityTrace(action, binding) {
  if (globalThis.__maraActualStability) throw Error('Actual stability trace already installed');
  const targets = [...document.querySelectorAll('button')].filter(node => /Login|登录/.test(node.textContent));
  if (targets.length !== 1) throw Error('Actual Login node is not unique');
  const target = targets[0], records = [];
  let dropped = 0, errors = 0;
  const trace = globalThis.__maraActualStability = {target, action,
    record(phase, node, values) {
      if (node !== target) return;
      if (records.length >= 128) { dropped++; return; }
      try {
        const row = {sequence: records.length, at: performance.now(), action, phase,
          node: 'login-target', sameDocument: node.ownerDocument === document, ...values};
        const payload = JSON.stringify(row);
        if (payload.length > 4000) throw Error('Actual stability record too long');
        records.push(row); globalThis[binding](payload);
      } catch (error) { errors++; }
    },
    gap(phase, error) { trace.record('condition-error', target, {failedPhase: phase, error: error.slice(0,500)}); },
    snapshot: () => ({action, records, dropped, errors})};
  trace.record('installed', target, {timeOrigin: performance.timeOrigin, url: location.href});
}

function nodeStabilityPoints(core) {
  const pointer = 'async _performPointerAction(progress2, actionName,';
  const utility = 'async evaluateInUtility(pageFunction, arg) {', utilityEnd = 'async _evaluateHandleInUtility(';
  const dispatch = 'async evaluateWithArguments(expression2, returnByValue, utilityScript, values, handles) {';
  const definitions = [
    ['pointer-dispatch', pointer, 'if (options.__testHookAfterStable)',
      'const result2 = await progress2.race(this.evaluateInUtility(',
      '{frame:this._frame._id,object:this._objectId,states:elementStates,apiId:progress2.metadata.id,apiName:progress2.metadata.apiName}'],
    ['pointer-result', pointer, 'if (options.__testHookAfterStable)', 'if (result2)\n            return result2;',
      '{frame:this._frame._id,object:this._objectId,result:result2,resultType:typeof result2,apiId:progress2.metadata.id}'],
    ['utility-enter', utility, utilityEnd, 'const utility = await this._frame.utilityContext();',
      '{frame:this._frame._id,object:this._objectId,states:arg?.elementStates}'],
    ['utility-context', utility, utilityEnd, 'return await utility.evaluate(pageFunction, [await utility.injectedScript(), this, arg]);',
      '{frame:this._frame._id,object:this._objectId,context:utility.delegate._contextId,world:utility.world,states:arg?.elementStates}'],
    ['utility-error', utility, utilityEnd, 'if (this._frame.isNonRetriableError(e))',
      '{frame:this._frame._id,object:this._objectId,error:String(e).slice(0,500),states:arg?.elementStates}'],
    ['cdp-evaluate-dispatch', dispatch, 'async getProperties(object)', 'const { exceptionDetails, result: remoteObject } = await this._client.send("Runtime.callFunctionOn", {',
      '{context:this._contextId,world:utilityScript._context.world,objectIds:handles.map(h=>h._objectId),matching:values.some(v=>typeof v==="string"&&v.includes("checkElementStates"))}'],
    ['cdp-evaluate-result', dispatch, 'async getProperties(object)', 'if (exceptionDetails)',
      '{context:this._contextId,world:utilityScript._context.world,error:exceptionDetails?.text,result:remoteObject,matching:values.some(v=>typeof v==="string"&&v.includes("checkElementStates"))}'],
  ];
  const points = definitions.map(([phase, start, end, needle, values]) => ({phase,
    ...uniquePoint(core, start, end, needle),
    condition: logCondition('__maraActualStabilityNode', phase, `record(${JSON.stringify(phase)},${values})`)}));
  points.push({phase: 'protocol-send', ...uniquePoint(core, '_rawSend(sessionId, method, params2) {', 'async _onMessage(message)', 'this._transport.send(message);'),
    condition: logCondition('__maraActualStabilityNode', 'protocol-send', 'sent(message)')});
  points.push({phase: 'protocol-response', ...uniquePoint(core, '_onMessage(object) {', 'async detach()', 'const callback = this._callbacks.get(object.id);'),
    condition: logCondition('__maraActualStabilityNode', 'protocol-response', 'received(this._sessionId,object)')});
  return points;
}

function stabilityGap(observation, gap) {
  if (observation.gaps.length < 32) observation.gaps.push(gap);
  else observation.droppedGaps++;
}

async function attachNodeStability(sources, observation, save) {
  if (globalThis.__maraActualStabilityNode) throw Error('Node stability observer already active');
  const session = new (require('node:inspector').Session)();
  session.connect();
  const send = (method, params = {}) => bounded(new Promise((resolve, reject) => {
    session.post(method, params, (error, result) => error ? reject(error) : resolve(result));
  }));
  const scripts = [], points = [], pending = new Set();
  let active;
  const record = (phase, data) => {
    if (!active || data.frame && data.frame !== active.frame || data.states && !data.states.includes('stable') || data.matching === false) return;
    if (phase.startsWith('utility-') && !data.states?.includes('stable')) return;
    if (observation.node.length >= 128) { observation.droppedNode++; return; }
    const encoded = JSON.stringify({phase, action: active.action, at: Date.now(), ...data});
    if (encoded.length > 6000) stabilityGap(observation, {kind: 'Node record over limit', phase});
    else observation.node.push(JSON.parse(encoded));
    save();
  };
  globalThis.__maraActualStabilityNode = {record,
    gap(phase, error) { stabilityGap(observation, {kind: 'Node condition', phase, error: error.slice(0,500)}); save(); },
    sent(message) {
      if (!active || message.method !== 'Runtime.callFunctionOn' || !message.params.arguments?.some(arg =>
        typeof arg.value === 'string' && arg.value.includes('checkElementStates'))) return;
      if (pending.size >= 128) { stabilityGap(observation, {kind: 'Pending protocol cap'}); return; }
      pending.add(message.sessionId + ':' + message.id);
      record('protocol-send', {id: message.id, session: message.sessionId,
        awaitPromise: message.params.awaitPromise, object: message.params.objectId,
        objects: message.params.arguments.filter(a => a.objectId).map(a => a.objectId),
        expression: message.params.arguments.find(a => typeof a.value === 'string' && a.value.includes('checkElementStates')).value});
    },
    received(sessionId, message) {
      if (!pending.delete(sessionId + ':' + message.id)) return;
      record('protocol-response', {id: message.id, session: sessionId, error: message.error, result: message.result});
    }};
  session.on('Debugger.scriptParsed', ({params}) => { if (params.url.endsWith('/playwright-core/lib/coreBundle.js')) scripts.push(params); });
  session.on('Debugger.paused', ({params}) => { stabilityGap(observation, {kind: 'Node paused unexpectedly', reason: params.reason}); save(); });
  try {
    await send('Debugger.enable');
    if (scripts.length !== 1) throw Error('Actual Node adapter script not unique');
    const script = scripts[0];
    const loaded = await send('Debugger.getScriptSource', {scriptId: script.scriptId});
    if (sha256(loaded.scriptSource) !== sources.coreSha256) throw Error('Loaded Node adapter differs from pinned file');
    observation.nodeScript = script;
    for (const point of nodeStabilityPoints(sources.core)) {
      const result = await send('Debugger.setBreakpoint', {location: {scriptId: script.scriptId,
        lineNumber: point.lineNumber, columnNumber: point.columnNumber}, condition: point.condition});
      points.push({...point, ...result});
      if (result.actualLocation.lineNumber !== point.lineNumber) throw Error('Node logpoint moved to another line');
    }
    observation.nodePoints = points; save();
  } catch (error) {
    delete globalThis.__maraActualStabilityNode; session.disconnect(); throw error;
  }
  return {activate(value) { active = value; }, async stop() {
    active = undefined;
    observation.pendingProtocol = [...pending];
    const cleanup = await Promise.allSettled(points.map(p => send('Debugger.removeBreakpoint', {breakpointId: p.breakpointId})));
    observation.nodeCleanup = cleanup.map((x, i) => ({phase: points[i].phase, status: x.status, error: x.status === 'rejected' ? String(x.reason) : undefined}));
    delete globalThis.__maraActualStabilityNode; session.disconnect(); save();
  }};
}

async function attachStability(page, output, options) {
  const sources = stabilitySources();
  const observation = {options, source: {file: sources.file, coreSha256: sources.coreSha256,
    injectedSha256: sources.injectedSha256}, node: [], browser: [], lifecycle: [], gaps: [],
    droppedNode: 0, droppedLifecycle: 0, droppedBrowser: 0, droppedGaps: 0, snapshots: [], points: []};
  const filename = path.join(output, `login-stability-${options.ordinal}.json`);
  const save = () => fs.writeFileSync(filename, JSON.stringify(observation, null, 2));
  save();
  const cdp = await bounded(page.context().newCDPSession(page));
  const send = (method, params = {}) => bounded(cdp.send(method, params));
  const contexts = new Map(), scripts = new Map(), listeners = [];
  const binding = '__maraActualStabilityBinding';
  let nodeObserver, selected, stopped = false;
  const on = (event, callback) => { cdp.on(event, callback); listeners.push([event, callback]); };
  const lifecycle = (event, params) => {
    if (JSON.stringify(params).length > 4000) stabilityGap(observation, {kind: 'Lifecycle record over limit', event});
    else if (observation.lifecycle.length < 128) observation.lifecycle.push({event, at: Date.now(), params});
    else observation.droppedLifecycle++;
    save();
  };
  on('Runtime.executionContextCreated', ({context}) => { contexts.set(context.id, context); lifecycle('context-created', context); });
  on('Runtime.executionContextDestroyed', params => { contexts.delete(params.executionContextId); lifecycle('context-destroyed', params); });
  on('Runtime.executionContextsCleared', params => { contexts.clear(); lifecycle('contexts-cleared', params); });
  on('Debugger.scriptParsed', script => {
    if (scripts.size < 256) scripts.set(script.scriptId, script);
    else if (!observation.gaps.some(g => g.kind === 'script-map-cap')) stabilityGap(observation, {kind: 'script-map-cap'});
  });
  on('Runtime.bindingCalled', params => {
    if (params.name !== binding) return;
    if (observation.browser.length >= 128) { observation.droppedBrowser++; return; }
    try {
      if (params.payload.length > 4000) throw Error('Binding payload over limit');
      observation.browser.push({context: params.executionContextId, receivedAt: Date.now(), ...JSON.parse(params.payload)});
    } catch (error) { stabilityGap(observation, {kind: 'binding', error: String(error).slice(0,500)}); }
    save();
  });
  for (const event of ['Page.frameAttached', 'Page.frameDetached', 'Page.frameNavigated', 'Page.lifecycleEvent',
    'Page.frameStartedLoading', 'Page.frameStoppedLoading', 'Debugger.paused', 'Debugger.resumed', 'Inspector.targetCrashed']) {
    on(event, params => lifecycle(event, params));
  }
  const evaluate = async (expression, returnByValue = true) => {
    const response = await send('Runtime.evaluate', {contextId: selected.id, expression, returnByValue, timeout: 1000});
    if (response.exceptionDetails) throw Error(response.exceptionDetails.text);
    return response.result;
  };
  const snapshot = async phase => {
    const row = {phase, at: Date.now(), contextPresent: selected && contexts.has(selected.id)};
    try {
      if (row.contextPresent) row.state = (await evaluate('globalThis.__maraActualStability?.snapshot()')).value;
      else row.gap = 'Selected context absent; streamed records retained, no continuity inferred';
    } catch (error) { row.gap = String(error); }
    observation.snapshots.push(row); save(); return row;
  };
  const stop = async () => {
    if (stopped) return;
    stopped = true;
    await snapshot('stop');
    const cleanup = await Promise.allSettled([
      ...observation.points.map(p => send('Debugger.removeBreakpoint', {breakpointId: p.breakpointId})),
      send('Runtime.removeBinding', {name: binding}),
      ...(nodeObserver ? [nodeObserver.stop()] : []),
    ]);
    observation.cleanup = cleanup.map(x => ({status: x.status, error: x.status === 'rejected' ? String(x.reason) : undefined}));
    if (selected && contexts.has(selected.id)) {
      try { await evaluate('delete globalThis.__maraActualStability; delete globalThis.__maraActualStabilityBinding;'); }
      catch (error) { stabilityGap(observation, {kind: 'owned-global-cleanup', error: String(error).slice(0,500)}); }
    }
    for (const [event, callback] of listeners) cdp.off(event, callback);
    try { await bounded(cdp.detach()); }
    catch (error) { stabilityGap(observation, {kind: 'detach', error: String(error).slice(0,500)}); }
    observation.stoppedAt = Date.now(); save();
  };
  try {
    await send('Page.enable');
    await send('Page.setLifecycleEventsEnabled', {enabled: true});
    await send('Runtime.enable');
    await send('Debugger.enable');
    observation.browserIdentity = await send('Browser.getVersion');
    nodeObserver = await attachNodeStability(sources, observation, save);
  } catch (error) {
    stabilityGap(observation, {kind: 'attach', error: String(error).slice(0,500)}); await stop(); throw error;
  }
  return {snapshot, stop, async arm() {
    try {
      const {frameTree} = await send('Page.getFrameTree');
      observation.frame = frameTree.frame;
      const candidates = [...contexts.values()].filter(c => c.auxData?.frameId === frameTree.frame.id &&
        c.name.startsWith('__playwright_utility_world_'));
      if (candidates.length !== 1) throw Error('Actual current-frame utility context not unique');
      selected = candidates[0]; observation.context = selected;
      const large = [...scripts.values()].filter(s => s.executionContextId === selected.id &&
        s.length >= sources.injected.length && s.length < sources.injected.length + 3000);
      if (large.length !== 1) throw Error('Actual loaded injected script not unique');
      const script = large[0];
      const {scriptSource} = await send('Debugger.getScriptSource', {scriptId: script.scriptId});
      const mapped = injectedStabilityPoints(scriptSource, sources.injected);
      observation.script = {...script, sha256: sha256(scriptSource), options: mapped.options};
      fs.writeFileSync(path.join(output, `login-stability-${options.ordinal}-injected.js`), scriptSource);
      await send('Runtime.addBinding', {name: binding, executionContextId: selected.id});
      const action = `Login-${options.ordinal}`;
      await evaluate(`(${installStabilityTrace.toString()})(${JSON.stringify(action)},${JSON.stringify(binding)})`);
      const target = await evaluate('globalThis.__maraActualStability.target', false);
      const {node} = await send('DOM.describeNode', {objectId: target.objectId});
      observation.target = {objectId: target.objectId, backendNodeId: node.backendNodeId, nodeName: node.nodeName, nodeId: node.nodeId};
      await send('Runtime.releaseObject', {objectId: target.objectId});
      for (const point of mapped.points) {
        const result = await send('Debugger.setBreakpoint', {location: {scriptId: script.scriptId,
          lineNumber: point.lineNumber, columnNumber: point.columnNumber}, condition: point.condition});
        observation.points.push({...point, ...result});
        if (result.actualLocation.lineNumber !== point.lineNumber) throw Error('Utility logpoint moved to another line');
      }
      observation.armedAt = Date.now();
      nodeObserver.activate({action, frame: frameTree.frame.id}); save();
    } catch (error) {
      stabilityGap(observation, {kind: 'arm', error: String(error).slice(0,500)}); await stop(); throw error;
    }
  }};
}

module.exports = {install, attach, bounded, stabilitySources, uniquePoint,
  injectedStabilityPoints, installStabilityTrace, nodeStabilityPoints, logCondition, stabilityGap, attachStability};

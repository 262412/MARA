const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {install, bounded} = require('./login_frame_observer.cjs');

function documentFixture() {
  const frames = new Map(), timers = new Map(), listeners = new Map();
  let serial = 0;
  const context = {crypto: require('node:crypto'), performance: {timeOrigin: 10, now: () => 5},
    location: {href: 'http://127.0.0.1/owned'},
    document: {readyState: 'loading', visibilityState: 'visible', hasFocus: () => true,
      querySelectorAll: () => []},
    requestAnimationFrame: callback => { frames.set(++serial, callback); return serial; },
    cancelAnimationFrame: id => frames.delete(id),
    setTimeout: (callback, delay) => { timers.set(++serial, {callback, delay}); return serial; },
    clearTimeout: id => timers.delete(id),
    addEventListener: (name, callback) => listeners.set(name, callback),
    removeEventListener: (name, callback) => { assert.equal(listeners.get(name), callback); listeners.delete(name); }};
  context.window = context;
  vm.runInNewContext(`(${install.toString()})('main')`, context);
  const probe = context.ownedLoginFrameProbe;
  return {context, frames, timers, listeners, probe,
    read: () => JSON.parse(JSON.stringify(probe.snapshot()))};
}

test('one-shot observations retain the actual APIs and do not manufacture callbacks', () => {
  const f = documentFixture();
  assert.equal(f.read().state.sameRAF, true);
  assert.equal(f.frames.size, 2);
  assert.equal(f.timers.size, 4);
  assert.equal(f.read().records.filter(r => r.kind === 'raf-callback').length, 0);
  for (const [id, callback] of f.frames) { f.frames.delete(id); callback(8); }
  assert.equal(f.read().records.filter(r => r.kind === 'raf-callback').length, 2);
  assert.equal(f.frames.size, 0, 'callbacks must not start a continuous frame loop');
  f.probe.stop();
});

test('live timers with absent frame callbacks remain absent and are explicitly cancelled', () => {
  const f = documentFixture();
  for (const [id, {callback}] of f.timers) { f.timers.delete(id); callback(); }
  assert.equal(f.read().records.filter(r => r.kind === 'timer').length, 4);
  assert.equal(f.read().records.filter(r => r.kind === 'raf-callback').length, 0);
  assert.equal(f.read().pendingRAF.length, 2);
  f.probe.stop();
  assert.equal(f.frames.size, 0);
  assert.equal(f.listeners.size, 0);
  assert.equal(f.read().records.filter(r => r.kind === 'raf-cancel').length, 2);
});

test('saved reference and current reference stay distinguishable after a simulated replacement', () => {
  const f = documentFixture();
  f.context.requestAnimationFrame = () => 99;
  f.probe.burst('before-login-click');
  assert.equal(f.read().state.sameRAF, false);
  assert.equal(f.frames.size, 3, 'only saved reference schedules the additional real callback');
  assert.ok(f.read().records.some(r => r.api === 'current' && r.id === 99));
  f.probe.stop();
});

test('new documents have distinct world tokens; records cannot imply continuity across them', () => {
  const a = documentFixture(), b = documentFixture();
  assert.notEqual(a.read().identity.worldToken, b.read().identity.worldToken);
  a.probe.stop(); b.probe.stop();
});

test('lifecycle noise is capped and truncation is explicit; cleanup releases every listener', () => {
  const f = documentFixture();
  for (let i = 0; i < 300; i++) f.listeners.get('focus')({type: 'focus'});
  assert.equal(f.read().records.length, 128);
  assert.ok(f.read().dropped > 0);
  f.probe.stop();
  assert.equal(f.timers.size, 0);
  assert.equal(f.listeners.size, 0);
});

test('a stalled page operation is bounded by Node independently of page timers', async () => {
  await assert.rejects(bounded(new Promise(() => {}), 10), /Login observation deadline/);
  assert.equal(await bounded(Promise.resolve('owned')), 'owned');
});

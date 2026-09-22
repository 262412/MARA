const assert = require('node:assert/strict');
const {test} = require('node:test');
const createSetup = require('./conversation_setup.cjs');

function fixture() {
  const framework = {errors: [], logpointsActive: true, records: [
    {sequence: 0, phase: 'installed'}, {sequence: 1, phase: 'logpoints_state', active: true},
  ]};
  const queue = []; queue.requestIds = []; queue.sessionHash = 'browser';
  const ready = {roles: {conversation_select: 10}, functions: {
    10: {name: 'select_conv', inputs: [164], outputs: [164], targets: [[164, 'select']], backend_fn: true, trigger_after: null},
    20: {name: 'last_backend', inputs: [], outputs: [], backend_fn: true, trigger_after: 10},
    30: {name: 'finish', inputs: [], outputs: [], backend_fn: false, js: 'finish()', trigger_after: 20},
  }};
  const server = [10, 20].map(fn => ({phase: 'call', fn, event_id: 'event-' + fn,
    session_hash: 'browser', username: 'actor', inputs: fn === 10 ? ['uuid-B', 'owner'] : []}));
  const page = {evaluate: async (fn, args) => fn(args), url: () => 'http://127.0.0.1:8768'};
  const expect = {poll: callback => ({toBe: async wanted => assert.equal(await callback(), wanted)})};
  const evidence = async () => ({queue_events: Object.fromEntries([10, 20].map(fn => ['event-' + fn, {status: 'success'}]))});
  return {framework, queue, ready, server, page, expect, evidence};
}

async function exercise(mutate) {
  const f = fixture(), oldWindow = global.window, oldFetch = global.fetch;
  global.window = {ownedFrameworkTrace: f.framework};
  global.fetch = async () => new Response(JSON.stringify(f.server));
  try {
    const setup = createSetup(f);
    const start = await setup.mark();
    f.queue.push(10, 20); f.queue.requestIds.push('event-10', 'event-20');
    f.framework.records.push(
      {sequence: 2, phase: 'transport', message: {msg: 'process_completed', event_id: 'event-10', success: true}},
      {sequence: 3, phase: 'transport', message: {msg: 'process_completed', event_id: 'event-20', success: true}},
      {sequence: 4, phase: 'js_schedule', fn: 30}, {sequence: 5, phase: 'js_result', fn: 30},
    );
    mutate(f);
    await setup.ended(setup.select, start);
  } finally { global.window = oldWindow; global.fetch = oldFetch; }
}
test('the current operation has a complete observed endpoint', () => exercise(() => {}));
for (const [name, mutate] of Object.entries({
  'same tail but different request': f => f.queue.requestIds[0] = 'other-event',
  'cross-session root': f => f.server[0].session_hash = 'another-session',
  'missing required backend': f => f.server.pop(),
  'observer disabled after start': f => f.framework.records.splice(2, 0, {sequence: 2, phase: 'logpoints_state', active: false}),
  'tail result before required backend transport': f => f.framework.records[3].sequence = 9,
  'multiple required branches': f => f.ready.functions[25] = {backend_fn: true, trigger_after: 10},
})) test(name + ' cannot satisfy ended', async () => {
  await assert.rejects(exercise(mutate));
});

const test = require('node:test');
const assert = require('node:assert/strict');
const {createFileBrowserRefresh} = require('../../libs/ktem/ktem/assets/js/file_browser_refresh.js');
const {assertRefreshDelivery} = require('./refresh_delivery_contract.cjs');

function fixture(coalesced = false) {
  const document = {querySelector: () => document, addEventListener() {}};
  const guard = createFileBrowserRefresh(document, () => 'owner-mount');
  const records = [], trace = [], backend = [];
  const web = (phase, rest = {}) => records.push({sequence: records.length, phase, ...rest});
  const log = (phase, rest = {}) => trace.push({sequence: trace.length, phase, ...rest});
  const payload = filter => ({stamp: guard.captureFiles(1), conversation: 'conversation-a',
    selected: [], filter, outputs: [[{id: 'owned'}], '<div>owned</div>', 'Focus: owned', '1 file']});
  const operation = (event_id, value) => ({fn: 117, event_id, session_hash: 'owner-session',
    username: 'owner', inputs: {user_id: 'owner-id', conversation: value.conversation,
      selected: value.selected, filter: value.filter, stamp: value.stamp}});
  const delivered = (op, value) => {
    for (const phase of ['call', 'return', 'postprocess']) backend.push({...op, phase,
      result: {stamp: value.stamp, ids: value.outputs[0].map(row => row.id)}});
    log('transport', {url: 'http://localhost/queue/data?session_hash=owner-session',
      message: {event_id: op.event_id, success: true, output: {data: [value]}}});
    log('handle_data', {fn: op.fn, data: [value]});
    log('handle_update', {fn: op.fn, data: [value]});
    log('queued', {updates: [{id: 31, value}]});
    log('assignment', {updates: [{id: 31, value}]});
  };
  const apply = value => {
    log('change', {detail: {id: 31, event: 'change'}});
    log('js_schedule', {fn: 116, data: [value]});
    const returned = guard.applyFiles(value, '.txt', [], 'conversation-a');
    web('applyFiles', {stamp: value.stamp, applied: returned === value.outputs, slots: returned.length,
      outputs: value.outputs, returned, ids: ['owned'], display: value.outputs.slice(2)});
    log('js_result', {fn: 116, input: [value], outputs: returned});
  };
  log('installed'); web('installed');
  web('input', {action: 'ABA-first-A', value: '.txt'}); guard.filterChanged();
  const old = payload('.txt'); web('captureFiles', {stamp: old.stamp});
  web('input', {action: 'ABA-B', value: '.png'}); guard.filterChanged();
  const middle = payload('.png');
  web('input', {action: 'ABA-last-A', value: '.txt'}); guard.filterChanged();
  const latest = payload('.txt'); web('captureFiles', {stamp: latest.stamp});
  const firstOp = operation('first-event', old), latestOp = operation('latest-event', latest);
  delivered(firstOp, old);
  if (coalesced) {
    if (coalesced === 'deferred') {
      log('flush_end', {updates: [{id: 31, value: old}]});
      log('change', {detail: {id: 31, event: 'change'}});
      log('change_schedule', {fn: 116, id: 31, scheduled: 'old-change', stamp: old.stamp});
    }
    delivered(operation('middle-event', middle), middle);
    log('flush_end', {updates: [{id: 31, value: middle}]});
    if (coalesced === 'deferred') log('change_callback', {fn: 116, id: 31, scheduled: 'old-change'});
    apply(middle);
  } else {
    log('flush_end', {updates: [{id: 31, value: old}]}); apply(old);
  }
  delivered(latestOp, latest);
  log('flush_end', {updates: [{id: 31, value: latest}]}); apply(latest);
  log('flush_end', {updates: [30, 36, 35, 37].map((id, i) => ({id, value: latest.outputs[i]}))});
  return structuredClone({records, backend, first: firstOp, latest: latestOp, observerErrors: [],
    expectedIds: ['owned'], dom: {ids: ['owned'], focus: 'Focus: owned', summary: '1 file'},
    framework: {bundleSha256: 'installed-hash', served: [{status: 'fulfilled', value: {sha256: 'installed-hash'}}],
      points: [{locations: [{lineNumber: 94}]}], resolved: [],
      state: {errors: [], records: trace, ids: {resultId: 31, applyFn: 116, components: [31, 30, 36, 35, 37]}}}});
}

test('production guard rejects actual old arrival and accepts actual latest arrival', () => {
  assert.equal(assertRefreshDelivery(fixture()).fate.kind, 'guard-rejected');
});
test('explicit same-flush replacement, change and guard evidence proves coalescing', () => {
  assert.equal(assertRefreshDelivery(fixture(true)).fate.kind, 'coalesced-in-flush');
});
test('exact deferred change callback reads a newer component value', () => {
  assert.equal(assertRefreshDelivery(fixture('deferred')).fate.kind, 'coalesced-before-js');
});

const negative = {
  'old result actually applies': value => { value.records.find(row => row.phase === 'applyFiles').applied = true; },
  'latest request completes without applying': value => { value.records.findLast(row => row.phase === 'applyFiles').applied = false; },
  'observer never installed': value => { value.records = value.records.filter(row => row.phase !== 'installed'); },
  'observer drops a real guard call': value => { value.records = value.records.filter(row => row.phase !== 'applyFiles' || row.stamp.fileRequest !== value.first.inputs.stamp.fileRequest); },
  'observer drops latest JS scheduling': value => { value.framework.state.records = value.framework.state.records.filter(row => row.phase !== 'js_schedule' || row.data[0].stamp.fileRequest !== value.latest.inputs.stamp.fileRequest); },
  'observer serialization failure': value => { value.observerErrors.push({error: 'dropped payload'}); },
  'wrong exact source IDs': value => { value.expectedIds = ['another-user-file']; },
  'three output slots': value => { value.records.findLast(row => row.phase === 'applyFiles').slots = 3; },
  'four returned outputs but no component commit': value => { value.framework.state.records.pop(); },
  'wrong Focus in final DOM': value => { value.dom.focus = 'old focus'; },
  'wrong summary in final DOM': value => { value.dom.summary = 'old summary'; },
  'different session reused': value => { value.latest.session_hash = 'other-session'; },
  'different user reused': value => { value.latest.username = 'other-user'; },
  'different conversation reused': value => { value.latest.inputs.conversation = 'other-conversation'; },
  'different mounted epoch reused': value => { value.latest.inputs.stamp.epoch = 'other-mount'; },
  'missing transport is not suppression': value => { value.framework.state.records = value.framework.state.records.filter(row => row.phase !== 'transport'); },
  'incorrect event correlation': value => { value.framework.state.records.find(row => row.phase === 'transport').message.event_id = 'unrelated-event'; },
  'unverified frontend bundle': value => { value.framework.served[0].value.sha256 = 'wrong'; },
  'logpoints never installed': value => { value.framework.points[0].locations = []; },
};
for (const [name, mutate] of Object.entries(negative)) test(name, () => {
  const value = fixture(); mutate(value);
  assert.throws(() => assertRefreshDelivery(value));
});
for (const phase of ['assignment', 'flush_end', 'change', 'js_schedule']) {
  test(`coalescing cannot be inferred without ${phase} evidence`, () => {
    const value = fixture(true);
    value.framework.state.records = value.framework.state.records.filter(row => row.phase !== phase);
    assert.throws(() => assertRefreshDelivery(value));
  });
}
for (const phase of ['change_schedule', 'change_callback', 'assignment', 'flush_end', 'js_schedule']) {
  test(`deferred coalescing requires ${phase}`, () => {
    const value = fixture('deferred');
    value.framework.state.records = value.framework.state.records.filter(row => row.phase !== phase);
    assert.throws(() => assertRefreshDelivery(value));
  });
}
test('production guard rejects a payload from a different mounted user context', () => {
  const document = {querySelector: () => document, addEventListener() {}};
  const owner = createFileBrowserRefresh(document, () => 'owner');
  const other = createFileBrowserRefresh(document, () => 'other');
  const payload = {stamp: owner.captureFiles(1), filter: '.txt', selected: [], conversation: 'a', outputs: [[], 'list', 'focus', 'summary']};
  assert.deepEqual(other.applyFiles(payload, '.txt', [], 'a'), Array.from({length: 4}, () => ({__type__: 'update'})));
  assert.equal(owner.applyFiles(payload, '.txt', [], 'a'), payload.outputs);
});
test('an unobserved old guard result cannot masquerade as component coalescing', () => {
  const value = fixture(true);
  value.framework.state.records.push({phase: 'js_result', fn: 116, input: [{stamp: value.first.inputs.stamp}], outputs: []});
  assert.throws(() => assertRefreshDelivery(value), /missing call record/);
});
test('a replacement from another session cannot prove safe coalescing', () => {
  const value = fixture(true);
  value.backend.find(row => row.event_id === 'middle-event' && row.phase === 'call').session_hash = 'foreign';
  assert.throws(() => assertRefreshDelivery(value));
});

// B1 full-App contract. The separate production-guard tests force both arrivals.
const assert = require('node:assert/strict');
const {isDeepStrictEqual: equal} = require('node:util');
const {assertLatestFilter} = require('./web_operation_observer.cjs');

const same = (payload, stamp) => equal(payload?.stamp, stamp);
const valueAt = (record, id) => record.updates?.find(item => item.id === id)?.value;

function delivery(framework, backend, operation) {
  const {records, ids} = framework.state, stamp = operation.inputs.stamp;
  const phases = ['call', 'return', 'postprocess'].map(phase => {
    const found = backend.find(row => row.event_id === operation.event_id && row.phase === phase);
    assert.ok(found, `backend ${phase} for ${operation.event_id}`);
    for (const key of ['fn', 'session_hash', 'username', 'inputs']) assert.deepEqual(found[key], operation[key]);
    return found;
  });
  const transport = records.find(row => row.phase === 'transport' && row.message.event_id === operation.event_id);
  assert.ok(transport, 'exact event must have transport evidence');
  assert.equal(new URL(transport.url).searchParams.get('session_hash'), operation.session_hash);
  assert.equal(transport.message.success, true);
  const payload = transport.message.output.data[0];
  assert.deepEqual(payload.stamp, stamp);
  for (const key of ['filter', 'conversation', 'selected']) assert.deepEqual(payload[key], operation.inputs[key]);
  assert.deepEqual(phases[1].result.stamp, stamp);
  assert.deepEqual(phases[1].result.ids, payload.outputs[0].map(row => row.id));
  assert.equal(payload.outputs.length, 4);
  const data = records.find(row => row.phase === 'handle_data' && row.fn === operation.fn && same(row.data[0], stamp));
  const update = records.find(row => row.phase === 'handle_update' && row.fn === operation.fn && same(row.data[0], stamp));
  const queued = records.find(row => row.phase === 'queued' && same(valueAt(row, ids.resultId), stamp));
  const assigned = records.find(row => row.phase === 'assignment' && same(valueAt(row, ids.resultId), stamp));
  assert.ok(data && update && queued && assigned, 'transport must reach the real intermediate component');
  assert.ok(data.sequence < update.sequence && update.sequence < queued.sequence && queued.sequence < assigned.sequence);
  assert.deepEqual(valueAt(assigned, ids.resultId), payload);
  return {payload, assigned};
}

function oldFate(framework, records, stamp, assigned) {
  const trace = framework.state.records, {resultId, applyFn} = framework.state.ids;
  const calls = trace.filter(row => row.phase === 'js_schedule' && row.fn === applyFn && same(row.data[0], stamp));
  const applications = records.filter(row => row.phase === 'applyFiles' && equal(row.stamp, stamp));
  if (calls.length) {
    assert.equal(applications.length, calls.length, 'observer must record every actual guard call');
    assert.ok(applications.every(row => row.applied === false), 'old A must be rejected');
    const returned = trace.filter(row => row.phase === 'js_result' && row.fn === applyFn && same(row.input[0], stamp));
    assert.equal(returned.length, calls.length);
    assert.ok(returned.every(row => equal(row.outputs, Array.from({length: 4}, () => ({__type__: 'update'})))));
    return {kind: 'guard-rejected', calls: calls.map(row => row.sequence)};
  }
  assert.equal(applications.length, 0, 'guard and framework observers must agree');
  assert.ok(!trace.some(row => row.phase === 'js_result' && row.fn === applyFn && same(row.input[0], stamp)),
    'a missing call record cannot hide a real guard result');
  const flush = trace.find(row => row.phase === 'flush_end' && row.sequence > assigned.sequence);
  assert.ok(flush, 'assignment needs a completed flush');
  const replacement = trace.findLast(row => row.phase === 'assignment' && row.sequence > assigned.sequence &&
    row.sequence < flush.sequence && valueAt(row, resultId)?.stamp);
  if (!replacement) return deferredChangeFate(trace, records, stamp, flush, resultId, applyFn);
  const payload = valueAt(replacement, resultId);
  assert.equal(payload.stamp.epoch, stamp.epoch);
  assert.ok(payload.stamp.filterVersion > stamp.filterVersion && payload.stamp.fileRequest > stamp.fileRequest);
  assert.deepEqual(valueAt(flush, resultId), payload);
  const change = trace.find(row => row.phase === 'change' && row.sequence > flush.sequence && row.detail.id === resultId);
  const scheduled = trace.find(row => row.phase === 'js_schedule' && row.fn === applyFn &&
    row.sequence > change?.sequence && same(row.data[0], payload.stamp));
  assert.ok(change && scheduled, 'replacement must dispatch change and reach production JS');
  assert.ok(records.some(row => row.phase === 'applyFiles' && equal(row.stamp, payload.stamp)), 'replacement guard observation required');
  return {kind: 'coalesced-in-flush', assigned: assigned.sequence, replacement: replacement.sequence,
    flush: flush.sequence, change: change.sequence, scheduled: scheduled.sequence, replacementStamp: payload.stamp};
}

function deferredChangeFate(trace, records, stamp, flush, resultId, applyFn) {
  assert.ok(same(valueAt(flush, resultId), stamp), 'old component must be flushed before deferred change');
  const schedule = trace.find(row => row.phase === 'change_schedule' && row.fn === applyFn &&
    row.sequence > flush.sequence && equal(row.stamp, stamp));
  assert.ok(schedule, 'missing guard log alone is not coalescing evidence');
  const callback = trace.find(row => row.phase === 'change_callback' && row.scheduled === schedule.scheduled);
  assert.ok(callback && callback.sequence > schedule.sequence, 'exact deferred change callback required');
  const replacement = trace.findLast(row => row.phase === 'assignment' && row.sequence > schedule.sequence &&
    row.sequence < callback.sequence && valueAt(row, resultId)?.stamp);
  assert.ok(replacement, 'replacement must precede the actual deferred callback');
  const payload = valueAt(replacement, resultId);
  assert.equal(payload.stamp.epoch, stamp.epoch);
  assert.ok(payload.stamp.filterVersion > stamp.filterVersion && payload.stamp.fileRequest > stamp.fileRequest);
  const replacementFlush = trace.find(row => row.phase === 'flush_end' && row.sequence > replacement.sequence &&
    row.sequence < callback.sequence && equal(valueAt(row, resultId), payload));
  const scheduled = trace.find(row => row.phase === 'js_schedule' && row.fn === applyFn &&
    row.sequence > callback.sequence && same(row.data[0], payload.stamp));
  assert.ok(replacementFlush && scheduled, 'deferred JS must read the replacement component value');
  assert.ok(records.some(row => row.phase === 'applyFiles' && equal(row.stamp, payload.stamp)));
  return {kind: 'coalesced-before-js', flush: flush.sequence, scheduledChange: schedule.sequence,
    callback: callback.sequence, replacement: replacement.sequence, replacementFlush: replacementFlush.sequence,
    scheduled: scheduled.sequence, replacementStamp: payload.stamp};
}

function assertRefreshDelivery({framework, backend, records, observerErrors, first, latest, expectedIds, dom}) {
  assert.deepEqual(observerErrors, [], 'guard observer must be healthy');
  assert.deepEqual(framework.state.errors, [], 'framework observer must be healthy');
  assert.equal(framework.state.records[0].phase, 'installed');
  assert.ok(framework.served.length && framework.served.every(row => row.status === 'fulfilled' && row.value.sha256 === framework.bundleSha256));
  assert.ok(framework.points.every(point => point.locations.length || framework.resolved.some(row => row.breakpointId === point.breakpointId)));
  const firstInput = records.find(row => row.phase === 'input' && row.action === 'ABA-first-A');
  assert.ok(firstInput && records.some(row => row.phase === 'installed' && row.sequence < firstInput.sequence), 'guard observer installed before input');
  for (const [operation, action] of [[first, 'ABA-first-A'], [latest, 'ABA-last-A']]) {
    const input = records.find(row => row.phase === 'input' && row.action === action);
    const capture = records.find(row => row.phase === 'captureFiles' && equal(row.stamp, operation.inputs.stamp));
    assert.ok(input && capture && capture.sequence > input.sequence, 'exact input to stamp correlation');
    assert.equal(input.value, operation.inputs.filter);
  }
  for (const key of ['fn', 'session_hash', 'username']) assert.equal(first[key], latest[key]);
  for (const key of ['user_id', 'conversation', 'selected']) assert.deepEqual(first.inputs[key], latest.inputs[key]);
  assert.equal(first.inputs.stamp.epoch, latest.inputs.stamp.epoch);
  assert.notEqual(first.event_id, latest.event_id);
  const oldDelivery = delivery(framework, backend, first);
  const newDelivery = delivery(framework, backend, latest);
  const fate = oldFate(framework, records, first.inputs.stamp, oldDelivery.assigned);
  if (fate.replacementStamp) {
    const replacement = backend.find(row => row.phase === 'call' && equal(row.inputs?.stamp, fate.replacementStamp));
    assert.ok(replacement, 'coalescing replacement needs its own exact backend event');
    for (const key of ['session_hash', 'username']) assert.equal(replacement[key], first[key]);
    for (const key of ['user_id', 'conversation', 'selected']) assert.deepEqual(replacement.inputs[key], first.inputs[key]);
    delivery(framework, backend, replacement);
    fate.replacementEvent = replacement.event_id;
    fate.replacementFn = replacement.fn;
  }
  const applied = assertLatestFilter(records, first.inputs.stamp, latest.inputs.stamp, true, fate.kind.startsWith('coalesced-'));
  assert.deepEqual(applied.stamp, latest.inputs.stamp);
  assert.deepEqual(applied.outputs, newDelivery.payload.outputs);
  assert.deepEqual(applied.returned, newDelivery.payload.outputs);
  assert.deepEqual([...applied.ids].sort(), [...expectedIds].sort(), 'exact authorized IDs');
  const {applyFn, components} = framework.state.ids;
  assert.equal(components.length, 5);
  const returned = framework.state.records.find(row => row.phase === 'js_result' && row.fn === applyFn && same(row.input[0], latest.inputs.stamp));
  assert.ok(returned, 'latest must return through the actual JS scheduler');
  assert.ok(framework.state.records.some(row => row.phase === 'js_schedule' && row.fn === applyFn &&
    row.sequence < returned.sequence && same(row.data[0], latest.inputs.stamp)), 'latest JS scheduling must be observed');
  assert.deepEqual(returned.outputs, newDelivery.payload.outputs);
  assert.ok(framework.state.records.some(row => row.phase === 'flush_end' && row.sequence > returned.sequence &&
    components.slice(1).every((id, i) => equal(valueAt(row, id), returned.outputs[i]))), 'all four component values must actually apply');
  assert.deepEqual([...dom.ids].sort(), [...expectedIds].sort());
  assert.equal(dom.focus.trim(), applied.display[0]);
  assert.equal(dom.summary.trim(), applied.display[1]);
  return {fate, applied};
}

module.exports = {assertRefreshDelivery};

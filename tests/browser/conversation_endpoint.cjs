// A linear registered operation needs its own requests and its final JS result.
const assert = require('node:assert/strict');

function chainFor(functions, root) {
  const chain = [], seen = new Set();
  let id = root;
  while (id != null) {
    assert.ok(!seen.has(id), 'conversation chain cycle'); seen.add(id);
    const fn = functions[id]; assert.ok(fn, 'missing registered function');
    chain.push({...fn, id: Number(id)});
    const children = Object.entries(functions).filter(([, child]) => child.trigger_after === Number(id));
    assert.ok(children.length <= 1, 'multiple required conversation successors');
    id = children.length ? Number(children[0][0]) : null;
  }
  assert.ok(chain.at(-1).js && !chain.at(-1).backend_fn, 'endpoint must be the registered JS tail');
  return chain;
}

function endpoint({chain, framework, queue, server, statuses, start, session, conversation, allowFailure = []}) {
  const missing = reason => ({complete: false, reason});
  if (framework.errors.length || !framework.records.some(row => row.phase === 'installed')) return missing('observer missing or errored');
  const windows = framework.records.filter(row => row.phase === 'logpoints_state');
  if (windows.findLast(row => row.sequence < start)?.active === false ||
      windows.some(row => row.sequence >= start && !row.active) || !framework.logpointsActive) return missing('observer inactive in operation window');
  let previous = start - 1, actor;
  const requests = [];
  for (const fn of chain.filter(row => row.backend_fn)) {
    const submitted = queue.filter(row => row.fn === fn.id);
    if (submitted.length !== 1 || !submitted[0].eventId) return missing('expected exactly one request for fn ' + fn.id);
    const event = submitted[0].eventId;
    const call = server.find(row => row.phase === 'call' && row.event_id === event && row.fn === fn.id);
    if (!call || call.session_hash !== session) return missing('request/session mismatch for fn ' + fn.id);
    actor ||= call.username;
    if (call.username !== actor) return missing('actor changed inside operation');
    if (fn.id === chain[0].id && fn.name === 'select_conv' && conversation && call.inputs[0] !== conversation) return missing('wrong conversation UUID');
    const deliveries = framework.records.filter(row => row.phase === 'transport' && row.message.msg === 'process_completed' && row.message.event_id === event);
    if (deliveries.length !== 1 || deliveries[0].sequence <= previous) return missing('missing or out-of-order transport for fn ' + fn.id);
    const delivery = deliveries[0];
    const failed = !delivery.message.success;
    if (failed !== allowFailure.includes(fn.id)) return missing('unexpected backend outcome for fn ' + fn.id);
    if (statuses[event]?.status !== (failed ? 'failed' : 'success')) return missing('request not terminal for fn ' + fn.id);
    requests.push({fn: fn.id, event, session, actor, transportSequence: delivery.sequence, failed});
    previous = delivery.sequence;
  }
  const tail = chain.at(-1).id;
  const schedules = framework.records.filter(row => row.phase === 'js_schedule' && row.fn === tail && row.sequence > previous);
  if (schedules.length !== 1) return missing('missing or ambiguous final JS scheduling');
  const results = framework.records.filter(row => row.phase === 'js_result' && row.fn === tail && row.sequence > schedules[0].sequence);
  if (results.length !== 1) return missing('missing or ambiguous final JS result');
  return {complete: true, root: chain[0].id, tail, start, requests,
    jsSchedule: schedules[0].sequence, jsResult: results[0].sequence, time: results[0].time};
}
module.exports = {chainFor, endpoint};

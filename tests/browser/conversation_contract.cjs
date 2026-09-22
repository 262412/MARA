const assert = require('node:assert/strict');

function assertSelection(proof) {
  const {expected, session, selectFn, dropdownId, queue, server, framework, web, dom, start} = proof;
  assert.equal(expected.user, proof.user, 'private conversation owner must match authenticated actor');
  assert.ok(expected.id && session);
  assert.ok(proof.gesture?.trusted && proof.gesture.phase === 'pointerdown', 'selection must be a real mouse gesture');
  const options = proof.gesture.dom.options.filter(row => row.name === expected.name && row.connected);
  assert.equal(options.length, 1, 'exactly one live option must match');
  assert.equal(proof.gesture.option.node, options[0].node);
  assert.deepEqual(framework.errors, []);
  assert.ok(framework.records.some(row => row.phase === 'installed'), 'framework observer must be installed');
  const logpointStates = framework.records.filter(row => row.phase === 'logpoints_state');
  assert.equal(logpointStates.findLast(row => row.sequence < start)?.active, true,
    'logpoints must be active before the critical mouse action');
  assert.ok(logpointStates.filter(row => row.sequence >= start).every(row => row.active),
    'logpoints must remain active throughout the critical action');
  assert.ok(web.records.some(row => row.phase === 'installed'), 'production guard observer must be installed');
  assert.deepEqual(web.errors, []);
  const restored = server.findLast(row => row.phase === 'return' && row.fn === selectFn &&
    row.session_hash === session && row.username === proof.username && row.inputs[0] === expected.id);
  assert.ok(restored, 'authorized backend restore must return the exact conversation UUID');
  assert.equal(restored.inputs[1], proof.user);
  assert.equal(restored.result[0], expected.id);
  assert.equal(restored.result[1], expected.id);
  assert.deepEqual(restored.result[3], expected.messages);
  assert.deepEqual(restored.result[proof.sourceIndex], expected.sources);
  assert.ok(queue.some(row => row.fn === selectFn && row.eventId === restored.event_id), 'restore must belong to this mouse action');
  const post = server.find(row => row.phase === 'postprocess' && row.event_id === restored.event_id);
  assert.ok(post, 'backend completion must be postprocessed');
  const transport = framework.records.find(row => row.phase === 'transport' &&
    row.message.event_id === restored.event_id && row.message.msg === 'process_completed');
  assert.ok(transport?.message.success, 'the same request must reach browser transport');
  assert.deepEqual(transport.message.output.data, post.data);
  const handled = framework.records.find(row => row.sequence >= start && row.phase === 'handle_data' && row.fn === selectFn);
  assert.ok(handled, 'the selection result must reach the component update path');
  assert.deepEqual(handled.data, post.data);
  assert.ok(framework.records.some(row => row.sequence > handled.sequence && row.phase === 'flush_end' &&
    row.updates.some(update => update.id === dropdownId && update.prop === 'value' && update.value === expected.id)),
  'the exact UUID must be applied, not only returned');
  const files = web.records.findLast(row => row.phase === 'applyFiles' && row.applied);
  assert.ok(files, 'latest source result must actually apply');
  assert.equal(files.args[2], expected.id, 'same-file conversations must not share ownership');
  assert.deepEqual(files.args[1], expected.sources);
  assert.equal(files.slots, 4); assert.equal(files.outputs.length, 4);
  assert.deepEqual(files.returned, files.outputs);
  assert.deepEqual([...dom.ids].sort(), files.outputs[0].map(row => row.id).sort(), 'exact authorized file IDs');
  assert.deepEqual(dom.ids, proof.renderedIds, 'DOM order must match the returned file HTML');
  assert.deepEqual(dom.selected, expected.sources);
  assert.equal(dom.focus.trim(), files.display[0]);
  assert.equal(dom.summary.trim(), files.display[1]);
  assert.ok(dom.focus.includes(expected.filename));
  assert.equal(dom.conversation, expected.name);
  assert.ok(dom.answer.includes(expected.messages.at(-1)[0]));
  assert.ok(dom.answer.includes(expected.messages.at(-1)[1]));
  const citation = server.findLast(row => row.phase === 'return' && row.fn === proof.citationFn &&
    row.session_hash === session && row.username === proof.username);
  assert.ok(citation && queue.some(row => row.eventId === citation.event_id && row.fn === proof.citationFn));
  assert.deepEqual(citation.inputs[0], expected.retrievalMessages);
  assert.equal(dom.citations.trim(), proof.citationsText.trim());
  return {eventId: restored.event_id, conversation: expected.id, session,
    fileStamp: files.stamp, ids: dom.ids, sources: dom.selected};
}

function assertOldRefreshRejected(proof, stamp) {
  assertSelection(proof);
  const old = proof.web.records.filter(row => row.phase === 'applyFiles' &&
    row.stamp?.epoch === stamp.epoch && row.stamp?.fileRequest === stamp.fileRequest);
  assert.ok(old.length, 'observe the held old result at the real production guard');
  assert.ok(old.every(row => !row.applied), 'old conversation result must not apply');
}

module.exports = {assertSelection, assertOldRefreshRejected};

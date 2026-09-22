const assert = require('node:assert/strict');
const {test} = require('node:test');
const {assertOldRefreshRejected} = require('./conversation_contract.cjs');
function fixture() {
  const data = [null, 'uuid-B', 'B', [['question B', 'answer B']]];
  const outputs = [[{id: 'same-file'}], '<files>', '<focus>', '<summary>'];
  const stamp = {epoch: 'page', fileRequest: 5};
  return {expected: {id: 'uuid-B', user: 'owner', name: 'B', messages: data[3], sources: ['same-file'], retrievalMessages: ['B evidence'], filename: 'exact.txt'},
    gesture: {trusted: true, phase: 'pointerdown', option: {node: 3}, dom: {options: [{name: 'B', node: 3, connected: true}]}},
    user: 'owner', username: 'actor', session: 'browser', selectFn: 64, dropdownId: 164, sourceIndex: 4, start: 2, citationFn: 81, citationsText: 'exact.txt',
    queue: [{fn: 64, eventId: 'request-B'}, {fn: 81, eventId: 'citations-B'}], server: [
      {phase: 'return', fn: 64, session_hash: 'browser', username: 'actor', event_id: 'request-B',
        inputs: ['uuid-B', 'owner'], result: ['uuid-B', 'uuid-B', 'B', data[3], ['same-file']]},
      {phase: 'postprocess', event_id: 'request-B', data},
      {phase: 'return', fn: 81, session_hash: 'browser', username: 'actor', event_id: 'citations-B', inputs: [['B evidence']]}],
    framework: {errors: [], records: [{phase: 'installed'},
      {phase: 'transport', message: {msg: 'process_completed', event_id: 'request-B', success: true, output: {data}}},
      {phase: 'handle_data', sequence: 2, fn: 64, data},
      {phase: 'flush_end', sequence: 3, updates: [{id: 164, prop: 'value', value: 'uuid-B'}]}]},
    web: {errors: [], records: [{phase: 'installed'},
      {phase: 'applyFiles', applied: false, stamp: {epoch: 'page', fileRequest: 4}},
      {phase: 'applyFiles', applied: true, slots: 4, args: ['', ['same-file'], 'uuid-B'],
        outputs, returned: outputs, display: ['exact.txt', 'summary'], stamp}]},
    dom: {ids: ['same-file'], selected: ['same-file'], focus: 'exact.txt', summary: 'summary',
      conversation: 'B', answer: 'question B answer B', citations: 'exact.txt'}};
}
test('complete request, application and exact UUID proof passes', () => {
  assertOldRefreshRejected(fixture(), {epoch: 'page', fileRequest: 4});
});
const negatives = {
  'missing option': p => p.gesture.dom.options = [],
  'duplicate label': p => p.gesture.dom.options.push({...p.gesture.dom.options[0]}),
  'untrusted synthetic selection': p => p.gesture.trusted = false,
  'missing authorized callback': p => p.server.shift(),
  'wrong UUID even with the same file': p => p.web.records.at(-1).args[2] = 'uuid-A',
  'private owner mismatch': p => p.expected.user = 'another-owner',
  'cross-session result': p => p.server[0].session_hash = 'another-browser',
  'different request event': p => p.queue[0].eventId = 'old-event',
  'completed but not applied': p => p.framework.records.pop(),
  'only the input label changed': p => p.framework.records[3].updates[0].value = 'uuid-A',
  'missing observer': p => p.web.records.shift(),
  'observer lost records': p => p.framework.errors.push('missed'),
  'three output slots': p => p.web.records.at(-1).slots = 3,
  'wrong source IDs': p => p.dom.selected = ['wrong'],
  'old restored messages': p => p.dom.answer = 'question A answer A',
  'wrong citation owner content': p => p.server[2].inputs = [['A evidence']],
  'wrong citation application': p => p.dom.citations = 'A evidence',
  'missing transport': p => p.framework.records.splice(1, 1),
  'old result applied': p => p.web.records[1].applied = true,
};
for (const [name, mutate] of Object.entries(negatives)) test(name + ' is rejected', () => {
  const proof = fixture(); mutate(proof);
  assert.throws(() => assertOldRefreshRejected(proof, {epoch: 'page', fileRequest: 4}));
});

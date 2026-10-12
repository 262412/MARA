const {test} = require('node:test');
const assert = require('node:assert/strict');
const {cleanup} = require('./browser_exit.cjs');

test('release, snapshot and close failures do not block later cleanup or replace the assertion', async () => {
  const results = {currentFailure: {error: 'original assertion'}}, attempted = [];
  await cleanup(results, ['release', 'snapshot', 'context', 'browser'].map(stage => [stage, () => {
    attempted.push(stage); if (stage !== 'browser') throw Error(stage);
  }]));
  assert.deepEqual(attempted, ['release', 'snapshot', 'context', 'browser']);
  assert.equal(results.currentFailure.error, 'original assertion');
  assert.equal(results.cleanupErrors.length, 3);
});
test('an auxiliary request that never responds is bounded and close still runs', async () => {
  const results = {}; let closed = false;
  await cleanup(results, [['request', () => new Promise(() => {})], ['close', () => closed = true]], 10);
  assert.equal(closed, true);
  assert.match(results.cleanupErrors[0].error, /deadline: request/);
});

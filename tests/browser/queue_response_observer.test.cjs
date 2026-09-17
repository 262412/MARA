const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, 'chat_submission.cjs'), 'utf8');
const start = source.indexOf("  page.on('response', async response => {");
const end = source.indexOf('  await page.route(', start);
assert.ok(start > 0 && end > start);
const registration = source.slice(start, end);
const missing = 'response.json: Protocol error (Network.getResponseBody): No resource with given identifier found';

function fixture({closed = false, navigation = 0, index = 0, error, pathname = '/queue/join', ok = true} = {}) {
  const request = {};
  const queue = [];
  queue.requestOrder = new WeakMap();
  queue.requestSessions = new WeakMap([[request, 'owned-session']]);
  if (index !== undefined) queue.requestOrder.set(request, index);
  queue.requestIds = [];
  queue.sessionHash = 'owned-session';
  queue.navigationStart = navigation;
  const results = {errors: []};
  let callback;
  let reads = 0;
  vm.runInNewContext(registration, {
    URL, Date, queue, results,
    page: {on: (_event, fn) => { callback = fn; }, isClosed: () => closed},
  });
  const response = {
    url: () => 'http://127.0.0.1:8768' + pathname,
    ok: () => ok,
    request: () => request,
    json: async () => {
      reads++;
      if (error) throw new Error(error);
      return {event_id: 'owned-event'};
    },
  };
  return {queue, results, response, observe: () => callback(response), reads: () => reads};
}

test('current successful response retains its original request index', async () => {
  const f = fixture({index: 2});
  await f.observe();
  assert.equal(f.queue.requestIds[2], 'owned-event');
  assert.deepEqual(f.results.errors, []);
  assert.equal(f.reads(), 1);
});

test('only a known response from a replaced document may lose its CDP body', async () => {
  const f = fixture({navigation: 1, error: missing});
  f.queue.sessionHash = 'new-document-session';
  await f.observe();
  assert.deepEqual(f.results.errors, []);
  const observation = f.results.observerClosures[0];
  assert.equal(observation.documentReplaced, true);
  assert.equal(observation.pageClosed, false);
  assert.equal(observation.requestIndex, 0);
  assert.equal(observation.navigationStart, 1);
  assert.equal(observation.url, 'http://127.0.0.1:8768/queue/join');
  assert.equal(observation.sessionHash, 'owned-session');
  assert.equal(typeof observation.at, 'string');
  assert.deepEqual(f.queue.requestIds, []);
});

test('navigation while the body is pending is checked at failure time', async () => {
  const f = fixture();
  let reject;
  f.response.json = () => new Promise((_resolve, failed) => { reject = failed; });
  const observation = f.observe();
  f.queue.navigationStart = 1;
  reject(new Error(missing));
  await observation;
  assert.deepEqual(f.results.errors, []);
  assert.equal(f.results.observerClosures[0].documentReplaced, true);
});

for (const [name, options] of [
  ['current document', {error: missing}],
  ['unknown request', {navigation: 1, index: undefined, error: missing}],
  ['other parser failure in an old document', {navigation: 1, error: 'invalid JSON'}],
  ['unproven missing body on a closed page', {closed: true, error: missing}],
]) {
  test(name + ' remains a strict global observer failure', async () => {
    const f = fixture(options);
    if (name === 'unknown request') f.queue.requestOrder = new WeakMap();
    await f.observe();
    assert.deepEqual(f.results.errors, ['Error: ' + options.error]);
    assert.equal(f.results.observerClosures, undefined);
    assert.equal(f.results.observerFailures[0].error, 'Error: ' + options.error);
  });
}

test('the existing exact closed-page exception stays separately recorded', async () => {
  const f = fixture({closed: true, error: 'response.json: Target page, context or browser has been closed'});
  await f.observe();
  assert.deepEqual(f.results.errors, []);
  assert.equal(f.results.observerClosures[0].pageClosed, true);
});

for (const options of [{pathname: '/other'}, {ok: false}]) {
  test('nonmatching responses retain the original no-read behavior ' + JSON.stringify(options), async () => {
    const f = fixture(options);
    await f.observe();
    assert.equal(f.reads(), 0);
    assert.deepEqual(f.results.errors, []);
  });
}

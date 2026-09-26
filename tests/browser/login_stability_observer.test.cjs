const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {uniquePoint, logCondition, installStabilityTrace, injectedStabilityPoints, stabilityGap} = require('./login_frame_observer.cjs');

test('scoped logpoints reject missing, duplicate and out-of-scope locations', () => {
  const source = 'needle\nbegin\n  needle();\nend\nneedle';
  assert.deepEqual(uniquePoint(source, 'begin', 'end', 'needle'), {lineNumber: 2, columnNumber: 2});
  assert.throws(() => uniquePoint('begin needle needle end', 'begin', 'end', 'needle'), /Nonunique/);
  assert.throws(() => uniquePoint('needle begin end', 'begin', 'end', 'needle'), /Nonunique/);
  assert.throws(() => uniquePoint(source, 'missing', 'end', 'needle'), /scope/);
});

test('a logpoint never pauses or changes the observed result and reports scope errors', () => {
  const records = [], gaps = [];
  const context = {__owned: {record: (...args) => records.push(args), gap: (...args) => gaps.push(args)},
    success: true, fulfill() { throw Error('Observer must not resolve the real Promise'); },
    requestAnimationFrame() { throw Error('Observer must not request a frame'); }};
  assert.equal(vm.runInNewContext(logCondition('__owned', 'resolve', 'record("resolve",{success})'), context), false);
  assert.equal(context.success, true);
  assert.equal(records[0][0], 'resolve');
  assert.equal(vm.runInNewContext(logCondition('__owned', 'wrong-scope', 'record(absentLocal)'), context), false);
  assert.equal(gaps[0][0], 'wrong-scope');
  assert.match(gaps[0][1], /absentLocal/);
  assert.equal(vm.runInNewContext(logCondition('__absent', 'missing-observer', 'record("none")'), context), false);
  assert.equal(records.length, 1, 'absence is not a fabricated hit');
});

function traceFixture() {
  const sent = [], target = {textContent: ' Login'}, other = {textContent: 'Other'};
  const document = {querySelectorAll: () => [target]};
  target.ownerDocument = document;
  const raf = () => { throw Error('No additional frame request permitted'); };
  const timer = () => { throw Error('No page timer permitted'); };
  const context = {document, location: {href: 'http://127.0.0.1:8768/'},
    performance: {timeOrigin: 100, now: () => 2}, requestAnimationFrame: raf,
    setTimeout: timer, __binding: data => sent.push(JSON.parse(data))};
  vm.runInNewContext(`(${installStabilityTrace.toString()})('owned-action','__binding')`, context);
  return {sent, target, other, document, context, raf, timer, trace: context.__maraActualStability};
}

test('actual-call observer records only the identified node and never drives frames or timers', () => {
  const f = traceFixture();
  f.trace.record('raf-first', f.other, {});
  assert.equal(f.sent.length, 1);
  f.trace.record('raf-first', f.target, {required: 1});
  assert.deepEqual(f.sent.map(r => r.phase), ['installed', 'raf-first']);
  assert.ok(!f.sent.some(r => r.phase === 'raf-enter'), 'registration does not imply callback entry');
  assert.equal(f.context.requestAnimationFrame, f.raf);
  assert.equal(f.context.setTimeout, f.timer);
});

test('binding failure and truncation are explicit observation gaps', () => {
  const f = traceFixture();
  f.context.__binding = () => { throw Error('Lost binding'); };
  f.trace.record('raf-enter', f.target, {});
  assert.equal(f.trace.snapshot().errors, 1);
  for (let i = 0; i < 200; i++) f.trace.record('rect', f.target, {rect: {x: i}});
  assert.equal(f.trace.snapshot().records.length, 128);
  assert.ok(f.trace.snapshot().dropped > 0);
  assert.equal(f.sent.length, 1, 'lost delivery must not be treated as observed callbacks');
});

test('a condition error retains its error phase and cannot impersonate the observed boundary', () => {
  const f = traceFixture();
  f.trace.gap('resolve', 'owned missing local');
  const row = f.sent.at(-1);
  assert.equal(row.phase, 'condition-error');
  assert.equal(row.failedPhase, 'resolve');
  assert.equal(row.error, 'owned missing local');
  assert.ok(!f.sent.some(item => item.phase === 'resolve'));
});

test('document replacement is preserved in records rather than assumed continuous', () => {
  const f = traceFixture();
  f.target.ownerDocument = {};
  f.trace.record('check-result', f.target, {success: true});
  assert.equal(f.sent.at(-1).sameDocument, false);
  const replacement = traceFixture();
  assert.notEqual(replacement.trace.target, f.trace.target);
});

test('unknown loaded source and a main-world wrapper cannot receive utility logpoints', () => {
  assert.throws(() => injectedStabilityPoints('unknown', 'pinned'), /source mismatch/);
  const source = '(() => {const module = {};pinned return new (module.exports.InjectedScript())(globalThis, {"isUtilityWorld":false});})();';
  assert.throws(() => injectedStabilityPoints(source, 'pinned'), /utility injection wrapper/);
  assert.throws(() => injectedStabilityPoints(source.replace('false', 'true'), 'other'), /source mismatch/);
});

test('repeated observation failures retain a bounded gap count instead of unbounded records', () => {
  const observation = {gaps: [], droppedGaps: 0};
  for (let i = 0; i < 200; i++) stabilityGap(observation, {kind: 'condition error', sequence: i});
  assert.equal(observation.gaps.length, 32);
  assert.equal(observation.droppedGaps, 168);
  assert.equal(observation.gaps[0].sequence, 0);
});

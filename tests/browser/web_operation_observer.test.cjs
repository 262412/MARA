const test = require('node:test');
const assert = require('node:assert/strict');
const {assertLatestFilter} = require('./web_operation_observer.cjs');
const first = {epoch: 'mount', filterVersion: 1, fileRequest: 3};
const latest = {epoch: 'mount', filterVersion: 3, fileRequest: 6};
const records = () => [
  {sequence: 1, phase: 'applyFiles', stamp: {...first, fileRequest: 4}, applied: true},
  {sequence: 2, phase: 'input', action: 'ABA-last-A'},
  {sequence: 3, phase: 'applyFiles', stamp: first, applied: false},
  {sequence: 4, phase: 'applyFiles', stamp: latest, applied: true, slots: 4},
];
test('legal first A before later input does not count as stale application', () => {
  assert.equal(assertLatestFilter(records(), first, latest, true).stamp, latest);
});
test('same filter text never permits old A after last input', () => {
  const values = records(); values[2].applied = true;
  assert.throws(() => assertLatestFilter(values, first, latest, true), /old A must be rejected/);
});
test('request completion without latest UI application fails', () => {
  const values = records(); values[3].applied = false;
  assert.throws(() => assertLatestFilter(values, first, latest, true), /last A must successfully apply/);
});
test('three display slots cannot stand in for the four-slot contract', () => {
  const values = records(); values[3].slots = 3;
  assert.throws(() => assertLatestFilter(values, first, latest, true));
});

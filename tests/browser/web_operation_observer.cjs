// Read-only observation of the real callbacks and their actual DOM application.
function install() {
  const records = [];
  window.ownedWebOperations = records;
  window.ownedWebAction = 'initialization';
  const copy = value => JSON.parse(JSON.stringify(value));
  const snapshot = () => ({
    filter: document.querySelector('#chat-file-filter textarea, #chat-file-filter input')?.value,
    ids: [...document.querySelectorAll('#chat-file-list [data-chat-file-id]')].map(node => node.dataset.chatFileId),
    focus: document.querySelector('#chat-selected-file')?.textContent,
    summary: document.querySelector('#workbench-file-summary')?.textContent,
  });
  const record = (phase, values) => records.push({sequence: records.length, action: window.ownedWebAction, phase, ...copy(values)});
  const observe = () => {
    const guard = window.maraFileBrowserRefresh;
    if (guard && !guard.ownedObserved) {
      guard.ownedObserved = true;
      for (const name of ['captureFiles', 'captureSelector']) {
        const original = guard[name];
        guard[name] = function (...args) {
          const result = original(...args);
          record(name, {args, stamp: result, dom: snapshot()});
          return result;
        };
      }
      const original = guard.applyFiles;
      guard.applyFiles = function (payload, ...args) {
        const result = original(payload, ...args);
        const text = html => {
          const element = document.createElement('div');
          element.innerHTML = html;
          return element.textContent.trim();
        };
        record('applyFiles', {stamp: payload?.stamp, filter: payload?.filter,
          ids: payload?.outputs?.[0]?.map(row => row.id), args,
          display: payload?.outputs?.slice(2).map(text),
          applied: result === payload?.outputs, slots: result.length, dom: snapshot()});
        return result;
      };
    }
  };
  let last = '';
  new MutationObserver(() => {
    observe();
    const dom = snapshot(), serialized = JSON.stringify(dom);
    if (serialized !== last) { last = serialized; record('dom', {dom}); }
  }).observe(document, {childList: true, subtree: true, attributes: true, characterData: true});
  document.addEventListener('input', event => {
    if (event.target.closest?.('#chat-file-filter')) record('input', {value: event.target.value, dom: snapshot()});
  }, true);
}

function assertLatestFilter(records, first, latest, complete) {
  const assert = require('node:assert/strict');
  const lastInput = records.findLast(item => item.phase === 'input' && item.action === 'ABA-last-A');
  assert.ok(lastInput, 'last A must have a distinct real input event');
  assert.ok(latest.filterVersion > first.filterVersion);
  const applications = records.filter(item => item.phase === 'applyFiles' && item.sequence > lastInput.sequence);
  const old = applications.find(item => item.stamp.fileRequest === first.fileRequest && item.stamp.epoch === first.epoch);
  assert.ok(old, 'observe old A at the actual apply boundary');
  assert.equal(old.applied, false, 'old A must be rejected after last A was issued');
  assert.deepEqual(applications.filter(item => item.applied && item.stamp.filterVersion < latest.filterVersion), [], 'no obsolete filter may apply');
  if (complete) {
    const applied = applications.find(item => item.stamp.fileRequest === latest.fileRequest && item.applied);
    assert.ok(applied, 'last A must successfully apply, not merely complete its request');
    assert.equal(applied.slots, 4);
    return applied;
  }
}

module.exports = {install, assertLatestFilter};

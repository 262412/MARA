// Read-only observation of the real callbacks and their actual DOM application.
function install() {
  const records = [];
  window.ownedWebOperations = records;
  window.ownedWebObserverErrors = [];
  window.ownedWebAction = 'initialization';
  const copy = value => JSON.parse(JSON.stringify(value));
  const snapshot = () => ({
    filter: document.querySelector('#chat-file-filter textarea, #chat-file-filter input')?.value,
    ids: [...document.querySelectorAll('#chat-file-list [data-chat-file-id]')].map(node => node.dataset.chatFileId),
    selected: [...document.querySelectorAll('#chat-file-list .is-selected')].map(node => node.dataset.chatFileId),
    focus: document.querySelector('#chat-selected-file')?.textContent,
    summary: document.querySelector('#workbench-file-summary')?.textContent,
  });
  const record = (phase, values) => {
    try { records.push({sequence: records.length, time: performance.now(), action: window.ownedWebAction, phase, ...copy(values)}); }
    catch (error) { window.ownedWebObserverErrors.push({phase, error: String(error)}); }
  };
  const observe = () => {
    const guard = window.maraFileBrowserRefresh;
    if (guard && !guard.ownedObserved) {
      guard.ownedObserved = true;
      record('installed', {});
      for (const name of ['captureFiles', 'captureSelector', 'captureFileSelection']) {
        const original = guard[name];
        guard[name] = function (...args) {
          const result = original(...args);
          record(name, {args, stamp: result, dom: snapshot()});
          return result;
        };
      }
      for (const name of ['applySelector', 'applyFileSelection']) {
        const original = guard[name];
        guard[name] = function (...args) {
          const result = original(...args);
          record(name, {args, returned: result, dom: snapshot()});
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
        try {
          record('applyFiles', {stamp: payload?.stamp, filter: payload?.filter,
            ids: payload?.outputs?.[0]?.map(row => row.id), args,
            outputs: payload?.outputs, returned: result,
            display: payload?.outputs?.slice(2).map(text),
            applied: result === payload?.outputs, slots: result.length, dom: snapshot()});
        } catch (error) { window.ownedWebObserverErrors.push({phase: 'applyFiles', error: String(error)}); }
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
    if (event.target.closest?.('#chat-file-click')) record('fileClickInput', {value: event.target.value, dom: snapshot()});
  }, true);
  document.addEventListener('click', event => {
    const card = event.target.closest?.('[data-chat-file-id]');
    if (card) record('fileCardClick', {id: card.dataset.chatFileId, trusted: event.isTrusted, dom: snapshot()});
  }, true);
}

function assertLatestFilter(records, first, latest, complete, coalesced = false) {
  const assert = require('node:assert/strict');
  const lastInput = records.findLast(item => item.phase === 'input' && item.action === 'ABA-last-A');
  assert.ok(lastInput, 'last A must have a distinct real input event');
  assert.ok(latest.filterVersion > first.filterVersion);
  const applications = records.filter(item => item.phase === 'applyFiles' && item.sequence > lastInput.sequence);
  const old = applications.find(item => item.stamp.fileRequest === first.fileRequest && item.stamp.epoch === first.epoch);
  assert.ok(old || coalesced, 'observe old A at the actual apply boundary or prove component coalescing');
  if (old) assert.equal(old.applied, false, 'old A must be rejected after last A was issued');
  assert.deepEqual(applications.filter(item => item.applied && item.stamp.filterVersion < latest.filterVersion), [], 'no obsolete filter may apply');
  if (complete) {
    const applied = applications.find(item => item.stamp.fileRequest === latest.fileRequest && item.applied);
    assert.ok(applied, 'last A must successfully apply, not merely complete its request');
    assert.equal(applied.slots, 4);
    return applied;
  }
}

module.exports = {install, assertLatestFilter};

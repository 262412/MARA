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
        record('applyFiles', {stamp: payload?.stamp, filter: payload?.filter,
          ids: payload?.outputs?.[0]?.map(row => row.id), args,
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

module.exports = {install};

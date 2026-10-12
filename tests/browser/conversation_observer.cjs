// Passive events and option identity; never focus, scroll, dispatch or write props.
function install() {
  const trace = window.ownedConversationTrace = {records: [], errors: []};
  const nodes = new WeakMap();
  let next = 0;
  const identity = node => {
    if (!node) return null;
    if (!nodes.has(node)) nodes.set(node, ++next);
    return {node: nodes.get(node), tag: node.tagName, id: node.id,
      role: node.getAttribute?.('role'), parent: node.closest?.('[id]')?.id};
  };
  const snapshot = () => {
    const input = document.querySelector('#conversation-dropdown input');
    return {active: identity(document.activeElement), input: identity(input),
      value: input?.value, expanded: input?.getAttribute('aria-expanded'),
      options: [...document.querySelectorAll('#conversation-dropdown [role=option]')].map(node => ({
        ...identity(node), name: node.getAttribute('aria-label'), connected: node.isConnected,
        rect: node.getBoundingClientRect().toJSON()}))};
  };
  const record = (phase, detail = {}) => {
    try { trace.records.push({sequence: trace.records.length, time: performance.now(),
      phase, action: window.ownedWebAction, ...detail, dom: snapshot()}); }
    catch (error) { trace.errors.push({phase, error: String(error)}); }
  };
  for (const name of ['focusin', 'focusout', 'input', 'pointerdown', 'pointerup', 'click']) {
    document.addEventListener(name, event => record(name, {target: identity(event.target),
      trusted: event.isTrusted, pointer: event.pointerId,
      option: identity(event.target.closest?.('[role=option]'))}), true);
  }
  let last = '';
  new MutationObserver(() => {
    const current = JSON.stringify(snapshot());
    if (current !== last) { last = current; record('dom'); }
  }).observe(document, {childList: true, subtree: true, attributes: true, characterData: true});
  record('installed');
}

module.exports = {install};

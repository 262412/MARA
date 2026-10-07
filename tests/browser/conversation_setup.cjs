// Operation endpoints for the real UI; a queue snapshot is not chain completion.
module.exports = ({expect, page, queue, evidence, send, tailFinished, ready, refreshTrace}) => {
  const {chainFor, endpoint} = require('./conversation_endpoint.cjs');
  const entries = Object.entries(ready.functions).map(([id, fn]) => ({...fn, id: Number(id)}));
  const select = entries.find(fn => fn.id === ready.roles.conversation_select);
  const dropdownId = select.inputs[0];
  const newRoot = entries.find(fn => fn.name === 'new_conv');
  const root = fn => fn.trigger_after == null ? fn : root(entries.find(item => item.id === fn.trigger_after));
  const rename = entries.find(fn => fn.name === 'rename_conv' && root(fn).targets.some(([, event]) => event === 'submit'));
  const gestures = new Map();
  const operations = new Map(), endpoints = [];
  const trace = () => page.evaluate(() => window.ownedFrameworkTrace.records);
  const mark = async (conversation) => {
    const start = await page.evaluate(() => window.ownedFrameworkTrace.records.length);
    operations.set(start, {queueStart: queue.length, session: queue.sessionHash, conversation});
    return start;
  };
  const ended = async (root, start, allowFailure = []) => {
    const chain = chainFor(ready.functions, root.id), operation = operations.get(start);
    if (!operation) throw Error('Operation start was not recorded');
    const observation = {root: root.id, start, session: operation.session};
    endpoints.push(observation);
    await expect.poll(async () => {
      const framework = await page.evaluate(() => window.ownedFrameworkTrace);
      const server = await (await fetch(new URL('/owned-web-operations', page.url()))).json();
      const data = await evidence();
      observation.last = endpoint({chain, framework, server, statuses: data.queue_events, start,
        session: operation.session, conversation: operation.conversation, allowFailure,
        queue: queue.map((fn, i) => ({fn, eventId: queue.requestIds[i]})).slice(operation.queueStart)});
      return observation.last.complete;
    // Locked-framework diagnostic measured a complete 13-request selection tail
    // at 31.445 s. This is an observed-operation budget, not a product timeout.
    }, {timeout: 45000, message: 'Exact conversation operation endpoint'}).toBe(true);
  };
  const selected = async (id, start) => {
    await expect.poll(() => page.evaluate(({id, start, dropdownId}) => window.ownedFrameworkTrace.records.some(row => row.sequence >= start && row.phase === 'flush_end' &&
      row.updates.some(update => update.id === dropdownId && update.prop === 'value' && update.value === id)), {id, start, dropdownId}), {timeout: 20000}).toBe(true);
  };
  const sourcesApplied = (id, selectedIds) => expect.poll(() => page.evaluate(({id, selectedIds}) =>
    window.ownedWebOperations.some(row => row.phase === 'applyFiles' && row.applied && row.args[2] === id &&
      JSON.stringify(row.args[1]) === JSON.stringify(selectedIds)), {id, selectedIds}), {timeout: 20000}).toBe(true);
  async function choose(row, {complete = true} = {}) {
    const start = await mark(row.id);
    gestures.set(start, {queueStart: queue.length, domStart: await page.evaluate(() => window.ownedConversationTrace.records.length)});
    const input = page.locator('#conversation-dropdown input');
    await input.fill(row.name);
    const option = page.getByRole('option', {name: row.name, exact: true});
    await expect(option).toHaveCount(1);
    await option.click();
    await selected(row.id, start);
    if (complete) await ended(select, start);
    return start;
  }
  let turns = 0;
  async function create(name, file) {
    const before = (await evidence()).conversations.map(row => row.id);
    let start = await mark();
    await page.locator('#new-conv-button').click();
    await expect.poll(async () => (await evidence()).conversations.filter(row => !before.includes(row.id)).length).toBe(1);
    const row = (await evidence()).conversations.find(row => !before.includes(row.id));
    await selected(row.id, start);
    await ended(newRoot, start);
    await sourcesApplied(row.id, []);
    await page.locator(`[data-chat-file-id="${file}"]`).click();
    await sourcesApplied(row.id, [file]);
    await expect(page.locator(`[data-chat-file-id="${file}"]`)).toHaveClass(/is-selected/);
    // Streaming produces many unrelated component writes. Keep passive transport,
    // DOM, production-guard and server evidence, without debugger logpoints here.
    await refreshTrace.setActive(false, 'prepare stored messages for ' + row.id);
    try {
      await send(page, 'Save source selection for ' + name);
      await tailFinished(queue, ++turns);
    } finally {
      await refreshTrace.setActive(true, 'stored messages preparation ended');
    }
    await page.locator('#rename-conv-button').click();
    const input = page.getByPlaceholder('Conversation name', {exact: true});
    await input.fill(name);
    start = await mark();
    await input.press('Enter');
    await expect.poll(() => page.evaluate(({start, fn}) => window.ownedFrameworkTrace.records.some(item => item.sequence >= start && item.phase === 'handle_data' && item.fn === fn), {start, fn: rename.id}), {timeout: 20000}).toBe(true);
    await expect.poll(() => page.evaluate(({start, dropdownId, name, id}) => window.ownedFrameworkTrace.records.some(item => item.sequence >= start && item.phase === 'flush_end' &&
      item.updates.some(update => update.id === dropdownId && update.prop === 'choices' && update.value.some(pair => pair[0] === name && pair[1] === id))), {start, dropdownId, name, id: row.id}), {timeout: 20000}).toBe(true);
    await selected(row.id, start);
    await expect(input).toBeHidden();
    await ended(rename, start);
    await expect(page.locator('#conversation-dropdown input')).toHaveValue(name);
    return {...(await evidence()).conversations.find(item => item.id === row.id), name, file};
  }
  async function proof(row, start) {
    const gesture = gestures.get(start);
    const data = await evidence();
    const server = await (await fetch(new URL('/owned-web-operations', page.url()))).json();
    const refresh = entries.find(fn => fn.name === 'refresh_chat_file_list');
    let current = select, citationFn;
    while (current) {
      if (current.name === 'render_latest_citations_card') citationFn = current.id;
      current = entries.find(fn => fn.trigger_after === current.id);
    }
    const citation = server.findLast(item => item.phase === 'return' && item.fn === citationFn && item.session_hash === queue.sessionHash);
    const citationsText = await page.evaluate(html => {
      const template = document.createElement('template'); template.innerHTML = html;
      return template.content.textContent;
    }, citation.result);
    const browser = await page.evaluate(({name, domStart}) => {
      const rendered = document.createElement('template');
      rendered.innerHTML = window.ownedWebOperations.findLast(row => row.phase === 'applyFiles' && row.applied)?.outputs[1] || '';
      return {
      renderedIds: [...rendered.content.querySelectorAll('[data-chat-file-id]')].map(node => node.dataset.chatFileId),
      framework: window.ownedFrameworkTrace,
      web: {records: window.ownedWebOperations, errors: window.ownedWebObserverErrors},
      gesture: window.ownedConversationTrace.records.find(item => item.sequence >= domStart && item.phase === 'pointerdown' && item.option && item.dom.options.some(option => option.name === name && option.node === item.option.node)),
      dom: {conversation: document.querySelector('#conversation-dropdown input').value,
        ids: [...document.querySelectorAll('#chat-file-list [data-chat-file-id]')].map(node => node.dataset.chatFileId),
        selected: [...document.querySelectorAll('#chat-file-list .is-selected')].map(node => node.dataset.chatFileId),
        focus: document.querySelector('#chat-selected-file').textContent,
        summary: document.querySelector('#workbench-file-summary').textContent,
        answer: document.querySelector('#answer-panel').textContent,
        citations: document.querySelector('#citations-card').textContent}
    }; }, {name: row.name, domStart: gesture.domStart});
    return {...browser, server, start, citationFn, citationsText, session: queue.sessionHash, username: 'browser-owner',
      user: data.users['browser-owner'], selectFn: select.id, dropdownId,
      sourceIndex: select.outputs.indexOf(refresh.inputs[3]),
      queue: queue.map((fn, index) => ({fn, eventId: queue.requestIds[index]})).slice(gesture.queueStart),
      expected: {...row, sources: [row.file], messages: row.data_source.messages, retrievalMessages: row.data_source.retrieval_messages,
        filename: data.files.find(file => file.id === row.file).name}};
  }
  return {create, choose, mark, trace, selected, ended, proof, select, newRoot, rename, dropdownId, endpoints};
};

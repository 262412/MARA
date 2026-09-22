// Operation endpoints for the real UI; a queue snapshot is not chain completion.
module.exports = ({expect, page, queue, evidence, send, tailFinished, ready}) => {
  const entries = Object.entries(ready.functions).map(([id, fn]) => ({...fn, id: Number(id)}));
  const select = entries.find(fn => fn.id === ready.roles.conversation_select);
  const dropdownId = select.inputs[0];
  const newRoot = entries.find(fn => fn.name === 'new_conv');
  const rename = entries.find(fn => fn.name === 'rename_conv' && fn.targets.some(([, event]) => event === 'submit'));
  const last = root => {
    let fn = root;
    while (entries.some(item => item.trigger_after === fn.id)) fn = entries.find(item => item.trigger_after === fn.id);
    return fn.id;
  };
  const trace = () => page.evaluate(() => window.ownedFrameworkTrace.records);
  const mark = () => page.evaluate(() => window.ownedFrameworkTrace.records.length);
  const ended = async (root, start) => {
    const tail = last(root);
    await expect.poll(() => page.evaluate(({start, tail}) => window.ownedFrameworkTrace.records.some(row => row.sequence >= start && row.phase === 'js_result' && row.fn === tail), {start, tail}), {timeout: 20000}).toBe(true);
  };
  const selected = async (id, start) => {
    await expect.poll(() => page.evaluate(({id, start, dropdownId}) => window.ownedFrameworkTrace.records.some(row => row.sequence >= start && row.phase === 'flush_end' &&
      row.updates.some(update => update.id === dropdownId && update.prop === 'value' && update.value === id)), {id, start, dropdownId}), {timeout: 20000}).toBe(true);
  };
  const sourcesApplied = (id, selectedIds) => expect.poll(() => page.evaluate(({id, selectedIds}) =>
    window.ownedWebOperations.some(row => row.phase === 'applyFiles' && row.applied && row.args[2] === id &&
      JSON.stringify(row.args[1]) === JSON.stringify(selectedIds)), {id, selectedIds}), {timeout: 20000}).toBe(true);
  async function choose(row, {complete = true} = {}) {
    const start = await mark();
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
    await send(page, 'Save source selection for ' + name);
    await tailFinished(queue, ++turns);
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
    await expect(page.locator('#conversation-dropdown input')).toHaveValue(name);
    return {...row, name, file};
  }
  return {create, choose, mark, trace, selected, ended, select, newRoot, rename, dropdownId};
};

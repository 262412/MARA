// Finite controlled full-App interleavings; separate from the original 37 records.
const fs = require('node:fs');
const path = require('node:path');

module.exports = ({expect, login, evidence, send, tailFinished, results, output, base, ready}) => {
  async function control(route, spec) {
    const response = await fetch(base + '/owned-file-browser-gate' + route,
      spec === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(spec)});
    expect(response.ok).toBeTruthy();
    return response.json();
  }
  async function focusCase(timing) {
    const {page, queue} = await login('browser-owner', {traceConversation: true});
    const key = 'conversation-focus-' + timing;
    const setup = require('./conversation_setup.cjs')({expect, page, queue, evidence, send, tailFinished, ready});
    await page.context().tracing.start({screenshots: false, snapshots: false, sources: false});
    let a, b;
    try {
      await page.getByText('Conversation', {exact: true}).click();
      a = await setup.create('U1 A ' + timing, 'owned-observatory');
      b = await setup.create('U1 B ' + timing, 'r3c-browser-owner-text');
      await control('/arm', {key, callback: 'WebOperation', event: 'return', function_id: ready.roles.conversation_select_tail,
        username: 'browser-owner', session_hash: queue.sessionHash});
      const start = await setup.choose(a, {complete: false});
      await expect.poll(async () => (await control(''))[key]?.entered, {timeout: 20000}).toBe(true);
      const input = page.locator('#conversation-dropdown input');
      const option = page.getByRole('option', {name: b.name, exact: true});
      if (timing === 'before-open') {
        await control('/release/' + key, {});
        await setup.ended(setup.select, start);
      }
      await input.fill(b.name);
      await expect(option).toBeVisible();
      if (timing === 'pointer-down') {
        const box = await option.boundingBox();
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
        await page.mouse.down();
      }
      if (timing !== 'before-open') {
        await control('/release/' + key, {});
        await setup.ended(setup.select, start);
      }
      if (timing === 'pointer-down') await page.mouse.up();
      else {
        await expect(input).toBeFocused();
        await expect(option).toBeVisible();
        await option.click();
      }
      await setup.selected(b.id, start);
      await expect(page.locator('#chat-selected-file')).toContainText('.txt');
      results.scenarios.push({name: 'conversation-focus-' + timing, a, b, session: queue.sessionHash, gate: (await control(''))[key]});
    } finally {
      if ((await control(''))[key]) await control('/release/' + key, {});
      fs.writeFileSync(path.join(output, key + '.json'), JSON.stringify({a, b, queue, requestIds: queue.requestIds,
        session: queue.sessionHash, gate: (await control(''))[key], dom: await page.evaluate(() => window.ownedConversationTrace)}, null, 2));
      fs.writeFileSync(path.join(output, key + '.html'), await page.content());
      await page.context().tracing.stop({path: path.join(output, key + '.zip')});
      await page.close();
    }
  }
  async function conversationFocusBeforeOpen() { await focusCase('before-open'); }
  async function conversationFocusAfterOpen() { await focusCase('after-open'); }
  async function conversationFocusDuringClick() { await focusCase('pointer-down'); }
  async function choicesCase(kind) {
    const {page, queue} = await login('browser-owner', {traceConversation: true});
    const key = 'conversation-' + kind;
    const setup = require('./conversation_setup.cjs')({expect, page, queue, evidence, send, tailFinished, ready});
    let a, b;
    try {
      await page.getByText('Conversation', {exact: true}).click();
      a = await setup.create('U1 A ' + kind, 'owned-observatory');
      b = await setup.create('U1 B ' + kind, 'r3c-browser-owner-text');
      if (kind !== 'restore') await setup.choose(a);
      const fn = {rename: setup.rename, new: setup.newRoot, restore: setup.select}[kind];
      await control('/arm', {key, callback: 'WebOperation', event: 'return', function_id: fn.id,
        username: 'browser-owner', session_hash: queue.sessionHash});
      if (kind === 'new') await page.locator('#new-conv-button').click();
      else if (kind === 'rename') {
        await page.locator('#rename-conv-button').click();
        const rename = page.getByPlaceholder('Conversation name', {exact: true});
        await rename.fill(a.name + ' renamed');
        await rename.press('Enter');
      } else {
        await page.locator('#conversation-dropdown input').fill(a.name);
        await page.getByRole('option', {name: a.name, exact: true}).click();
      }
      await expect.poll(async () => (await control(''))[key]?.entered, {timeout: 20000}).toBe(true);
      const input = page.locator('#conversation-dropdown input');
      await input.fill(b.name);
      const option = page.getByRole('option', {name: b.name, exact: true});
      await expect(option).toBeVisible();
      const start = await setup.mark();
      if (kind === 'restore') await option.click();
      await control('/release/' + key, {});
      await expect.poll(() => page.evaluate(({start, fn}) => window.ownedFrameworkTrace.records.some(row =>
        row.sequence >= start && row.phase === 'handle_data' && row.fn === fn), {start, fn: fn.id}), {timeout: 20000}).toBe(true);
      if (kind !== 'restore') {
        await expect(input).toHaveValue(b.name);
        await expect(option).toBeVisible();
        await option.click();
      }
      await expect.poll(async () => (await (await fetch(base + '/owned-web-operations')).json()).some(row =>
        row.phase === 'return' && row.fn === setup.select.id && row.session_hash === queue.sessionHash && row.inputs[0] === b.id), {timeout: 20000}).toBe(true);
      await setup.selected(b.id, start);
      await expect(page.locator('#chat-selected-file')).toContainText('.txt');
      results.scenarios.push({name: key, a, b, session: queue.sessionHash, gate: (await control(''))[key]});
    } finally {
      if ((await control(''))[key]) await control('/release/' + key, {});
      fs.writeFileSync(path.join(output, key + '.json'), JSON.stringify({a, b, session: queue.sessionHash,
        gate: (await control(''))[key], dom: await page.evaluate(() => window.ownedConversationTrace)}, null, 2));
      await page.close();
    }
  }
  async function conversationRenameChoices() { await choicesCase('rename'); }
  async function conversationNewChoices() { await choicesCase('new'); }
  async function conversationRestoreOverlap() { await choicesCase('restore'); }
  return [conversationFocusBeforeOpen, conversationFocusAfterOpen, conversationFocusDuringClick,
    conversationRenameChoices, conversationNewChoices, conversationRestoreOverlap];
};

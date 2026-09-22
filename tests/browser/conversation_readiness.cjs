// Explicit UI readiness and fast user interaction, separate from file-refresh races.
const fs = require('node:fs');
const path = require('node:path');

module.exports = ({expect, login, evidence, send, tailFinished, results, output, base, ready}) => {
  const control = async (route, spec) => {
    const response = await fetch(base + '/owned-file-browser-gate' + route,
      spec === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(spec)});
    expect(response.ok).toBe(true);
    return response.json();
  };
  async function run(kind) {
    const {page, queue, refreshTrace} = await login('browser-owner', {traceConversation: true});
    const key = 'readiness-' + kind;
    const setup = require('./conversation_setup.cjs')({expect, page, queue, evidence, send, tailFinished, ready, refreshTrace});
    let a, b, pending, after;
    try {
      await page.getByText('Conversation', {exact: true}).click();
      a = await setup.create('Ready A ' + kind, 'owned-observatory');
      b = await setup.create('Ready B ' + kind, 'r3c-browser-owner-text');
      if (kind !== 'restore' && kind !== 'focus') await setup.choose(a);
      expect(await page.evaluate(() => window.ownedFrameworkTrace.logpointsActive)).toBe(true);
      const fn = kind === 'new' ? setup.newRoot : kind === 'rename' || kind === 'error' ? setup.rename : setup.select;
      await control('/arm', {key, callback: 'WebOperation', event: 'return',
        function_id: kind === 'focus' ? ready.roles.conversation_select_tail : fn.id,
        username: 'browser-owner', session_hash: queue.sessionHash, failure: kind === 'error'});
      const start = await setup.mark();
      if (kind === 'new') await page.locator('#new-conv-button').click();
      else if (kind === 'rename' || kind === 'error') {
        await page.locator('#rename-conv-button').click();
        const rename = page.getByPlaceholder('Conversation name', {exact: true});
        await rename.fill(a.name + ' renamed');
        await rename.press('Enter');
      } else {
        await page.locator('#conversation-dropdown input').fill(a.name);
        await page.getByRole('option', {name: a.name, exact: true}).click();
      }
      await expect.poll(async () => (await control(''))[key]?.entered, {timeout: 20000}).toBe(true);
      const dock = page.locator('#conversation-dock');
      await expect(dock).toHaveAttribute('aria-busy', 'true');
      expect(await dock.evaluate(node => node.inert)).toBe(true);
      const input = page.locator('#conversation-dropdown input');
      const box = await input.boundingBox();
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      await expect(input).not.toBeFocused();
      await expect(page.locator('#conversation-dropdown [role=option]')).toHaveCount(0);
      pending = {gate: (await control(''))[key], dom: await page.evaluate(() => window.ownedConversationTrace)};
      expect(pending.gate.completed).toBe(false);
      const filter = page.locator('#chat-file-filter textarea, #chat-file-filter input');
      if (kind === 'focus') {
        await filter.fill('.txt');
        await expect(filter).toBeFocused();
      }
      await control('/release/' + key, {});
      await setup.ended(fn, start);
      await expect(dock).toHaveAttribute('aria-busy', 'false');
      if (kind === 'focus') await expect(filter).toBeFocused();
      if (kind === 'error') {
        await expect(page.getByRole('alert').filter({hasText: 'Owned U1 return failure'})).toBeVisible();
        expect((await evidence()).conversations.find(row => row.id === a.id).name).toBe(a.name + ' renamed');
      }
      await setup.choose(b);
      expect((await setup.trace()).filter(row => row.phase === 'logpoints_state' && row.sequence >= start).every(row => row.active)).toBe(true);
      await expect(page.locator('#chat-selected-file')).toContainText('.txt');
      after = await page.evaluate(() => window.ownedConversationTrace);
      results.scenarios.push({name: key, a, b, session: queue.sessionHash,
        pendingGate: pending.gate, completedGate: (await control(''))[key]});
    } finally {
      if ((await control(''))[key]) await control('/release/' + key, {});
      fs.writeFileSync(path.join(output, key + '.json'), JSON.stringify({a, b, pending, after,
        session: queue.sessionHash, dom: await page.evaluate(() => window.ownedConversationTrace)}, null, 2));
      await page.close();
    }
  }
  async function conversationNewReadiness() { await run('new'); }
  async function conversationRenameReadiness() { await run('rename'); }
  async function conversationRestoreReadiness() { await run('restore'); }
  async function conversationErrorReadiness() { await run('error'); }
  async function conversationTailFocusOwnership() { await run('focus'); }
  return [conversationNewReadiness, conversationRenameReadiness, conversationRestoreReadiness,
    conversationErrorReadiness, conversationTailFocusOwnership];
};

const fs = require('node:fs');
const path = require('node:path');
const exit = require('./browser_exit.cjs');

module.exports = ({expect, login, evidence, results, output, base, ready}) => {
  const control = async (route, spec) => {
    const response = await fetch(base + '/owned-file-browser-gate' + route,
      spec === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(spec)});
    expect(response.ok).toBe(true);
    return response.json();
  };
  async function run(expectBusy, signin = false) {
    const key = signin ? 'reload-signin-readiness' : expectBusy ? 'reload-readiness' : 'reload-late-write';
    const root = fn => fn.trigger_after == null ? fn : root(ready.functions[fn.trigger_after]);
    const reload = Object.entries(ready.functions).find(([, fn]) => fn.name === 'reload_conv' &&
      root(fn).targets.some(([, event]) => event === 'load') && (signin ? fn.trigger_after != null : fn.trigger_after == null));
    expect(reload).toBeDefined();
    const id = Number(reload[0]);
    await control('/arm', {key, callback: 'WebOperation', event: 'return', function_id: id, username: 'browser-owner'});
    const {page, queue, refreshTrace} = await login('browser-owner', {initialize: false, traceConversation: true});
    const setup = require('./conversation_setup.cjs')({expect, page, queue, evidence, ready, refreshTrace});
    let created, beforeRelease, afterRelease;
    try {
      await expect.poll(async () => (await control(''))[key]?.entered, {timeout: 20000}).toBe(true);
      if (!expectBusy) await page.getByText('Conversation', {exact: true}).click();
      const previous = (await evidence()).conversations.map(row => row.id);
      const button = page.locator('#new-conv-button');
      if (expectBusy) {
        await expect(page.locator('#conversation-dock')).toHaveAttribute('aria-busy', 'true');
        const box = await page.getByText('Conversation', {exact: true}).boundingBox();
        await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
        expect((await evidence()).conversations.map(row => row.id)).toEqual(previous);
        await control('/release/' + key, {});
        await expect(page.locator('#conversation-dock')).toHaveAttribute('aria-busy', 'false');
        await page.getByText('Conversation', {exact: true}).click();
      }
      const newStart = await setup.mark();
      await button.click();
      await expect.poll(async () => (await evidence()).conversations.filter(row => !previous.includes(row.id)).length, {timeout: 20000}).toBe(1);
      created = (await evidence()).conversations.find(row => !previous.includes(row.id));
      await expect(page.locator('#conversation-dropdown input')).toHaveValue(created.name);
      beforeRelease = await page.evaluate(() => window.ownedConversationTrace);
      if (!expectBusy) {
        expect((await control(''))[key].completed).toBe(false);
        await control('/release/' + key, {});
        await expect.poll(() => page.evaluate(fn => window.ownedFrameworkTrace.records.some(row => row.phase === 'handle_data' && row.fn === fn), id), {timeout: 20000}).toBe(true);
      }
      await setup.ended(setup.newRoot, newStart);
      await expect(page.locator('#conversation-dock')).toHaveAttribute('aria-busy', 'false');
      afterRelease = await page.evaluate(() => window.ownedConversationTrace);
      await expect(page.locator('#conversation-dropdown input')).toHaveValue(created.name);
      results.scenarios.push({name: key, created, session: queue.sessionHash, gate: (await control(''))[key]});
    } catch (error) {
      exit.primary(results, output, error);
      throw error;
    } finally {
      await exit.cleanup(results, [
        ['reload snapshot', async () => fs.writeFileSync(path.join(output, key + '.json'), JSON.stringify({created, beforeRelease, afterRelease,
          session: queue.sessionHash, gate: (await control(''))[key], dom: await page.evaluate(() => window.ownedConversationTrace),
          framework: await refreshTrace.snapshot(), endpoints: setup.endpoints}, null, 2))],
        ['reload release', () => control('/release/' + key, {})],
        ['reload page close', () => page.close()],
      ]);
    }
  }
  async function conversationReloadLateWrite() { await run(false); }
  async function conversationReloadReadiness() { await run(true); }
  async function conversationSigninReloadReadiness() { await run(true, true); }
  return [conversationReloadLateWrite, conversationReloadReadiness, conversationSigninReloadReadiness];
};

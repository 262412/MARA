// Delays real refresh results while users continue to interact with the full App.
module.exports = ({expect, login, evidence, settled, results, base}) => {
  async function control(path, spec) {
    const response = await fetch(base + '/owned-file-browser-gate' + path,
      spec === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(spec)});
    expect(response.ok).toBeTruthy();
    return response.json();
  }

  async function initializationFilterOverlap() {
    const key = 'initial-empty-refresh';
    await control('/arm', {key, callback: 'ChatPage.refresh_chat_file_list', username: 'browser-owner', filter_text: ''});
    const {page, queue} = await login('browser-owner', {initialize: false});
    try {
      await expect.poll(async () => (await control(''))[key]?.entered).toBe(true);
      const filter = page.locator('#chat-file-filter textarea, #chat-file-filter input');
      await expect(filter).toBeEnabled();
      await filter.fill('.txt');
      await expect(page.locator('#chat-file-list [data-chat-file-id]')).toHaveCount(1);
      await expect(page.locator('#chat-file-list')).toContainText('.txt');
      await control('/release/' + key, {});
      await expect.poll(async () => (await control(''))[key]?.completed).toBe(true);
      await settled(queue);
      const snapshot = {
        name: 'initialization-filter-overlap', gate: (await control(''))[key],
        filter: await filter.inputValue(),
        ids: await page.locator('#chat-file-list [data-chat-file-id]').evaluateAll(nodes => nodes.map(node => node.dataset.chatFileId)),
        summary: await page.locator('#workbench-file-summary').innerText(),
        focus: await page.locator('#chat-selected-file').innerText(),
        writes: (await evidence()).writes,
      };
      results.fileBrowserRaces ||= [];
      results.fileBrowserRaces.push(snapshot);
      expect(snapshot.filter).toBe('.txt');
      expect(snapshot.ids).toEqual(['r3c-browser-owner-text']);
      expect(snapshot.summary).toContain('1 file');
      expect(snapshot.writes).toEqual([]);
      results.scenarios.push(snapshot);
    } finally {
      await control('/release/' + key, {});
      await page.close();
    }
  }

  async function filterWhileRefreshIsHeld() {
    const {page, queue} = await login();
    const key = 'filter-A-before-B';
    try {
      await control('/arm', {key, callback: 'ChatPage.refresh_chat_file_list', username: 'browser-owner', session_hash: queue.sessionHash, filter_text: '.txt'});
      const filter = page.locator('#chat-file-filter textarea, #chat-file-filter input');
      await filter.fill('.txt');
      await expect.poll(async () => (await control(''))[key]?.entered).toBe(true);
      await page.evaluate(() => {
        window.r3dListObservations = [];
        new MutationObserver(() => {
          window.r3dListObservations.push({
            filter: document.querySelector('#chat-file-filter textarea, #chat-file-filter input').value,
            ids: [...document.querySelectorAll('#chat-file-list [data-chat-file-id]')].map(node => node.dataset.chatFileId),
          });
        }).observe(document.querySelector('#chat-file-list'), {childList: true, subtree: true});
      });
      await filter.fill('.png');
      await control('/release/' + key, {});
      await expect.poll(() => page.locator('#chat-file-list [data-chat-file-id]').evaluateAll(nodes => nodes.map(node => node.dataset.chatFileId))).toEqual(['r3c-browser-owner-image']);
      await settled(queue);
      const observations = await page.evaluate(() => window.r3dListObservations);
      results.fileBrowserRaces ||= [];
      results.fileBrowserRaces.push({name: 'busy-filter-intent-before-old-return', observations});
      expect(observations.filter(item => item.filter === '.png' && item.ids.length === 1 && item.ids[0] === 'r3c-browser-owner-text'), 'an old filter result must never be applied after the next input').toEqual([]);
      results.scenarios.push({name: 'busy-filter-intent-before-old-return', observations});
    } finally {
      await control('/release/' + key, {});
      await page.close();
    }
  }

  async function concurrentBrowserContexts() {
    const contexts = [await login(), await login(), await login('browser-other')];
    const key = 'same-owner-context-A';
    try {
      const [a, b, other] = contexts;
      await control('/arm', {key, callback: 'ChatPage.refresh_chat_file_list', username: 'browser-owner', session_hash: a.queue.sessionHash, filter_text: '.txt'});
      await a.page.locator('#chat-file-filter textarea, #chat-file-filter input').fill('.txt');
      await expect.poll(async () => (await control(''))[key]?.entered).toBe(true);
      await b.page.locator('#chat-file-filter textarea, #chat-file-filter input').fill('.png');
      await other.page.locator('#chat-file-filter textarea, #chat-file-filter input').fill('.txt');
      await control('/release/' + key, {});
      const expected = ['r3c-browser-owner-text', 'r3c-browser-owner-image', 'r3c-browser-other-text'];
      for (let i = 0; i < contexts.length; i++) {
        await expect.poll(() => contexts[i].page.locator('#chat-file-list [data-chat-file-id]').evaluateAll(nodes => nodes.map(node => node.dataset.chatFileId))).toEqual([expected[i]]);
        await settled(contexts[i].queue);
      }
      expect(new Set(contexts.map(item => item.queue.sessionHash)).size).toBe(3);
      results.scenarios.push({name: 'same-owner-two-browsers-and-other-user-refresh-isolation', sessionHashes: contexts.map(item => item.queue.sessionHash), expected});
    } finally {
      await control('/release/' + key, {});
      for (const {page} of contexts) await page.close();
    }
  }

  return [initializationFilterOverlap, filterWhileRefreshIsHeld, concurrentBrowserContexts];
};

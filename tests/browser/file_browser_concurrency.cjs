// Delays real refresh results while users continue to interact with the full App.
module.exports = ({expect, login, evidence, settled, send, tailFinished, results, base}) => {
  async function control(path, spec) {
    const response = await fetch(base + '/owned-file-browser-gate' + path,
      spec === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(spec)});
    expect(response.ok).toBeTruthy();
    return response.json();
  }

  async function expectedFiles(username, suffix) {
    const data = await evidence();
    return data.files.filter(file => file.user === data.users[username] && file.name.toLowerCase().endsWith(suffix)).map(file => file.id).sort();
  }

  async function initializationFilterOverlap() {
    const key = 'initial-empty-refresh';
    const expected = await expectedFiles('browser-owner', '.txt');
    const writesBefore = (await evidence()).writes;
    await control('/arm', {key, callback: 'ChatPage.refresh_chat_file_list', username: 'browser-owner', filter_text: ''});
    const {page, queue} = await login('browser-owner', {initialize: false});
    try {
      await expect.poll(async () => (await control(''))[key]?.entered).toBe(true);
      const filter = page.locator('#chat-file-filter textarea, #chat-file-filter input');
      await expect(filter).toBeEnabled();
      await filter.fill('.txt');
      await expect(page.locator('#chat-file-list [data-chat-file-id]')).toHaveCount(expected.length);
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
      expect(snapshot.ids.sort()).toEqual(expected);
      expect(snapshot.summary).toContain(expected.length + ' file');
      expect(snapshot.writes).toEqual(writesBefore);
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
      await expect.poll(() => page.locator('#chat-file-list [data-chat-file-id]').evaluateAll(nodes => nodes.map(node => node.dataset.chatFileId).sort())).toEqual(await expectedFiles('browser-owner', '.png'));
      await settled(queue);
      const observations = await page.evaluate(() => window.r3dListObservations);
      results.fileBrowserRaces ||= [];
      results.fileBrowserRaces.push({name: 'busy-filter-intent-before-old-return', observations});
      expect(observations.filter(item => item.filter === '.png' && item.ids.includes('r3c-browser-owner-text')), 'an old filter result must never be applied after the next input').toEqual([]);
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
      const expected = [await expectedFiles('browser-owner', '.txt'), await expectedFiles('browser-owner', '.png'), await expectedFiles('browser-other', '.txt')];
      for (let i = 0; i < contexts.length; i++) {
        await expect.poll(() => contexts[i].page.locator('#chat-file-list [data-chat-file-id]').evaluateAll(nodes => nodes.map(node => node.dataset.chatFileId).sort())).toEqual(expected[i]);
        await settled(contexts[i].queue);
      }
      expect(new Set(contexts.map(item => item.queue.sessionHash)).size).toBe(3);
      results.scenarios.push({name: 'same-owner-two-browsers-and-other-user-refresh-isolation', sessionHashes: contexts.map(item => item.queue.sessionHash), expected});
    } finally {
      await control('/release/' + key, {});
      for (const {page} of contexts) await page.close();
    }
  }

  async function repeatedFilterIntent() {
    const {page, queue} = await login();
    const old = 'filter-ABA-old', latest = 'filter-ABA-latest';
    try {
      const filter = page.locator('#chat-file-filter textarea, #chat-file-filter input');
      const ids = () => page.locator('#chat-file-list [data-chat-file-id]').evaluateAll(nodes => nodes.map(node => node.dataset.chatFileId));
      const initial = await ids();
      await control('/arm', {key: old, callback: 'ChatPage.refresh_chat_file_list', username: 'browser-owner', session_hash: queue.sessionHash, filter_text: '.txt'});
      await page.evaluate(() => { window.ownedWebAction = 'ABA-first-A'; });
      await filter.fill('.txt');
      await expect.poll(async () => (await control(''))[old]?.entered).toBe(true);
      await control('/arm', {key: latest, callback: 'ChatPage.refresh_chat_file_list', username: 'browser-owner', session_hash: queue.sessionHash, filter_text: '.txt'});
      await page.evaluate(() => { window.ownedWebAction = 'ABA-B'; });
      await filter.fill('.png');
      await page.evaluate(() => { window.ownedWebAction = 'ABA-last-A'; });
      await filter.fill('.txt');
      await control('/release/' + old, {});
      await expect.poll(async () => (await control(''))[latest]?.entered).toBe(true);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const beforeLatest = await ids();
      results.fileBrowserRaces ||= [];
      results.fileBrowserRaces.push({name: 'A-B-A-before-latest-return', initial, beforeLatest});
      expect(beforeLatest, 'first A must not stand in for the last A').toEqual(initial);
      await control('/release/' + latest, {});
      await expect.poll(async () => (await ids()).sort()).toEqual(await expectedFiles('browser-owner', '.txt'));
      await settled(queue);
      results.scenarios.push({name: 'A-B-A-retains-issuance-order', initial, beforeLatest});
    } finally {
      await control('/release/' + old, {});
      await control('/release/' + latest, {});
      await page.close();
    }
  }

  async function selectorInitializationSelectionOverlap() {
    const key = 'initial-selector-before-file-choice';
    await control('/arm', {key, callback: 'FileSelector.load_files', username: 'browser-owner'});
    const {page, queue} = await login('browser-owner', {initialize: false});
    try {
      await expect.poll(async () => (await control(''))[key]?.entered).toBe(true);
      await expect(page.locator('#chat-file-list')).toHaveAttribute('data-chat-file-bound', 'true');
      await page.locator('[data-chat-file-id="r3c-browser-owner-text"]').click();
      await expect(page.locator('[data-chat-file-id="r3c-browser-owner-text"]')).toHaveClass(/is-selected/);
      await control('/release/' + key, {});
      await expect.poll(async () => (await control(''))[key]?.completed).toBe(true);
      await settled(queue);
      const selected = await page.locator('#chat-file-list .is-selected').evaluateAll(nodes => nodes.map(node => node.dataset.chatFileId));
      const focus = await page.locator('#chat-selected-file').innerText();
      results.fileBrowserRaces ||= [];
      results.fileBrowserRaces.push({name: 'selector-init-versus-new-choice', selected, focus});
      expect(selected).toEqual(['r3c-browser-owner-text']);
      expect(focus).toContain('.txt');
      results.scenarios.push({name: 'selector-initialization-preserves-new-choice', selected, focus});
    } finally {
      await control('/release/' + key, {});
      await page.close();
    }
  }

  async function conversationDuringFileRefresh() {
    const {page, queue} = await login();
    const key = 'old-conversation-refresh';
    await control('/arm', {key, callback: 'ChatPage.refresh_chat_file_list', username: 'browser-owner', session_hash: queue.sessionHash, filter_text: '.txt'});
    try {
      await page.getByText('Conversation', {exact: true}).click();
      let turns = 0;
      async function create(name, file) {
        const before = (await evidence()).conversations.length;
        await page.locator('#new-conv-button').click();
        await expect.poll(async () => (await evidence()).conversations.length).toBe(before + 1);
        await settled(queue);
        await page.locator(`[data-chat-file-id="${file}"]`).click();
        await expect(page.locator(`[data-chat-file-id="${file}"]`)).toHaveClass(/is-selected/);
        await send(page, 'Save source selection for ' + name);
        await tailFinished(queue, ++turns);
        await page.locator('#rename-conv-button').click();
        const input = page.getByPlaceholder('Conversation name', {exact: true});
        await input.fill(name);
        await input.press('Enter');
        await expect(page.locator('#conversation-dropdown input')).toHaveValue(name);
        await settled(queue);
      }
      await create('R3D context A', 'owned-observatory');
      await create('R3D context B', 'r3c-browser-owner-text');
      const dropdown = page.locator('#conversation-dropdown input');
      await dropdown.fill('R3D context A');
      await page.getByRole('option', {name: 'R3D context A', exact: true}).click();
      await expect(page.locator('[data-chat-file-id="owned-observatory"]')).toHaveClass(/is-selected/);
      await settled(queue);
      await page.locator('#chat-file-filter textarea, #chat-file-filter input').fill('.txt');
      await expect.poll(async () => (await control(''))[key]?.entered).toBe(true);
      await dropdown.fill('R3D context B');
      await page.getByRole('option', {name: 'R3D context B', exact: true}).click();
      await expect(page.locator('#chat-selected-file')).toContainText('.txt');
      await control('/release/' + key, {});
      await settled(queue);
      const focus = await page.locator('#chat-selected-file').innerText();
      const ids = await page.locator('#chat-file-list .is-selected').evaluateAll(nodes => nodes.map(node => node.dataset.chatFileId));
      results.fileBrowserRaces ||= [];
      results.fileBrowserRaces.push({name: 'conversation-switch-during-file-refresh', focus, ids});
      expect(focus).toContain('.txt');
      expect(ids).toEqual(['r3c-browser-owner-text']);
      results.scenarios.push({name: 'conversation-switch-during-file-refresh', focus, ids});
    } finally {
      await control('/release/' + key, {});
      await page.close();
    }
  }

  async function quickUploadThenChooseSource() {
    const {page, queue} = await login();
    const key = 'upload-return-before-new-source-choice';
    const filename = 'r3d-quick-upload.txt';
    await control('/arm', {key, callback: 'FileIndexPage.index_fn_file_with_default_loaders', username: 'browser-owner', session_hash: queue.sessionHash});
    try {
      const response = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/upload');
      await page.locator('#quick-file input[type=file]').setInputFiles({
        name: filename, mimeType: 'text/plain', buffer: Buffer.from('D1 owned upload: seven telescopes.'),
      });
      expect((await response).ok()).toBeTruthy();
      await expect.poll(async () => (await control(''))[key]?.entered, {timeout: 20000}).toBe(true);
      await page.locator('[data-chat-file-id="r3c-browser-owner-image"]').click();
      await expect(page.locator('[data-chat-file-id="r3c-browser-owner-image"]')).toHaveClass(/is-selected/);
      await control('/release/' + key, {});
      await expect(page.locator('#quick-file-upload-status')).toContainText('Indexing completed.', {timeout: 20000});
      await settled(queue);
      const data = await evidence();
      const uploaded = data.files.find(file => file.name === filename && file.user === data.users['browser-owner']);
      const selected = await page.locator('#chat-file-list .is-selected').evaluateAll(nodes => nodes.map(node => node.dataset.chatFileId));
      results.fileBrowserRaces ||= [];
      results.fileBrowserRaces.push({name: 'quick-upload-followed-by-active-choice', uploaded, selected});
      expect(uploaded).toBeDefined();
      await expect(page.locator(`[data-chat-file-id="${uploaded.id}"]`)).toHaveCount(1);
      expect(selected).toEqual(['r3c-browser-owner-image']);
      results.scenarios.push({name: 'index-side-effect-retained-new-source-intent-preserved', uploaded, selected});
    } finally {
      await control('/release/' + key, {});
      await page.close();
    }
  }

  async function reverseFilterDelivery() {
    const {page, queue} = await login();
    const key = 'reverse-filter-delivery';
    await control('/arm', {key, callback: 'refresh_chat_file_list', event: 'delivery', username: 'browser-owner', session_hash: queue.sessionHash, filter_text: '.txt'});
    try {
      const filter = page.locator('#chat-file-filter textarea, #chat-file-filter input');
      await filter.fill('.txt');
      await expect.poll(async () => (await control(''))[key]?.entered).toBe(true);
      await filter.fill('.png');
      const ids = () => page.locator('#chat-file-list [data-chat-file-id]').evaluateAll(nodes => nodes.map(node => node.dataset.chatFileId).sort());
      const expected = await expectedFiles('browser-owner', '.png');
      await expect.poll(ids).toEqual(expected);
      expect((await control(''))[key].completed).toBe(false);
      await control('/release/' + key, {});
      await expect.poll(async () => (await control(''))[key]?.completed).toBe(true);
      await settled(queue);
      expect(await ids()).toEqual(expected);
      results.scenarios.push({name: 'two-filter-completions-delivered-in-reverse-order', expected, gate: (await control(''))[key]});
    } finally {
      await control('/release/' + key, {});
      await page.close();
    }
  }

  async function quickUrlThenChooseSource() {
    const {page, queue} = await login();
    const key = 'url-return-before-source-choice';
    const url = 'https://example.org/owned-web-document';
    await control('/arm', {key, callback: 'FileIndexPage.index_fn_url_with_default_loaders', username: 'browser-owner', session_hash: queue.sessionHash});
    try {
      await page.locator('#quick-url textarea').fill(url);
      await page.locator('#quick-url textarea').press('Enter');
      await expect.poll(async () => (await control(''))[key]?.entered, {timeout: 20000}).toBe(true);
      await page.locator('[data-chat-file-id="r3c-browser-owner-image"]').click();
      await expect(page.locator('[data-chat-file-id="r3c-browser-owner-image"]')).toHaveClass(/is-selected/);
      await control('/release/' + key, {});
      await expect(page.locator('#quick-file-upload-status')).toContainText('Indexing completed.', {timeout: 20000});
      await settled(queue);
      const data = await evidence();
      expect(data.files.some(file => file.name === url && file.user === data.users['browser-owner'])).toBe(true);
      const selected = await page.locator('#chat-file-list .is-selected').evaluateAll(nodes => nodes.map(node => node.dataset.chatFileId));
      expect(selected).toEqual(['r3c-browser-owner-image']);
      results.scenarios.push({name: 'URL-index-side-effect-retained-new-source-intent-preserved', selected});
    } finally {
      await control('/release/' + key, {});
      await page.close();
    }
  }

  async function deletionNotificationDuringRefresh() {
    const {page, queue} = await login();
    const filename = 'r3d-delete-notification.txt';
    const key = 'file-list-before-authorized-deletion';
    await control('/arm', {key, callback: 'refresh_chat_file_list', event: 'delivery', username: 'browser-owner', session_hash: queue.sessionHash, filter_text: '.txt'});
    try {
      const upload = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/upload');
      await page.locator('#quick-file input[type=file]').setInputFiles({name: filename, mimeType: 'text/plain', buffer: Buffer.from('Owned deletion notification document.')});
      expect((await upload).ok()).toBe(true);
      await expect(page.locator('#quick-file-upload-status')).toContainText('Indexing completed.', {timeout: 20000});
      await settled(queue);
      const data = await evidence();
      const uploaded = data.files.find(file => file.name === filename && file.user === data.users['browser-owner']);
      expect(uploaded).toBeDefined();
      await page.locator('[data-chat-file-id="r3c-browser-owner-image"]').click();
      await expect(page.locator('[data-chat-file-id="r3c-browser-owner-image"]')).toHaveClass(/is-selected/);
      await page.locator('#chat-file-filter textarea, #chat-file-filter input').fill('.txt');
      await expect.poll(async () => (await control(''))[key]?.entered).toBe(true);
      await page.getByRole('tab', {name: 'files', exact: true}).click();
      const managerFilter = page.locator('#indices-tab').getByLabel('Filter by name:');
      await managerFilter.fill(filename);
      await managerFilter.press('Enter');
      await page.locator('#file_list_view svelte-virtual-table-viewport').getByText(filename, {exact: true}).click();
      await expect(page.locator('#indices-tab')).toContainText('Selected file: ' + filename);
      await page.locator('#indices-tab').getByRole('button', {name: 'Delete', exact: true}).click();
      await expect.poll(async () => (await evidence()).files.some(file => file.id === uploaded.id)).toBe(false);
      await page.getByRole('tab', {name: 'chat', exact: true}).click();
      const ids = () => page.locator('#chat-file-list [data-chat-file-id]').evaluateAll(nodes => nodes.map(node => node.dataset.chatFileId).sort());
      const expected = await expectedFiles('browser-owner', '.txt');
      await expect.poll(ids).toEqual(expected);
      await control('/release/' + key, {});
      await settled(queue);
      expect(await ids()).toEqual(expected);
      await expect(page.locator('#chat-selected-file')).toContainText('.png');
      results.scenarios.push({name: 'authorized-delete-notification-rejects-prior-catalog', deleted: uploaded.id, expected});
    } finally {
      await control('/release/' + key, {});
      await page.close();
    }
  }

  async function successiveFileChoices() {
    const {page, queue} = await login();
    const old = 'source-choice-A', latest = 'source-choice-B';
    for (const [key, file_id] of [[old, 'owned-observatory'], [latest, 'r3c-browser-owner-image']]) {
      await control('/arm', {key, callback: 'select_chat_file', event: 'delivery', username: 'browser-owner', session_hash: queue.sessionHash, file_id});
    }
    try {
      await expect(page.locator('#index-0 .token')).toHaveCount(0);
      await page.locator('[data-chat-file-id="owned-observatory"]').click();
      await expect.poll(async () => (await control(''))[old]?.entered).toBe(true);
      await page.locator('[data-chat-file-id="r3c-browser-owner-image"]').click();
      await control('/release/' + old, {});
      await expect.poll(async () => (await control(''))[latest]?.entered).toBe(true);
      await settled(queue);
      const scope = (await page.locator('#index-0 .token').allTextContents()).join('\n');
      results.fileBrowserRaces ||= [];
      results.fileBrowserRaces.push({name: 'older-source-selection-before-latest-delivery', scope});
      expect(scope).not.toContain('owned-observatory.pdf');
      await control('/release/' + latest, {});
      await expect(page.locator('[data-chat-file-id="r3c-browser-owner-image"]')).toHaveClass(/is-selected/);
      results.scenarios.push({name: 'successive-card-choices-keep-latest-user-intent', scope});
    } finally {
      await control('/release/' + old, {});
      await control('/release/' + latest, {});
      await page.close();
    }
  }

  return [initializationFilterOverlap, filterWhileRefreshIsHeld, concurrentBrowserContexts,
    repeatedFilterIntent, selectorInitializationSelectionOverlap, conversationDuringFileRefresh,
    quickUploadThenChooseSource, reverseFilterDelivery, quickUrlThenChooseSource,
    deletionNotificationDuringRefresh, successiveFileChoices];
};

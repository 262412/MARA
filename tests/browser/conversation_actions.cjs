// Exercise the existing App through browser events; evidence routes are read-only.
const path = require('node:path');

module.exports = function ({expect, login, evidence, send, tailFinished, settled, initialized, results, output, base, assertFinalizerAndWebWrites}) {
  async function ownedRows() {
    const data = await evidence();
    return data.conversations.filter(row => row.user === data.users['browser-controls']);
  }

  async function openControls(page) {
    await initialized(page.submissionQueue);
    await page.getByText('Conversation', {exact: true}).click();
    await expect(page.locator('#new-conv-button')).toBeVisible();
  }

  async function choose(page, name) {
    await settled(page.submissionQueue);
    const input = page.locator('#conversation-dropdown input');
    await input.fill(name);
    await expect(page.getByRole('option', {name, exact: true})).toBeVisible();
    await expect(page.locator('#conversation-dropdown').getByRole('option')).toHaveCount(1);
    await input.press('ArrowDown');
    await input.press('Enter');
    await expect(input).toHaveValue(name);
    await settled(page.submissionQueue);
  }

  async function rename(page, id, name) {
    await page.locator('#rename-conv-button').click();
    const input = page.getByPlaceholder('Conversation name', {exact: true});
    await input.fill(name);
    await input.press('Enter');
    await expect.poll(async () => (await evidence()).conversations.find(row => row.id === id)?.name).toBe(name);
    await expect(input).toBeHidden();
    await settled(page.submissionQueue);
  }

  async function remove(page, id) {
    await page.locator('#delete-conv-button').click();
    await page.getByRole('button', {name: 'Delete', exact: true}).click();
    await expect.poll(async () => (await evidence()).conversations.some(row => row.id === id)).toBe(false);
    await expect(page.getByRole('button', {name: 'Cancel', exact: true})).toBeHidden();
  }

  async function source(page, id) {
    await expect(page.locator('#chat-file-list')).toHaveAttribute('data-chat-file-bound', 'true');
    await page.locator(`[data-chat-file-id="${id}"]`).click();
    await expect(page.locator(`[data-chat-file-id="${id}"]`)).toHaveClass(/is-selected/);
    await settled(page.submissionQueue);
  }

  async function upload(page, queue, question) {
    await page.getByRole('radio', {name: 'Document', exact: true}).check();
    const response = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/upload');
    await page.locator('#chat-input input[type=file]').setInputFiles({
      name: 'control-owned.txt', mimeType: 'text/plain',
      buffer: Buffer.from('This owned observatory has seven telescopes.'),
    });
    expect((await response).ok()).toBeTruthy();
    await expect(page.locator('#chat-input .thumbnails .thumbnail-item')).toHaveCount(1);
    await send(page, question);
    await tailFinished(queue);
    const data = await evidence();
    return data.files.find(file => file.user === data.users['browser-controls']);
  }

  async function publicConversationPermissions() {
    const {page, queue} = await login('browser-other');
    try {
      const data = await evidence();
      const record = data.conversations.find(row => row.name === 'Owned public control');
      expect(record).toBeDefined();
      const id = record.id;
      await openControls(page);
      await page.locator('#conversation-dropdown input').click();
      await expect(page.getByRole('option', {name: 'Owned private control', exact: true})).toHaveCount(0);
      await page.getByRole('option', {name: 'Owned public control', exact: true}).click();
      await expect(page.locator('#answer-panel')).toContainText('PUBLIC FIXTURE');
      await expect(page.locator('[data-chat-file-id="owned-observatory"]')).toHaveCount(0);
      const before = (await evidence()).conversations.find(row => row.id === id);
      await page.locator('#rename-conv-button').click();
      await page.getByPlaceholder('Conversation name', {exact: true}).fill('Forbidden rename');
      await page.getByPlaceholder('Conversation name', {exact: true}).press('Enter');
      await expect(page.getByText(/outside the authenticated owner scope/).first()).toBeVisible();
      await page.locator('#delete-conv-button').click();
      await page.getByRole('button', {name: 'Delete', exact: true}).click();
      await expect.poll(async () => (await evidence()).callbacks.filter(item =>
        item.callback === 'ConversationControl.delete_conv' && item.event === 'return' && item.session_hash === queue.sessionHash
      ).length).toBe(1);
      expect((await evidence()).conversations.find(row => row.id === id)).toEqual(before);
      results.scenarios.push({name: 'public-read-nonowner-rename-delete-rejected', id, queue});
    } finally { await page.close(); }
  }

  async function conversationOperations() {
    const {page, queue} = await login('browser-controls');
    try {
      const unrelated = (await evidence()).conversations;
      const uploaded = await upload(page, queue, 'CONTROL FIRST question');
      expect(uploaded).toBeDefined();
      const first = (await ownedRows())[0];
      expect(first.name).toBe('Owned document discussion');
      await openControls(page);
      await rename(page, first.id, 'Control first');
      await page.locator('#new-conv-button').click();
      await expect.poll(async () => (await ownedRows()).length).toBe(2);
      await expect(page.locator('#answer-panel')).not.toContainText('CONTROL FIRST');
      const second = (await ownedRows()).find(row => row.id !== first.id);
      expect(second.data_source.messages || []).toEqual([]);
      await source(page, uploaded.id);
      await send(page, 'ISOLATED CONVERSATION CONTROL SECOND question');
      await tailFinished(queue, 2);
      expect((await ownedRows()).find(row => row.id === second.id).name).toBe('Isolated conversation');
      await rename(page, second.id, 'Control second');
      await choose(page, 'Control first');
      await expect(page.locator('#answer-panel')).toContainText('CONTROL FIRST');
      await expect(page.locator('#answer-panel')).not.toContainText('CONTROL SECOND');
      await choose(page, 'Control second');
      await expect(page.locator('#answer-panel')).toContainText('CONTROL SECOND');
      await page.reload();
      await page.locator('#chat-input textarea').waitFor({state: 'visible'});
      await openControls(page);
      await choose(page, 'Control first');
      await expect(page.locator('#answer-panel')).toContainText('CONTROL FIRST');
      await expect(page.locator('#citations-card')).toContainText(uploaded.name);
      const beforeCancel = (await evidence()).conversations;
      await page.locator('#delete-conv-button').click();
      await page.getByRole('button', {name: 'Cancel', exact: true}).click();
      await expect(page.getByRole('button', {name: 'Delete', exact: true})).toBeHidden();
      expect((await evidence()).conversations).toEqual(beforeCancel);
      const filesBeforeDelete = (await evidence()).files;
      await choose(page, 'Control second');
      await expect(page.locator('#answer-panel')).toContainText('CONTROL SECOND');
      await remove(page, second.id);
      await expect(page.locator('#conversation-dropdown input')).toHaveValue('Control first');
      await expect(page.locator('#answer-panel')).toContainText('CONTROL FIRST');
      await expect(page.locator('#answer-panel')).not.toContainText('CONTROL SECOND');
      await remove(page, first.id);
      await expect(page.locator('#conversation-dropdown input')).toHaveValue('');
      await expect(page.locator('#answer-panel')).not.toContainText('CONTROL FIRST');
      await expect(page.locator('#citations-card')).not.toContainText(uploaded.name);
      expect(await ownedRows()).toEqual([]);
      const after = await evidence();
      expect(after.conversations).toEqual(unrelated);
      expect(after.files).toEqual(filesBeforeDelete);
      for (const id of [first.id, second.id]) {
        assertFinalizerAndWebWrites(after.writes.filter(item => item.conversation_id === id), 1);
      }
      results.scenarios.push({name: 'new-cancel-same-source-restore-manual-auto-name-delete-last', ids: [first.id, second.id], queue});
    } finally {
      await page.screenshot({path: path.join(output, 'conversation-operations.png'), fullPage: true});
      await page.close();
    }
  }

  async function lateConversationOperations() {
    const {page, queue} = await login('browser-controls');
    try {
      const initial = await ownedRows();
      const file = (await evidence()).files.find(file => file.name === 'control-owned.txt');
      if (file) {
        await source(page, file.id);
        await send(page, 'HELD_STREAM late deletion');
      } else {
        // Standalone runs still upload through the browser before the held request.
        await upload(page, queue, 'SETUP source for a held request');
        await openControls(page);
        await page.locator('#new-conv-button').click();
        await expect.poll(async () => (await ownedRows()).length).toBe(initial.length + 2);
        const uploaded = (await evidence()).files.find(file => file.name === 'control-owned.txt');
        await source(page, uploaded.id);
        await send(page, 'HELD_STREAM late deletion');
      }
      await expect.poll(async () => (await (await fetch(base + '/owned-model-gate')).json()).started, {timeout: 15000}).toBe(true);
      await expect(page.locator('#answer-panel')).toContainText('The owned document says');
      const held = (await ownedRows()).at(-1);
      if (file) await openControls(page);
      await rename(page, held.id, 'Held conversation');
      await page.locator('#new-conv-button').click();
      await expect.poll(async () => (await ownedRows()).at(-1).id).not.toBe(held.id);
      const protectedRow = (await ownedRows()).at(-1);
      await rename(page, protectedRow.id, 'Protected view');
      await choose(page, 'Held conversation');
      await remove(page, held.id);
      // Selection following deletion is the service's original first-row rule.
      const beforeRelease = (await evidence()).conversations;
      const beforeTail = (await evidence()).callbacks.filter(item => item.callback === 'CompletionTail.persist' && item.session_hash === queue.sessionHash).length;
      expect((await fetch(base + '/owned-model-gate/release', {method: 'POST'})).ok).toBeTruthy();
      // The unchanged finalizer rejects the deleted row; its failed success edge
      // must never start the Web tail or recreate the conversation.
      await expect(page.getByText('No row was found when one was required', {exact: true}).first()).toBeVisible({timeout: 15000});
      expect((await evidence()).conversations).toEqual(beforeRelease);
      expect((await evidence()).callbacks.filter(item => item.callback === 'CompletionTail.persist' && item.session_hash === queue.sessionHash)).toHaveLength(beforeTail);
      await expect(page.locator('#answer-panel')).not.toContainText('HELD_STREAM');
      expect((await ownedRows()).some(row => row.id === held.id)).toBe(false);
      expect((await evidence()).writes.filter(item => item.conversation_id === protectedRow.id)).toEqual([]);
      results.scenarios.push({name: 'held-model-switch-delete-no-resurrection-or-view-overwrite', deleted: held.id, protected: protectedRow.id, queue});
    } finally {
      await fetch(base + '/owned-model-gate/release', {method: 'POST'});
      await page.screenshot({path: path.join(output, 'conversation-late.png'), fullPage: true});
      await page.close();
    }
  }

  return [conversationOperations, lateConversationOperations, publicConversationPermissions];
};

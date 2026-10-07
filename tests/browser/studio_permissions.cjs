// Public reads use the fixture's public conversation; every write goes through UI.
module.exports = function ({expect, login, evidence, settled, roles, results}) {
  async function selectPublic(page, queue) {
    await page.getByText('Conversation', {exact: true}).click();
    const tails = queue.filter(fn => fn === roles.conversation_select_tail).length;
    await page.locator('#conversation-dropdown input').fill('Owned public control');
    await page.getByRole('option', {name: 'Owned public control', exact: true}).click();
    await expect.poll(() => queue.filter(fn => fn === roles.conversation_select_tail).length).toBe(tails + 1);
    await settled(queue);
    await page.locator('#studio-notes-panel').getByText('Studio Notes', {exact: true}).click();
  }

  async function publicStudioPermissions() {
    const owner = await login('browser-owner');
    let row;
    try {
      await selectPublic(owner.page, owner.queue);
      await owner.page.locator('#studio-manual-note-title textarea').fill('Owner public Studio note');
      await owner.page.locator('#studio-manual-note-text textarea').fill('Only its owner may convert this saved note.');
      await owner.page.locator('#studio-save-manual-note').click();
      await expect.poll(async () => (await evidence()).conversations.find(item => item.name === 'Owned public control').data_source.mara_notebook?.notes.length).toBe(1);
      const uploaded = owner.page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/upload');
      await owner.page.locator('#quick-file input[type=file]').setInputFiles({name: 'r3d-public-artifact.txt', mimeType: 'text/plain', buffer: Buffer.from('Owned public artifact source: seven telescopes observe stars.')});
      expect((await uploaded).ok()).toBe(true);
      await expect(owner.page.locator('#quick-file-upload-status')).toContainText('Indexing completed.', {timeout: 30000});
      await expect(owner.page.locator('#index-0 .token')).toContainText('r3d-public-artifact.txt');
      await settled(owner.queue);
      await owner.page.locator('#studio-artifact-card-mindmap').click();
      await owner.page.locator('#studio-generate-artifact').click();
      await expect.poll(async () => (await evidence()).conversations.find(item => item.name === 'Owned public control').data_source.mara_notebook?.artifacts.length, {timeout: 45000}).toBe(1);
      row = (await evidence()).conversations.find(item => item.name === 'Owned public control');
      expect(row.data_source.mara_notebook.artifacts[0].status).toBe('ready');
    } finally { await owner.page.close(); }

    const {page, queue} = await login('browser-other');
    try {
      await selectPublic(page, queue);
      await expect(page.locator('#notebook-panel-card')).toContainText('Owner public Studio note');
      await expect(page.locator('.studio-artifact-result-row')).toContainText('Interactive Mind Map');
      const before = await evidence();
      await page.locator('#studio-manual-note-title textarea').fill('Forbidden note');
      await page.locator('#studio-manual-note-text textarea').fill('Must never persist');
      await page.locator('#studio-convert-note-id textarea').fill(row.data_source.mara_notebook.notes[0].note_id);
      for (const selector of ['#studio-save-manual-note', '#studio-save-latest-answer-note', '#studio-convert-note-source', '#studio-export-latest-artifact', '#studio-delete-latest-artifact']) {
        const count = queue.length;
        await page.locator(selector).click();
        await expect.poll(() => queue.length).toBeGreaterThan(count);
        await settled(queue);
        await expect(page.getByText('Notebook is unavailable.', {exact: true}).first()).toBeVisible();
        const current = await evidence();
        expect(current.conversations.find(item => item.id === row.id)).toEqual(row);
        expect(current.files).toEqual(before.files);
        expect(current.studio_exports).toEqual(before.studio_exports);
      }
      await page.locator('#studio-artifact-card-mindmap').click();
      const count = queue.length;
      await page.locator('#studio-generate-artifact').click();
      await expect.poll(() => queue.length).toBeGreaterThan(count);
      await settled(queue);
      await expect(page.getByText('Notebook is unavailable.', {exact: true}).first()).toBeVisible();
      expect((await evidence()).conversations.find(item => item.id === row.id)).toEqual(row);
      results.scenarios.push({name: 'Studio-public-read-nonowner-save-convert-export-delete-generate-denied', id: row.id, owner: row.user, reader: before.users['browser-other'], artifactId: row.data_source.mara_notebook.artifacts[0].artifact_id});
    } finally { await page.close(); }
  }
  return [publicStudioPermissions];
};

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
      row = (await evidence()).conversations.find(item => item.name === 'Owned public control');
    } finally { await owner.page.close(); }

    const {page, queue} = await login('browser-other');
    try {
      await selectPublic(page, queue);
      await expect(page.locator('#notebook-panel-card')).toContainText('Owner public Studio note');
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
      results.scenarios.push({name: 'Studio-public-read-nonowner-save-convert-export-delete-denied', id: row.id, owner: row.user, reader: before.users['browser-other']});
    } finally { await page.close(); }
  }
  return [publicStudioPermissions];
};

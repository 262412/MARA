// All writes and deletes use the real UI. The observer only reads storage;
// its release endpoint controls the deterministic embedding boundary.
module.exports = function ({expect, login, evidence, settled, send, tailFinished, results, base}) {
  const manager = page => page.locator('#indices-tab');
  const snapshot = async () => (await fetch(base + '/owned-indexing-lifetime')).json();
  async function upload(page, name, body, quick = false) {
    if (!quick) {
      await page.getByRole('tab', {name: 'files', exact: true}).click();
      await manager(page).getByRole('tab', {name: 'Upload Files', exact: true}).click();
    }
    const input = quick ? page.locator('#quick-file input[type=file]') : manager(page).locator('input[type=file][multiple]');
    const [response] = await Promise.all([
      page.waitForResponse(item => item.request().method() === 'POST' && new URL(item.url()).pathname === '/upload'),
      input.setInputFiles({name, mimeType: 'text/plain', buffer: Buffer.from(body)}),
    ]);
    expect(response.ok()).toBe(true);
    if (!quick) await manager(page).getByRole('button', {name: 'Upload and Index', exact: true}).click();
  }
  async function selected(page, name) {
    await page.getByRole('tab', {name: 'files', exact: true}).click();
    const filter = manager(page).getByLabel('Filter by name:');
    await filter.fill(name); await filter.press('Enter');
    await manager(page).getByRole('tab', {name: 'Files', exact: true}).click();
    const rows = page.locator('#file_list_view svelte-virtual-table-viewport');
    await expect(rows).toContainText(name, {timeout: 20000});
    await rows.getByText(name, {exact: true}).click();
    await expect(manager(page)).toContainText('Selected file: ' + name);
  }
  const targets = (data, id) => data.persistence.relations.filter(row => row.source_id === id && row.relation_type === 'document').map(row => row.target_id);

  async function indexingDeleteThenReplaceDuringEmbedding() {
    const original = await login('browser-controls');
    let second;
    const name = 'r5b-closeout-replacement.txt';
    try {
      await upload(original.page, name, 'R5B_DELETE_HELD seven telescopes.');
      await expect.poll(async () => (await snapshot()).deletion_embedding_started, {timeout: 30000}).toBe(true);
      const old = (await evidence()).files.find(file => file.name === name);
      const before = await snapshot();
      const oldTargets = targets(before, old.id);
      expect(oldTargets.length).toBeGreaterThan(0);
      second = await login('browser-controls');
      await selected(second.page, name);
      await manager(second.page).getByRole('button', {name: 'Delete', exact: true}).click();
      await expect.poll(async () => (await evidence()).files.some(file => file.id === old.id), {timeout: 20000}).toBe(false);
      await settled(second.queue);
      await second.page.getByRole('tab', {name: 'chat', exact: true}).click();
      await upload(second.page, name, 'Replacement owned source with seven telescopes.', true);
      await expect.poll(async () => (await evidence()).files.find(file => file.name === name)?.id, {timeout: 30000}).toBeTruthy();
      await settled(second.queue);
      const replacement = (await evidence()).files.find(file => file.name === name);
      expect(replacement.id).not.toBe(old.id);
      const currentTargets = targets(await snapshot(), replacement.id);
      expect(currentTargets.length).toBeGreaterThan(0);
      await fetch(base + '/owned-indexing-lifetime/release-deletion', {method: 'POST'});
      await expect(manager(original.page).getByLabel('Upload result', {exact: true})).toHaveValue(/Source removed during indexing/, {timeout: 30000});
      await settled(original.queue);
      const after = await snapshot();
      expect(after.persistence.relations.some(row => row.source_id === old.id)).toBe(false);
      expect(oldTargets.some(id => after.persistence.vector_ids.includes(id) || after.persistence.document_ids.includes(id))).toBe(false);
      expect(targets(after, replacement.id)).toEqual(currentTargets);
      expect(currentTargets.every(id => after.persistence.vector_ids.includes(id) && after.persistence.document_ids.includes(id))).toBe(true);
      results.scenarios.push({name: 'real-ui-delete-replace-reject-late-writer', old: old.id, replacement: replacement.id, before, after});
    } finally {
      await fetch(base + '/owned-indexing-lifetime/release-deletion', {method: 'POST'});
      await original.page.close();
      if (second) await second.page.close();
    }
  }

  async function indexingSharedCacheTwoOwnersSurviveDeletion() {
    const first = await login('browser-controls');
    const second = await login('browser-other');
    const name = 'r5b-closeout-shared.txt';
    const body = 'Shared cached report: the observatory has seven telescopes.';
    try {
      for (const session of [first, second]) {
        await upload(session.page, name, body);
        await expect(manager(session.page).getByLabel('Upload result', {exact: true})).toHaveValue(/✅.*r5b-closeout-shared.txt/, {timeout: 30000});
        await settled(session.queue);
      }
      const data = await evidence();
      const a = data.files.find(file => file.name === name && file.user === data.users['browser-controls']);
      const b = data.files.find(file => file.name === name && file.user === data.users['browser-other']);
      const stored = await snapshot();
      expect(stored.parses.find(row => row.file_id === b.id).cache_hit).toBe(true);
      expect(stored.parses.find(row => row.file_id === a.id).parser_ids).toEqual(stored.parses.find(row => row.file_id === b.id).parser_ids);
      const firstTargets = targets(stored, a.id), secondTargets = targets(stored, b.id);
      expect(firstTargets.length).toBeGreaterThan(0);
      expect(secondTargets.length).toBeGreaterThan(0);
      expect(firstTargets.some(id => secondTargets.includes(id))).toBe(false);
      await selected(first.page, name);
      await manager(first.page).getByRole('button', {name: 'Delete', exact: true}).click();
      await expect.poll(async () => (await evidence()).files.some(file => file.id === a.id), {timeout: 20000}).toBe(false);
      await selected(second.page, name);
      await manager(second.page).getByRole('button', {name: 'Go to Chat', exact: true}).click();
      await expect(second.page.locator('#index-0 .token')).toContainText(name);
      await send(second.page, 'How many telescopes are there in this shared report?');
      await tailFinished(second.queue);
      await expect(second.page.locator('#answer-panel')).toContainText('seven telescopes');
      await expect(second.page.locator('#citations-card')).toContainText(name);
      const after = await snapshot();
      expect(targets(after, b.id)).toEqual(secondTargets);
      expect(secondTargets.every(id => after.persistence.vector_ids.includes(id) && after.persistence.document_ids.includes(id))).toBe(true);
      expect(firstTargets.some(id => after.persistence.vector_ids.includes(id) || after.persistence.document_ids.includes(id))).toBe(false);
      results.scenarios.push({name: 'real-ui-two-owner-cache-delete-surviving-retrieval-and-citation', first: a.id, second: b.id, before: stored, after});
    } finally { await first.page.close(); await second.page.close(); }
  }
  return [indexingDeleteThenReplaceDuringEmbedding, indexingSharedCacheTwoOwnersSurviveDeletion];
};

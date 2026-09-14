// Real index management controls; fixture metadata is read only for assertions.
const fs = require('node:fs');
const path = require('node:path');

module.exports = function ({expect, login, evidence, settled, send, tailFinished, results, output, base}) {
  const manager = page => page.locator('#indices-tab');
  const ownerFiles = (data, username) => data.files.filter(file => file.user === data.users[username]);

  async function openManager(page) {
    await page.getByRole('tab', {name: 'files', exact: true}).click();
    await expect(manager(page).getByRole('button', {name: 'Upload and Index', exact: true})).toBeVisible();
  }

  async function upload(page, names, {reindex = false} = {}) {
    const queue = page.submissionQueue;
    const before = queue.length;
    const oldIds = (await evidence()).files.filter(file => names.includes(file.name)).map(file => file.id);
    await manager(page).getByRole('tab', {name: 'Upload Files', exact: true}).click();
    const [uploaded] = await Promise.all([
      page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/upload'),
      manager(page).locator('input[type=file][multiple]').setInputFiles(names.map(name => ({
        name, mimeType: 'text/plain', buffer: Buffer.from('Owned management source: seven telescopes. ' + (reindex ? 'Reindexed revision two.' : name)),
      }))),
    ]);
    expect(uploaded.ok()).toBe(true);
    if (reindex) {
      await manager(page).getByText('Advanced indexing options', {exact: true}).click();
      await manager(page).getByRole('checkbox', {name: 'Force reindex file'}).check();
    }
    await manager(page).getByRole('button', {name: 'Upload and Index', exact: true}).click();
    await expect(manager(page).getByLabel('Upload result', {exact: true})).toHaveValue(new RegExp(names.at(-1)), {timeout: 30000});
    if (reindex) {
      await expect.poll(async () => (await evidence()).files.filter(file => names.includes(file.name) && !oldIds.includes(file.id)).length, {timeout: 30000}).toBe(names.length);
    }
    await expect.poll(() => queue.length).toBeGreaterThan(before);
    await settled(queue);
    // Reindex keeps the displayed filename while replacing its source ID.
    // The old upload-result text can match before the refresh tail arrives.
    const indexed = (await evidence()).files.filter(file => names.includes(file.name));
    for (const file of indexed) {
      const row = page.locator('#file_list_view svelte-virtual-table-viewport tr')
        .filter({hasText: file.name});
      await expect(row).toContainText(file.id, {timeout: 30000});
    }
  }

  async function selectFile(page, filename) {
    const filter = manager(page).getByLabel('Filter by name:');
    await filter.fill(filename);
    await filter.press('Enter');
    await manager(page).getByRole('tab', {name: 'Files', exact: true}).click();
    await page.locator('#file_list_view svelte-virtual-table-viewport').getByText(filename, {exact: true}).click();
    await expect(manager(page)).toContainText('Selected file: ' + filename);
    await expect(manager(page).getByRole('button', {name: 'Delete', exact: true})).toBeVisible();
  }

  async function indexManagement() {
    const username = 'browser-controls';
    const {page, queue} = await login(username);
    const names = ['r3d-management-a.txt', 'r3d-management-b.txt'];
    try {
      await openManager(page);
      await upload(page, names);
      let data = await evidence();
      let added = ownerFiles(data, username).filter(file => names.includes(file.name));
      expect(added).toHaveLength(2);
      const firstId = added.find(file => file.name === names[0]).id;
      await selectFile(page, names[0]);
      await manager(page).getByRole('button', {name: 'Close', exact: true}).click();
      await expect(manager(page)).toContainText('Selected file: (please select above)');
      await expect(manager(page).getByRole('button', {name: 'Delete', exact: true})).toHaveCount(0);
      expect((await evidence()).files.some(file => file.id === firstId)).toBe(true);
      await upload(page, [names[0]], {reindex: true});
      data = await evidence();
      added = ownerFiles(data, username).filter(file => names.includes(file.name));
      expect(added).toHaveLength(2);
      const revised = added.find(file => file.name === names[0]);
      expect(revised).toBeDefined();
      await selectFile(page, names[0]);
      await manager(page).getByRole('button', {name: 'Go to Chat', exact: true}).click();
      await expect(page.locator('#chat-input textarea')).toBeVisible();
      await expect(page.locator('#index-0 .token')).toContainText(names[0]);
      await expect(page.locator(`[data-chat-file-id="${revised.id}"]`)).toHaveClass(/is-selected/);
      await openManager(page);
      await selectFile(page, names[0]);
      await manager(page).getByRole('button', {name: 'Delete', exact: true}).click();
      await expect.poll(async () => (await evidence()).files.some(file => file.id === revised.id), {timeout: 30000}).toBe(false);
      await settled(queue);
      await page.getByRole('tab', {name: 'chat', exact: true}).click();
      await expect(page.locator(`[data-chat-file-id="${revised.id}"]`)).toHaveCount(0);
      results.previewRevocations ||= [];
      results.previewRevocations.push({sessionHash: queue.sessionHash, fileId: revised.id});
      await openManager(page);
      const filter = manager(page).getByLabel('Filter by name:');
      await filter.fill('r3d-management-'); await filter.press('Enter');
      await expect(page.locator('#file_list_view svelte-virtual-table-viewport')).toContainText(names[1]);
      await manager(page).getByText('Advance options', {exact: true}).click();
      await manager(page).getByRole('button', {name: 'Delete all files', exact: true}).click();
      await expect(manager(page).getByRole('button', {name: 'Confirm delete', exact: true})).toBeVisible();
      await manager(page).getByRole('button', {name: 'Cancel', exact: true}).click();
      expect(ownerFiles(await evidence(), username).some(file => file.name === names[1])).toBe(true);
      await manager(page).getByRole('button', {name: 'Delete all files', exact: true}).click();
      const retained = (await evidence()).files.filter(file => !names.includes(file.name));
      await manager(page).getByRole('button', {name: 'Confirm delete', exact: true}).click();
      await expect.poll(async () => ownerFiles(await evidence(), username).filter(file => names.includes(file.name))).toEqual([]);
      const after = await evidence();
      expect(after.files.filter(file => retained.some(row => row.id === file.id))).toEqual(retained);
      results.scenarios.push({name: 'real-index-management-upload-select-close-reindex-single-delete-bulk-cancel-confirm', firstId, revisedId: revised.id, retained: retained.map(file => file.id)});
    } finally {
      fs.writeFileSync(path.join(output, 'index-management.html'), await manager(page).innerHTML());
      await page.screenshot({path: path.join(output, 'index-management.png'), fullPage: true});
      await page.close();
    }
  }

  async function indexGroups() {
    const username = 'browser-controls';
    const {page, queue} = await login(username);
    const names = ['r3d-group-a.txt', 'r3d-group-b.txt'];
    try {
      await openManager(page);
      await upload(page, names);
      await manager(page).getByRole('tab', {name: 'Groups', exact: true}).click();
      await manager(page).getByRole('button', {name: 'Add', exact: true}).click();
      await manager(page).getByLabel('Group name', {exact: true}).fill('Owned R3-D group');
      const attached = manager(page).locator('label').filter({hasText: 'Attached files'}).locator('input');
      for (const name of names) {
        await attached.fill(name);
        await page.getByRole('option', {name, exact: true}).click();
      }
      await manager(page).getByRole('button', {name: 'Save', exact: true}).click();
      await expect.poll(async () => (await evidence()).groups.find(group => group.name === 'Owned R3-D group')?.data.files.length).toBe(2);
      const group = (await evidence()).groups.find(group => group.name === 'Owned R3-D group');
      await manager(page).locator('svelte-virtual-table-viewport').getByText('Owned R3-D group', {exact: true}).click();
      await expect(manager(page).getByLabel('Group name', {exact: true})).toHaveValue('Owned R3-D group');
      await manager(page).getByRole('button', {name: 'Go to Chat', exact: true}).click();
      await expect(page.locator('#chat-input textarea')).toBeVisible();
      await expect(page.locator('#index-0 .token')).toContainText('Owned R3-D group');
      await expect(page.locator('#chat-file-list .is-selected')).toHaveCount(2);
      await page.getByRole('radio', {name: 'Document', exact: true}).check();
      await send(page, 'GROUP SOURCES: summarize the two owned documents');
      await tailFinished(queue);
      let data = await evidence();
      const conversationId = data.states.find(state => state.session_hash === queue.sessionHash)._request_completion.conversation_id;
      await page.locator('#studio-artifact-card-mindmap').click();
      await page.locator('#studio-artifact-scope input').click();
      await page.getByRole('option', {name: 'multi-document', exact: true}).click();
      await page.locator('#studio-generate-artifact').click();
      await expect.poll(async () => (await evidence()).conversations.find(row => row.id === conversationId).data_source.mara_notebook?.artifacts.length, {timeout: 45000}).toBe(1);
      const artifact = (await evidence()).conversations.find(row => row.id === conversationId).data_source.mara_notebook.artifacts[0];
      expect(artifact.status).toBe('ready');
      expect([...artifact.source_scope.source_ids].sort()).toEqual([...group.data.files].sort());
      const other = await login('browser-other');
      try {
        await openManager(other.page);
        await other.page.locator('#indices-tab').getByRole('tab', {name: 'Groups', exact: true}).click();
        await expect(other.page.locator('#indices-tab svelte-virtual-table-viewport').getByText('Owned R3-D group', {exact: true})).toHaveCount(0);
      } finally { await other.page.close(); }
      await openManager(page);
      await manager(page).getByRole('tab', {name: 'Groups', exact: true}).click();
      const beforeSelection = queue.length;
      await manager(page).locator('svelte-virtual-table-viewport').getByText('Owned R3-D group', {exact: true}).click();
      await expect.poll(() => queue.length).toBeGreaterThan(beforeSelection);
      await settled(queue);
      await manager(page).getByLabel('Group name', {exact: true}).fill('Updated R3-D group');
      await manager(page).getByRole('button', {name: 'Save', exact: true}).click();
      await expect.poll(async () => (await evidence()).groups.find(row => row.id === group.id)?.name).toBe('Updated R3-D group');
      await manager(page).locator('svelte-virtual-table-viewport').getByText('Updated R3-D group', {exact: true}).click();
      await manager(page).getByRole('button', {name: 'Close', exact: true}).click();
      expect((await evidence()).groups.some(row => row.id === group.id)).toBe(true);
      await manager(page).locator('svelte-virtual-table-viewport').getByText('Updated R3-D group', {exact: true}).click();
      await manager(page).getByRole('button', {name: 'Delete', exact: true}).click();
      await expect.poll(async () => (await evidence()).groups.some(row => row.id === group.id)).toBe(false);
      await settled(queue);
      data = await evidence();
      expect(group.data.files.every(id => data.files.some(file => file.id === id))).toBe(true);
      results.scenarios.push({name: 'real-group-create-select-chat-update-close-delete-with-owner-isolation', groupId: group.id, retainedFiles: group.data.files});
    } finally {
      fs.writeFileSync(path.join(output, 'index-groups.html'), await manager(page).innerHTML());
      await page.screenshot({path: path.join(output, 'index-groups.png'), fullPage: true});
      await page.close();
    }
  }

  async function deletedSourcePreviewRevocation() {
    const {page, queue} = await login('browser-controls');
    const key = 'revoked-source-preview';
    const name = 'r3d-revoked-preview.txt';
    async function gate(suffix, body) {
      const response = await fetch(base + '/owned-file-browser-gate' + suffix, body === undefined ? {} : {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
      });
      expect(response.ok).toBe(true);
      return response.json();
    }
    try {
      await openManager(page);
      await upload(page, [name]);
      const before = await evidence();
      const file = ownerFiles(before, 'browser-controls').find(item => item.name === name);
      await selectFile(page, name);
      await manager(page).getByRole('button', {name: 'Go to Chat', exact: true}).click();
      await expect(page.locator(`[data-chat-file-id="${file.id}"]`)).toHaveClass(/is-selected/);
      await gate('/arm', {key, callback: 'ChatPagePreviewController.on_preview_tick', event: 'call', username: 'browser-controls', session_hash: queue.sessionHash, file_id: file.id});
      await expect.poll(async () => (await gate(''))[key]?.entered, {timeout: 15000}).toBe(true);
      await openManager(page);
      await selectFile(page, name);
      await manager(page).getByRole('button', {name: 'Delete', exact: true}).click();
      await expect.poll(async () => (await evidence()).files.some(item => item.id === file.id), {timeout: 30000}).toBe(false);
      await expect(page.locator(`[data-chat-file-id="${file.id}"]`)).toHaveCount(0, {timeout: 20000});
      await gate('/release/' + key, {});
      await expect.poll(async () => (await evidence()).callbacks.filter(item => item.event === 'exception' && item.session_hash === queue.sessionHash && item.file_id === file.id).length).toBe(1);
      await settled(queue);
      await page.getByRole('tab', {name: 'chat', exact: true}).click();
      await expect(page.locator('#index-0 .token')).toHaveCount(0);
      expect((await evidence()).files).toEqual(before.files.filter(item => item.id !== file.id));
      results.previewRevocations ||= [];
      results.previewRevocations.push({sessionHash: queue.sessionHash, fileId: file.id});
      results.scenarios.push({name: 'deleted-owner-source-rejects-held-preview-without-reading-or-restoring-it', fileId: file.id});
    } finally {
      await gate('/release/' + key, {});
      await page.close();
    }
  }

  return [indexManagement, indexGroups, deletedSourcePreviewRevocation];
};

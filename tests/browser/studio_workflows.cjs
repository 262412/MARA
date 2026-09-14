const fs = require('node:fs');
const path = require('node:path');

module.exports = function ({expect, login, evidence, send, tailFinished, settled, initialized, roles, results, output, base, assertFinalizerAndWebWrites}) {
  const notebook = row => row.data_source.mara_notebook || {notes: [], artifacts: []};

  async function createConversation(page, queue, name) {
    await page.getByRole('radio', {name: 'Document', exact: true}).check();
    const [uploaded] = await Promise.all([
      page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/upload'),
      page.locator('#chat-input input[type=file]').setInputFiles({
        name, mimeType: 'text/plain', buffer: Buffer.from('An owned observatory has seven telescopes. Astronomers track stars and planets.'),
      }),
    ]);
    expect(uploaded.ok()).toBe(true);
    await expect(page.locator('#chat-input .thumbnails .thumbnail-item')).toHaveCount(1);
    await send(page, 'STUDIO SOURCE: summarize this document');
    await tailFinished(queue);
    const data = await evidence();
    const context = data.states.find(state => state.session_hash === queue.sessionHash)._request_completion;
    const row = data.conversations.find(item => item.id === context.conversation_id);
    expect(row.data_source.messages).toHaveLength(1);
    await page.getByText('Conversation', {exact: true}).click();
    await page.locator('#rename-conv-button').click();
    const nameInput = page.getByPlaceholder('Conversation name', {exact: true});
    await nameInput.fill(name);
    await nameInput.press('Enter');
    await expect.poll(async () => (await getRow(row.id)).name).toBe(name);
    await expect(nameInput).toBeHidden();
    await settled(queue);
    await page.getByText('Conversation', {exact: true}).click();
    return row.id;
  }

  async function getRow(id) {
    return (await evidence()).conversations.find(row => row.id === id);
  }

  async function openNotes(page) {
    await page.locator('#studio-notes-panel').getByText('Studio Notes', {exact: true}).click();
    await expect(page.locator('#studio-manual-note-text textarea')).toBeVisible();
  }

  async function chooseConversation(page, queue, name) {
    const tails = queue.filter(fn => fn === roles.conversation_select_tail).length;
    await page.locator('#conversation-dropdown input').fill(name);
    await page.getByRole('option', {name, exact: true}).click();
    await expect.poll(() => queue.filter(fn => fn === roles.conversation_select_tail).length).toBe(tails + 1);
    await settled(queue);
  }

  async function control(suffix, body) {
    const response = await fetch(base + '/owned-file-browser-gate' + suffix, body === undefined ? {} : {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
    });
    expect(response.ok).toBe(true);
    return response.json();
  }

  async function studioNotesAndArtifact() {
    const {page, queue} = await login('browser-controls');
    try {
      const id = await createConversation(page, queue, 'r3d-studio-source.txt');
      await openNotes(page);
      await page.locator('#studio-save-manual-note').click();
      await settled(queue);
      expect(notebook(await getRow(id)).notes).toHaveLength(0);
      await page.locator('#studio-manual-note-title textarea').fill('Owned <orbit> & notes');
      await page.locator('#studio-manual-note-text textarea').fill('Seven telescopes observe stars. This is an owned Studio note.');
      await page.locator('#studio-save-manual-note').click();
      await expect(page.locator('#notebook-panel-card')).toContainText('Owned <orbit> & notes');
      let row = await getRow(id);
      const note = notebook(row).notes[0];
      expect(note.text).toContain('Seven telescopes');
      expect(await page.locator('#notebook-panel-card orbit').count()).toBe(0);
      await page.locator('#studio-save-latest-answer-note').click();
      await expect.poll(async () => notebook(await getRow(id)).notes.length).toBe(2);
      const answerNote = notebook(await getRow(id)).notes.find(item => item.source !== 'manual');
      expect(answerNote.text).toContain('seven telescopes');
      expect(answerNote.citation_refs.join(' ')).toContain('r3d-studio-source.txt');
      // The existing UI asks for a Note ID; use the ID of this actual saved note.
      await page.locator('#studio-convert-note-id textarea').fill(note.note_id);
      await page.locator('#studio-convert-note-source').click();
      await expect.poll(async () => notebook(await getRow(id)).notes.find(item => item.note_id === note.note_id)?.indexed_source_ids?.length, {timeout: 30000}).toBe(1);
      row = await getRow(id);
      const indexed = notebook(row).notes.find(item => item.note_id === note.note_id);
      const data = await evidence();
      expect(data.files.some(file => file.id === indexed.indexed_source_ids[0] && file.user === row.user)).toBe(true);
      const before = notebook(row);
      await page.reload();
      await page.locator('#chat-input textarea').waitFor({state: 'visible'});
      await initialized(queue);
      await page.getByText('Conversation', {exact: true}).click();
      const tails = queue.filter(fn => fn === roles.conversation_select_tail).length;
      await page.locator('#conversation-dropdown input').fill(row.name);
      await page.getByRole('option', {name: row.name, exact: true}).click();
      await expect.poll(() => queue.filter(fn => fn === roles.conversation_select_tail).length).toBe(tails + 1);
      await settled(queue);
      await expect(page.locator('#notebook-panel-card')).toContainText('Owned <orbit> & notes');
      expect(notebook(await getRow(id))).toEqual(before);
      await page.locator('#studio-artifact-card-mindmap').click();
      await expect(page.locator('#studio-artifact-detail-panel')).toBeVisible();
      await page.locator('#studio-artifact-detail-back').click();
      await expect(page.locator('#studio-artifact-selector-panel')).toBeVisible();
      expect(notebook(await getRow(id)).artifacts).toHaveLength(0);
      await page.locator('#studio-artifact-card-mindmap').click();
      await page.locator('#studio-generate-artifact').click();
      await expect.poll(async () => notebook(await getRow(id)).artifacts.length, {timeout: 45000}).toBe(1);
      row = await getRow(id);
      const artifact = notebook(row).artifacts[0];
      expect(artifact.type).toBe('mindmap');
      expect(artifact.status).toBe('ready');
      await expect(page.locator('#notebook-panel-card')).toContainText('1 saved');
      await expect(page.locator('.studio-artifact-result-row')).toContainText('Interactive Mind Map');
      await page.locator('#studio-save-latest-artifact-note').click();
      await expect.poll(async () => notebook(await getRow(id)).notes.length).toBe(3);
      await page.locator('#studio-export-latest-artifact').click();
      await expect.poll(async () => notebook(await getRow(id)).artifacts[0].exports?.length).toBe(1);
      row = await getRow(id);
      const exported = (await evidence()).studio_exports.find(item => item.artifact_id === artifact.artifact_id);
      expect(exported.bytes).toBeGreaterThan(0);
      expect(exported.text).toContain('Interactive Mind Map');
      await expect(page.locator('.studio-artifact-result-row')).toContainText('Interactive Mind Map');
      await page.locator('.studio-artifact-result-row').click();
      await expect(page.locator('[data-kg-viewer-overlay="true"]')).toBeVisible();
      await page.locator('[data-kg-node-role="knowledge_point"]').first().click();
      await expect(page.locator('#kg-answer-hint')).toContainText('Knowledge Graph Context');
      await expect(page.locator('[data-kg-viewer-overlay="true"]')).toBeHidden();
      await expect(page.locator('#chat-input textarea')).not.toHaveValue('');
      const graphQuestion = await page.locator('#chat-input textarea').inputValue();
      const priorTails = queue.filter(fn => fn === roles.persist).length;
      await send(page, graphQuestion);
      await expect.poll(() => queue.filter(fn => fn === roles.persist).length).toBe(priorTails + 1);
      await expect.poll(async () => (await evidence()).callbacks.filter(item =>
        item.callback === 'CompletionTail.persist' && item.event === 'return' && item.session_hash === queue.sessionHash
      ).length).toBe(1);
      await expect(page.locator('#citations-card')).toContainText('r3d-studio-source.txt');
      const linked = await getRow(id);
      expect(linked.data_source.messages).toHaveLength(2);
      expect(linked.data_source.retrieval_messages).toHaveLength(2);
      expect(linked.data_source.retrieval_messages.every(refs => refs.includes('r3d-studio-source.txt'))).toBe(true);
      expect(linked.data_source.messages.at(-1)[0]).toContain(graphQuestion);
      expect(linked.data_source.retrieval_messages.at(-1)).toContain('r3d-studio-source.txt');
      expect(linked.data_source.origin).toBe('web');
      assertFinalizerAndWebWrites((await evidence()).writes.filter(write => write.conversation_id === id), 2);
      expect(notebook(linked).artifacts).toEqual(notebook(row).artifacts);
      await page.reload();
      await page.locator('#chat-input textarea').waitFor({state: 'visible'});
      await initialized(queue);
      await page.getByText('Conversation', {exact: true}).click();
      await chooseConversation(page, queue, row.name);
      expect(notebook(await getRow(id)).artifacts).toEqual(notebook(row).artifacts);
      await expect(page.locator('.studio-artifact-result-row')).toContainText('Interactive Mind Map');
      expect((await getRow(id)).data_source.messages).toEqual(linked.data_source.messages);
      results.scenarios.push({name: 'Studio-real-upload-note-answer-note-source-restore-artifact-cancel-generate-save-export-graph-send', id, noteId: note.note_id, indexedId: indexed.indexed_source_ids[0], artifact: notebook(row).artifacts[0], graphQuestion, messages: linked.data_source.messages});
    } finally {
      fs.writeFileSync(path.join(output, 'studio-workflow.html'), await page.locator('#chat-info-panel').innerHTML());
      await page.screenshot({path: path.join(output, 'studio-workflow.png'), fullPage: true});
      await page.close();
    }
  }

  async function studioLateGeneration() {
    const {page, queue} = await login('browser-controls');
    const key = 'studio-late-mindmap';
    try {
      const id = await createConversation(page, queue, 'r3d-studio-late.txt');
      await control('/arm', {key, callback: 'generate_studio_artifact_panel_update', username: 'browser-controls', session_hash: queue.sessionHash});
      await page.locator('#studio-artifact-card-mindmap').click();
      await page.locator('#studio-generate-artifact').click();
      await expect.poll(async () => (await control(''))[key]?.entered).toBe(true);
      expect(notebook(await getRow(id)).artifacts).toHaveLength(1);
      await page.getByText('Conversation', {exact: true}).click();
      const beforeIds = (await evidence()).conversations.map(row => row.id);
      await page.locator('#new-conv-button').click();
      await expect.poll(async () => (await evidence()).conversations.filter(row => !beforeIds.includes(row.id)).length).toBe(1);
      const current = (await evidence()).conversations.find(row => !beforeIds.includes(row.id));
      await expect(page.locator('#answer-panel .prose')).toHaveText('');
      await expect(page.locator('#notebook-panel-card')).toContainText('No artifacts');
      await expect.poll(async () => (await getRow(current.id)).data_source.graph_source_ids).toEqual([]);
      const protectedData = (await getRow(current.id)).data_source;
      await control('/release/' + key, {});
      await expect.poll(async () => (await control(''))[key]?.completed).toBe(true);
      await settled(queue);
      await expect(page.locator('#answer-panel .prose')).toHaveText('');
      await expect(page.locator('.studio-artifact-result-row')).toHaveCount(0);
      expect(notebook(await getRow(id)).artifacts).toHaveLength(1);
      expect((await getRow(current.id)).data_source).toEqual(protectedData);
      results.scenarios.push({name: 'Studio-late-generation-does-not-overwrite-new-conversation', generated: id, current: current.id});
    } finally {
      await control('/release/' + key, {});
      await page.screenshot({path: path.join(output, 'studio-late.png'), fullPage: true});
      await page.close();
    }
  }

  async function studioNoSourceFailure() {
    const {page, queue} = await login('browser-controls');
    try {
      await page.getByText('Conversation', {exact: true}).click();
      const before = (await evidence()).conversations.map(row => row.id);
      await page.locator('#new-conv-button').click();
      await expect.poll(async () => (await evidence()).conversations.filter(row => !before.includes(row.id)).length).toBe(1);
      const row = (await evidence()).conversations.find(row => !before.includes(row.id));
      await expect(page.locator('#index-0 .token')).toHaveCount(0);
      await settled(queue);
      await page.locator('#studio-artifact-card-mindmap').click();
      await page.locator('#studio-generate-artifact').click();
      await expect.poll(async () => notebook(await getRow(row.id)).artifacts.length).toBe(1);
      const artifact = notebook(await getRow(row.id)).artifacts[0];
      expect(artifact.status).toBe('failed');
      expect(artifact.generation.error).toContain('Select at least one source');
      expect(artifact.source_scope.source_ids).toEqual([]);
      await expect(page.locator('.studio-artifact-result-row')).toContainText('Mind Map Failed');
      expect((await getRow(row.id)).data_source.messages || []).toEqual([]);
      results.scenarios.push({name: 'Studio-no-source-failure-is-visible-and-owned', id: row.id, artifact});
    } finally { await page.close(); }
  }

  async function studioDisconnectAndRestore() {
    const first = await login('browser-controls');
    const key = 'studio-disconnect-mindmap';
    let recovered;
    try {
      const id = await createConversation(first.page, first.queue, 'r3d-studio-disconnect.txt');
      await control('/arm', {key, callback: 'generate_studio_artifact_panel_update', username: 'browser-controls', session_hash: first.queue.sessionHash});
      await first.page.locator('#studio-artifact-card-mindmap').click();
      await first.page.locator('#studio-generate-artifact').click();
      await expect.poll(async () => (await control(''))[key]?.entered).toBe(true);
      const saved = await getRow(id);
      expect(notebook(saved).artifacts).toHaveLength(1);
      await first.page.close();
      await control('/release/' + key, {});
      await expect.poll(async () => (await control(''))[key]?.completed).toBe(true);
      recovered = await login('browser-controls');
      await recovered.page.getByText('Conversation', {exact: true}).click();
      await chooseConversation(recovered.page, recovered.queue, saved.name);
      await expect(recovered.page.locator('.studio-artifact-result-row')).toContainText('Interactive Mind Map');
      expect((await getRow(id)).data_source).toEqual(saved.data_source);
      results.scenarios.push({name: 'Studio-disconnect-after-save-fresh-browser-restores-one-artifact', id, artifactId: notebook(saved).artifacts[0].artifact_id});
    } finally {
      await control('/release/' + key, {});
      if (!first.page.isClosed()) await first.page.close();
      if (recovered) await recovered.page.close();
    }
  }

  return [studioNotesAndArtifact, studioLateGeneration, studioNoSourceFailure, studioDisconnectAndRestore];
};

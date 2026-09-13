// Full production App regression: model/CDN boundaries only are deterministic.
const { chromium, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const output = process.argv[2];
const { roles, initial_selection_events } = JSON.parse(fs.readFileSync(path.join(output, 'ready.json')));
const base = 'http://127.0.0.1:8768';
const results = { scenarios: [], errors: [], completions: [] };
let browser;

async function evidence() {
  const response = await fetch(base + '/owned-evidence');
  expect(response.ok).toBeTruthy();
  return response.json();
}

async function login(username = 'browser-owner') {
  const page = await browser.newPage({locale: 'en-US', viewport: {width: 1600, height: 1200}});
  page.on('pageerror', error => results.errors.push(String(error)));
  const queue = [];
  queue.requestOrder = new WeakMap();
  queue.requestIds = [];
  queue.navigationStart = 0;
  page.on('framenavigated', frame => {
    if (frame === page.mainFrame()) queue.navigationStart = queue.length;
  });
  queue.page = page;
  page.on('request', request => {
    if (request.url().includes('/queue/join')) {
      const payload = request.postDataJSON();
      queue.requestOrder.set(request, queue.length);
      queue.push(payload.fn_index);
      queue.sessionHash = payload.session_hash;
    }
  });
  page.on('response', async response => {
    if (new URL(response.url()).pathname === '/queue/join' && response.ok()) {
      const body = await response.json();
      queue.requestIds[queue.requestOrder.get(response.request())] = body.event_id;
    }
  });
  await page.route('https://cdnjs.cloudflare.com/ajax/libs/tributejs/5.1.3/tribute.min.js',
    route => route.fulfill({path: path.join(output, 'tribute.min.js'), contentType: 'application/javascript'}));
  await page.goto(base);
  await page.locator('input[type=text]').fill(username);
  await page.locator('input[type=password]').fill('OwnedFixture7!');
  await page.getByRole('button', {name: /Login|登录/}).click();
  await page.locator('#chat-input textarea').waitFor({state: 'visible', timeout: 60000});
  await initialized(queue);
  page.submissionQueue = queue;
  return {page, queue};
}

async function initialized(queue) {
  await expect.poll(() => initial_selection_events.every(fn => queue.slice(queue.navigationStart).includes(fn)), {timeout: 20000}).toBe(true);
  await settled(queue);
}

async function settled(queue) {
  // Wait for this action's submitted requests. Periodic preview work continues;
  // a held generation also remains active while conversation controls are used.
  const offset = queue.navigationStart;
  const submitted = queue.slice(offset);
  await expect.poll(async () => {
    const data = await evidence();
    return submitted.length > 0 && submitted.every((fn, index) => fn === roles.runtime ||
      ['success', 'failed'].includes(data.queue_events[queue.requestIds[index + offset]]?.status));
  }, {timeout: 20000}).toBe(true);
  results.completions.push({sessionHash: queue.sessionHash, submitted: submitted.map((fn, i) => ({fn, eventId: queue.requestIds[i + offset]}))});
  await queue.page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function selectSource(page) {
  await expect(page.locator('#chat-file-list')).toHaveAttribute('data-chat-file-bound', 'true');
  await page.locator('[data-chat-file-id="owned-observatory"]').click();
  await expect(page.locator('[data-chat-file-id="owned-observatory"]')).toHaveClass(/is-selected/);
  await expect(page.locator('#main-pdf-preview-frame')).toHaveAttribute('src', /viewer.html/, {timeout: 15000});
  await settled(page.submissionQueue);
}

async function send(page, text) {
  await settled(page.submissionQueue);
  await page.locator('#chat-input textarea').fill(text);
  await page.locator('#chat-input textarea').press('Enter');
}

async function tailFinished(queue, count = 1) {
  await expect.poll(() => queue.filter(id => id === roles.persist).length, {timeout: 20000}).toBe(count);
  await expect.poll(async () => (await evidence()).callbacks.filter(
    item => item.callback === 'CompletionTail.persist' && item.event === 'return' && item.session_hash === queue.sessionHash
  ).length, {timeout: 20000}).toBeGreaterThanOrEqual(count);
}

function assertStoredTurn(record, writes, turns) {
  expect(record.data_source.messages).toHaveLength(turns);
  expect(record.data_source.retrieval_messages).toHaveLength(turns);
  expect(record.data_source.plot_history).toHaveLength(turns);
  expect(record.data_source.graph_source_ids).toEqual(['owned-observatory']);
  expect(record.data_source.origin).toBe('web');
  assertFinalizerAndWebWrites(writes, turns);
  expect(record.data_source.retrieval_messages.every(refs => refs.includes('owned-observatory.pdf'))).toBeTruthy();
}

function assertFinalizerAndWebWrites(writes, turns) {
  expect(writes).toHaveLength(turns * 2);
  for (let i = 0; i < writes.length; i += 2) {
    expect(writes[i].origin_argument).toBe('web');
    expect(writes[i + 1].origin_argument).toBeNull();
    for (const field of ['messages', 'retrieval_messages', 'plot_history', 'state', 'selected', 'origin', 'graph_source_ids']) {
      expect(writes[i + 1].data_source[field], field).toEqual(writes[i].data_source[field]);
    }
  }
}

async function normalSubmission() {
  const {page, queue} = await login();
  try {
    await selectSource(page);
    await send(page, 'How many telescopes are there?');
    await expect(page.locator('#answer-panel')).toContainText('The owned document says', {timeout: 15000});
    await expect(page.locator('#answer-panel')).toContainText('seven telescopes', {timeout: 15000});
    await expect(page.locator('#citations-card')).toContainText('owned-observatory.pdf');
    await tailFinished(queue);
    await expect.poll(async () => (await evidence()).conversations[0].name).toBe('Owned document discussion');
    let data = await evidence();
    const id = data.conversations[0].id;
    assertStoredTurn(data.conversations[0], data.writes.filter(item => item.conversation_id === id), 1);
    await send(page, 'SECOND question about the telescopes');
    await tailFinished(queue, 2);
    data = await evidence();
    const record = data.conversations.find(item => item.id === id);
    assertStoredTurn(record, data.writes.filter(item => item.conversation_id === id), 2);
    expect(record.name).toBe('Owned document discussion');
    expect(JSON.stringify(data.states)).toContain('SECOND question about the telescopes');
    for (const callback of ['ChatPage.check_and_suggest_name_conv', 'ConversationControl.rename_conv', 'ChatPage.persist_data_source']) {
      expect(data.callbacks.some(item => item.callback === callback && item.event === 'return')).toBeTruthy();
    }
    await page.reload();
    await page.locator('#chat-input textarea').waitFor({state: 'visible'});
    await initialized(queue);
    await page.getByText('Conversation', {exact: true}).click();
    await page.locator('#conversation-dropdown input').click();
    await page.getByRole('option', {name: 'Owned document discussion', exact: true}).click();
    await expect(page.locator('#answer-panel')).toContainText('SECOND question about the telescopes', {timeout: 15000});
    await expect(page.locator('#citations-card')).toContainText('owned-observatory.pdf');
    expect((await evidence()).conversations.find(item => item.id === id).data_source).toEqual(record.data_source);
    results.scenarios.push({name: 'two-turn-stream-citations-cache-name-web-persist-reload', id, queue});
    await page.screenshot({path: path.join(output, 'normal-reloaded.png'), fullPage: true});
  } finally { await page.close(); }
}

async function streamFailure() {
  const {page, queue} = await login();
  try {
    const count = (await evidence()).conversations.length;
    await selectSource(page);
    await send(page, 'STREAM_FAILURE how many telescopes?');
    await expect(page.locator('#answer-panel')).toContainText("(Sorry, I don't know)", {timeout: 15000});
    await tailFinished(queue);
    const data = await evidence();
    const record = data.conversations[count];
    expect(record.data_source.messages || []).toEqual([]);
    expect(record.name).toMatch(/^Untitled/);
    expect(data.writes.filter(item => item.conversation_id === record.id)).toEqual([]);
    results.scenarios.push({name: 'stream-error-no-naming-or-write', id: record.id, queue});
  } finally { await page.close(); }
}

async function conversationIsolation() {
  const {page, queue} = await login();
  try {
    await page.getByText('Conversation', {exact: true}).click();
    await page.locator('#conversation-dropdown input').click();
    await page.getByRole('option', {name: 'Owned document discussion', exact: true}).click();
    await expect(page.locator('#answer-panel')).toContainText('SECOND question about the telescopes');
    const before = (await evidence()).conversations;
    await page.locator('#new-conv-button').click();
    await expect.poll(async () => (await evidence()).conversations.length).toBe(before.length + 1);
    await expect(page.locator('#answer-panel')).not.toContainText('SECOND question');
    await selectSource(page);
    await expect(page.locator('#answer-panel')).not.toContainText('SECOND question');
    await send(page, 'ISOLATED CONVERSATION own question');
    await tailFinished(queue);
    let data = await evidence();
    const fresh = data.conversations.find(row => !before.some(old => old.id === row.id));
    expect(fresh.name).toBe('Isolated conversation');
    assertStoredTurn(fresh, data.writes.filter(item => item.conversation_id === fresh.id), 1);
    await page.getByRole('button', {name: 'Next ▶', exact: true}).click();
    await expect(page.locator('#pdf-page-number input')).toHaveValue('2');
    await expect(page.locator('#answer-panel')).not.toContainText('ISOLATED CONVERSATION');
    await page.getByRole('button', {name: '◀ Prev', exact: true}).click();
    await expect(page.locator('#pdf-page-number input')).toHaveValue('1');
    await expect(page.locator('#answer-panel')).toContainText('ISOLATED CONVERSATION');
    await page.locator('#conversation-dropdown input').click();
    await page.getByRole('option', {name: 'Owned document discussion', exact: true}).click();
    await expect(page.locator('#answer-panel')).toContainText('SECOND question about the telescopes');
    await expect(page.locator('#answer-panel')).not.toContainText('ISOLATED CONVERSATION');
    await page.reload();
    await page.locator('#chat-input textarea').waitFor({state: 'visible'});
    await initialized(queue);
    await page.getByText('Conversation', {exact: true}).click();
    await page.locator('#conversation-dropdown input').click();
    await page.getByRole('option', {name: 'Isolated conversation', exact: true}).click();
    await expect(page.locator('#answer-panel')).toContainText('ISOLATED CONVERSATION');
    await expect(page.locator('#answer-panel')).not.toContainText('SECOND question');
    data = await evidence();
    expect(data.conversations.find(row => row.id === fresh.id).data_source).toEqual(fresh.data_source);
    results.scenarios.push({name: 'empty-conversation-same-file-page-isolation-navigation-reload', id: fresh.id, queue});
  } finally { await page.close(); }
}

async function slowViewSwitch() {
  const {page, queue} = await login();
  try {
    const count = (await evidence()).conversations.length;
    await selectSource(page);
    await send(page, 'SLOW_STREAM view switch');
    await expect(page.locator('#answer-panel')).toContainText('The owned document says', {timeout: 15000});
    await page.getByText('Conversation', {exact: true}).click();
    await page.locator('#new-conv-button').click();
    await tailFinished(queue);
    const data = await evidence();
    expect(data.conversations).toHaveLength(count + 2);
    const fresh = data.conversations[count + 1];
    expect(fresh.name).toMatch(/^Untitled/);
    expect(fresh.data_source.messages || []).toEqual([]);
    expect(data.writes.filter(item => item.conversation_id === fresh.id)).toEqual([]);
    await expect(page.locator('#answer-panel')).not.toContainText('seven telescopes');
    results.scenarios.push({name: 'slow-stream-new-conversation-protected', id: fresh.id, queue});
  } finally { await page.close(); }
}

async function disconnectStream() {
  const {page, queue} = await login();
  const count = (await evidence()).conversations.length;
  await selectSource(page);
  await send(page, 'SLOW_STREAM disconnect');
  await expect(page.locator('#answer-panel')).toContainText('The owned document says', {timeout: 15000});
  await page.close();
  await new Promise(resolve => setTimeout(resolve, 6500));
  const data = await evidence();
  const record = data.conversations[count];
  expect(record.data_source.messages || []).toEqual([]);
  expect(data.writes.filter(item => item.conversation_id === record.id)).toEqual([]);
  results.scenarios.push({name: 'disconnect-cancels-before-finalizer-and-web-tail', id: record.id, queue});
}

async function authenticatedIndexing() {
  const filesBefore = (await evidence()).files;
  for (const username of ['browser-owner', 'browser-other']) {
    const {page, queue} = await login(username);
    try {
      if (username === 'browser-other') {
        await expect.poll(async () => (await evidence()).callbacks.filter(item =>
          item.callback === 'ChatPage.refresh_chat_file_list' && item.event === 'return'
          && item.session_hash === queue.sessionHash).length).toBeGreaterThan(0);
        await expect(page.locator('[data-chat-file-id="owned-observatory"]')).toHaveCount(0);
      }
      const filename = username + '-uploaded.txt';
      await page.getByRole('radio', {name: 'Document', exact: true}).check();
      const uploadResponse = page.waitForResponse(response =>
        response.request().method() === 'POST' && new URL(response.url()).pathname === '/upload');
      await page.locator('#chat-input input[type=file]').setInputFiles({
        name: filename, mimeType: 'text/plain',
        buffer: Buffer.from(username + ': the observatory has seven telescopes.'),
      });
      expect((await uploadResponse).ok()).toBeTruthy();
      await expect(page.locator('#chat-input .thumbnails .thumbnail-item')).toHaveCount(1);
      await send(page, 'Summarize the uploaded document');
      await tailFinished(queue);
      let data = await evidence();
      const owner = data.users[username];
      const uploaded = data.files.find(file => file.name === filename && file.user === owner);
      expect(uploaded).toBeDefined();
      const context = data.states.find(state => state.session_hash === queue.sessionHash)._request_completion;
      const conversationId = context.conversation_id;
      assertFinalizerAndWebWrites(data.writes.filter(item => item.conversation_id === conversationId), 1);
      await expect(page.locator(`[data-chat-file-id="${uploaded.id}"]`)).toHaveCount(1);
      await send(page, 'https://example.org/owned-web-document');
      await tailFinished(queue, 2);
      data = await evidence();
      expect(data.files.some(file => file.name === 'https://example.org/owned-web-document' && file.user === owner)).toBeTruthy();
      await expect(page.locator('.pdf-preview-notice')).toContainText('Selected file is unavailable');
      const conversation = data.conversations.find(row => row.id === conversationId);
      expect(conversation.data_source.messages).toHaveLength(2);
      expect(conversation.data_source.retrieval_messages).toHaveLength(2);
      expect(conversation.data_source.plot_history).toHaveLength(2);
      expect(conversation.data_source.retrieval_messages[0]).toContain(filename);
      expect(conversation.data_source.retrieval_messages[1]).toContain('owned-web-document');
      assertFinalizerAndWebWrites(data.writes.filter(item => item.conversation_id === conversationId), 2);
      const indexCalls = data.callbacks.filter(item => item.event === 'call' && item.callback.includes('index_fn_') && item.session_hash === queue.sessionHash);
      expect(indexCalls.map(item => item.username)).toEqual([username, username]);
      results.scenarios.push({name: 'browser-upload-and-url-owner-isolation', username, uploadedId: uploaded.id, queue});
    } finally {
      fs.writeFileSync(path.join(output, username + '-input.html'), await page.locator('#chat-input').innerHTML());
      await page.screenshot({path: path.join(output, username + '-indexing.png'), fullPage: true});
      await page.close();
    }
  }
  const data = await evidence();
  const added = data.files.filter(file => !filesBefore.some(old => old.id === file.id));
  expect(added).toHaveLength(4);
  expect(new Set(added.map(file => file.user)).size).toBe(2);
}

(async () => {
  browser = await chromium.launch({headless: true, ...(process.env.MARA_BROWSER_CHANNEL ? {channel: process.env.MARA_BROWSER_CHANNEL} : {})});
  const selected = process.env.MARA_BROWSER_SCENARIOS?.split(',');
  const operations = require('./conversation_actions.cjs')({expect, login, evidence, send, tailFinished, settled, initialized, roles, results, output, base, assertFinalizerAndWebWrites});
  const scenarios = [normalSubmission, conversationIsolation, streamFailure, slowViewSwitch, disconnectStream, authenticatedIndexing, ...operations];
  if (selected) expect(selected.every(name => scenarios.some(fn => fn.name === name))).toBeTruthy();
  for (const scenario of scenarios.filter(fn => selected ? selected.includes(fn.name) : fn.name !== 'publicConversationPermissions')) {
    console.log('Starting browser scenario:', scenario.name);
    try { await scenario(); console.log('Passed browser scenario:', scenario.name); }
    catch (error) { results.scenarios.push({name: scenario.name, failure: error.stack}); console.log('Failed browser scenario:', scenario.name, error.stack); }
  }
  results.evidence = await evidence();
  expect(results.evidence.callbacks.filter(item => item.preview_failed), 'unexpected preview callback failures').toEqual([]);
  expect(results.errors).toEqual([]);
  if (results.scenarios.some(item => item.failure)) process.exitCode = 1;
})().catch(error => { results.errors.push(String(error)); process.exitCode = 1; })
  .finally(async () => {
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify({scenarios: results.scenarios, errors: results.errors}, null, 2));
    if (browser) await browser.close();
  });

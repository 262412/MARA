// Real file-library and page controls, with owned hostile display metadata.
const path = require('node:path');

module.exports = function ({expect, login, evidence, settled, send, selectSource, tailFinished, results, output}) {
  async function card(page, id) {
    await expect(page.locator('#chat-file-list')).toHaveAttribute('data-chat-file-bound', 'true');
    await page.locator(`[data-chat-file-id="${id}"]`).click();
    await expect(page.locator(`[data-chat-file-id="${id}"]`)).toHaveClass(/is-selected/);
    await settled(page.submissionQueue);
  }

  async function pageNumber(page, expected) {
    await expect(page.locator('#pdf-page-number input')).toHaveValue(String(expected));
    await expect(page.locator('#page-thumbnail-list .is-active')).toHaveAttribute('data-page-number', String(expected));
    await expect(page.locator('#page-metadata-strip')).toContainText(`${expected} /`);
    await settled(page.submissionQueue);
  }

  async function fileBrowserNavigation() {
    for (const username of ['browser-owner', 'browser-other']) {
      const {page, queue} = await login(username);
      const leaked = [];
      page.on('request', request => { if (request.url().includes('/r3c-exfil')) leaked.push(request.url()); });
      try {
        const textId = `r3c-${username}-text`;
        const imageId = `r3c-${username}-image`;
        const other = username === 'browser-owner' ? 'browser-other' : 'browser-owner';
        await expect(page.locator(`[data-chat-file-id^="r3c-${other}-"]`)).toHaveCount(0);
        const data = await evidence();
        const name = data.files.find(file => file.id === textId).name;
        await card(page, textId);
        await expect(page.locator('#page-strip-file-summary strong')).toHaveText(name);
        await expect(page.locator('#chat-selected-file')).toHaveText('Focus: ' + name);
        await expect(page.locator('#page-thumbnail-list')).toContainText('ALPHA Ω & <b>literal</b>');
        await expect(page.locator('#page-metadata-strip')).toContainText('Previewing ' + name);
        await expect(page.locator('#page-strip-file-summary img, #chat-file-list img')).toHaveCount(0);
        await expect(page.locator('#main-pdf-preview-frame')).toHaveAttribute('srcdoc', /ALPHA/);
        await expect(page.locator('#main-pdf-preview-frame')).toHaveAttribute('sandbox', 'allow-same-origin');
        await pageNumber(page, 1);
        const initialCards = await page.locator('[data-chat-file-id]').count();
        const filter = page.locator('#chat-file-filter textarea, #chat-file-filter input');
        await filter.fill('  ' + username.toUpperCase() + ' Ω & <IMG  ');
        await expect(page.locator('[data-chat-file-id]')).toHaveCount(2);
        await expect(page.locator('#workbench-file-summary')).toContainText('2 files');
        await filter.fill('no-match-<>&');
        await expect(page.locator('#chat-file-list')).toHaveText('No files uploaded');
        await expect(page.locator('#chat-selected-file')).toHaveText('Focus: ' + name);
        await expect(page.locator('#page-strip-file-summary strong')).toHaveText(name);
        await filter.fill('');
        await expect(page.locator('[data-chat-file-id]')).toHaveCount(initialCards);
        await expect(page.locator(`[data-chat-file-id="${textId}"]`)).toHaveClass(/is-selected/);
        await page.getByRole('button', {name: 'Next ▶', exact: true}).click();
        await pageNumber(page, 2);
        await page.getByRole('button', {name: '◀ Prev', exact: true}).click();
        await pageNumber(page, 1);
        await page.locator('#pdf-page-number input').fill('2');
        await page.locator('#pdf-page-number input').press('Tab');
        await pageNumber(page, 2);
        await expect(page.locator('#page-thumbnail-list')).toHaveAttribute('data-page-thumbnails-bound', 'true');
        await page.locator('#page-thumbnail-list [data-page-number="1"]').click();
        await pageNumber(page, 1);
        await card(page, imageId);
        await expect(page.locator('#page-metadata-strip')).toContainText('Needed for scanned pages');
        // The existing PNG handler presents indexed text in the main preview;
        // its page card uses the indexed image thumbnail.
        await expect(page.locator('#main-pdf-preview-frame')).toHaveAttribute('srcdoc', /ALPHA/);
        await expect(page.locator('#page-thumbnail-list img')).toHaveCount(1);
        await expect(page.locator('#page-thumbnail-list img')).toHaveAttribute('src', /^data:image\/png;base64,/);
        await pageNumber(page, 1);
        await card(page, textId);
        await expect(page.locator('#main-pdf-preview-frame')).toHaveAttribute('srcdoc', /ALPHA/);
        await expect(page.locator('#chat-file-list')).not.toContainText(other);
        expect(await page.evaluate(() => globalThis.r3cInjected)).toBeUndefined();
        expect(leaked).toEqual([]);
        results.scenarios.push({name: 'file-library-filter-card-pages-special-metadata-isolation', username, textId, imageId, queue});
      } finally {
        results.fileBrowserObservations ||= [];
        results.fileBrowserObservations.push({username, leaked, focusHtml: await page.locator('#chat-selected-file').innerHTML(), injected: await page.evaluate(() => globalThis.r3cInjected ?? null)});
        await page.screenshot({path: path.join(output, username + '-file-browser.png'), fullPage: true});
        await page.close();
      }
    }
  }

  async function pdfSearchAndSourceSwitch() {
    const {page, queue} = await login();
    try {
      await selectSource(page);
      const viewer = page.frameLocator('#main-pdf-preview-frame');
      // The iframe HTML exposes controls before the PDF.js module binds them.
      // Assert the viewer's actual readiness before the one search click.
      await expect.poll(() => viewer.locator('body').evaluate(() => Boolean(
        globalThis.PDFViewerApplication?.initialized &&
        globalThis.PDFViewerApplication?.pdfDocument
      )), {timeout: 15000}).toBe(true);
      await viewer.locator('#viewFindButton').click();
      await viewer.locator('#findInput').fill('telescopes');
      await expect.poll(async () => JSON.parse(await viewer.locator('#findResultsCount').getAttribute('data-l10n-args') || '{}')).toMatchObject({current: 1, total: 1});
      await expect(viewer.locator('.highlight.selected')).toHaveText('telescopes');
      await viewer.locator('#findInput').fill('no-match-<>&');
      await expect(viewer.locator('#findMsg')).toContainText('Phrase not found');
      await viewer.locator('#findInput').fill('');
      await expect(viewer.locator('.highlight')).toHaveCount(0);
      const before = (await evidence()).conversations;
      await send(page, 'SLOW_STREAM source switch');
      await expect(page.locator('#answer-panel')).toContainText('The owned document says', {timeout: 15000});
      await card(page, 'r3c-browser-owner-text');
      await pageNumber(page, 1);
      await tailFinished(queue);
      await expect(page.locator('#answer-panel')).not.toContainText('seven telescopes');
      await expect(page.locator('#chat-selected-file')).toContainText('browser-owner Ω');
      const data = await evidence();
      const record = data.conversations.find(row => !before.some(old => row.id === old.id));
      const writes = data.writes.filter(item => item.conversation_id === record.id);
      results.sourceSwitchObservation = {record, writes};
      expect(record.data_source.messages).toHaveLength(1);
      expect(record.data_source.messages[0][0]).toBe('SLOW_STREAM source switch');
      expect(record.data_source.graph_source_ids).toEqual(['owned-observatory']);
      expect(writes).toHaveLength(1);
      expect(writes[0].origin_argument).toBe('web');
      expect(record.name).toMatch(/^Untitled/);
      results.scenarios.push({name: 'pdf-search-clear-and-slow-stream-file-switch-protected', id: record.id, queue});
    } finally {
      await page.screenshot({path: path.join(output, 'pdf-search-source-switch.png'), fullPage: true});
      await page.close();
    }
  }

  return [fileBrowserNavigation, pdfSearchAndSourceSwitch];
};

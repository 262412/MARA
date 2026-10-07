// Upload actual archives; observe persistence and input lifetime without driving
// intermediate indexing APIs. The release endpoint controls only the model gate.
const {execFileSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

module.exports = function ({expect, login, evidence, settled, results, output, base}) {
  const manager = page => page.locator('#indices-tab');
  const lifetime = async () => (await fetch(base + '/owned-indexing-lifetime')).json();
  async function uploadZip(page, filename, text, quick = false) {
    const zip = path.join(output, filename);
    const python = process.env.MARA_BROWSER_PYTHON;
    require('./runtime_isolation.cjs').validate(process.env);
    execFileSync(python, ['-B', path.join(__dirname, 'write_owned_archive.py'), zip, filename.replace('.zip', '.txt'), text]);
    if (!quick) {
      await page.getByRole('tab', {name: 'files', exact: true}).click();
      await manager(page).getByRole('tab', {name: 'Upload Files', exact: true}).click();
    }
    const input = quick ? page.locator('#quick-file input[type=file]') : manager(page).locator('input[type=file][multiple]');
    const [uploaded] = await Promise.all([
      page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/upload'),
      input.setInputFiles({name: filename, mimeType: 'application/zip', buffer: fs.readFileSync(zip)}),
    ]);
    expect(uploaded.ok()).toBe(true);
    if (!quick) await manager(page).getByRole('button', {name: 'Upload and Index', exact: true}).click();
  }

  async function indexingZipAndWriterFailure() {
    const {page, queue} = await login('browser-controls');
    try {
      await uploadZip(page, 'r5b-normal.zip', 'Owned archive with seven telescopes.');
      await expect(manager(page).getByLabel('Upload result', {exact: true})).toHaveValue(/✅.*r5b-normal.txt/, {timeout: 30000});
      await settled(queue);
      expect((await lifetime()).inputs).toEqual([]);
      expect((await evidence()).files.some(file => file.name === 'r5b-normal.txt')).toBe(true);
      await uploadZip(page, 'r5b-failure.zip', 'R5B_FAIL_EMBEDDING owned document.');
      await expect(manager(page).getByLabel('Upload result', {exact: true})).toHaveValue(/❌.*Owned R5-B embedding failure/, {timeout: 30000});
      await settled(queue);
      expect((await lifetime()).inputs).toEqual([]);
      expect((await evidence()).files.some(file => file.name === 'r5b-failure.txt')).toBe(true);
      results.scenarios.push({name: 'browser-real-zip-success-and-writer-failure', lifetime: await lifetime()});
    } finally { await page.close(); }
  }

  async function indexingDisconnectRetainsInputsUntilWriterStops() {
    const {page} = await login('browser-other');
    try {
      await uploadZip(page, 'r5b-disconnect.zip', 'R5B_HELD_EMBEDDING seven telescopes.', true);
      await expect.poll(async () => (await lifetime()).embedding_started, {timeout: 30000}).toBe(true);
      const held = await lifetime();
      expect(held.inputs).toHaveLength(1);
      expect(held.writers.some(writer => writer.alive && !writer.done)).toBe(true);
      await page.close();
      expect((await lifetime()).inputs).toHaveLength(1);
      await fetch(base + '/owned-indexing-lifetime/release', {method: 'POST'});
      await expect.poll(async () => (await lifetime()).inputs, {timeout: 30000}).toEqual([]);
      await expect.poll(async () => (await lifetime()).writers.some(writer => writer.alive), {timeout: 30000}).toBe(false);
      // A synchronous quick-upload request is not an interruptible Gradio task.
      // Disconnect does not prove cancellation; its admitted writer may finish.
      expect((await evidence()).files.some(file => file.name === 'r5b-disconnect.txt')).toBe(true);
      results.scenarios.push({name: 'browser-disconnect-retains-zip-until-real-producer-stops', held, completed: await lifetime(), immediateCancellation: false});
    } finally {
      await fetch(base + '/owned-indexing-lifetime/release', {method: 'POST'});
      await page.close();
    }
  }
  return [indexingZipAndWriterFailure, indexingDisconnectRetainsInputsUntilWriterStops];
};

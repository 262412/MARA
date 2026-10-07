// Completion means the selected stable ID was installed, then used by Chat.
const fs = require('node:fs');
const path = require('node:path');

module.exports = ({expect, base, output}) => {
  const {functions} = JSON.parse(fs.readFileSync(path.join(output, 'ready.json')));
  const operations = async () => (await fetch(base + '/owned-web-operations')).json();
  const control = async (suffix, body) => {
    const response = await fetch(base + '/owned-file-browser-gate' + suffix,
      body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    expect(response.ok).toBe(true);
    return response.json();
  };
  async function holdClose(queue, username, key) {
    const save = Object.entries(functions).find(([, fn]) => fn.name === 'save_group');
    const children = Object.entries(functions).filter(([, fn]) => fn.trigger_after === Number(save[0]));
    const close = children.find(([, fn]) => fn.name === '<lambda>') ||
      Object.entries(functions).find(([, fn]) => fn.trigger_after === Number(children[0][0]));
    expect(close[1].name).toBe('<lambda>');
    await control('/arm', {key, callback: 'WebOperation', event: 'call', username, session_hash: queue.sessionHash, function_id: Number(close[0])});
    return {
      entered: async () => expect.poll(async () => (await control(''))[key]?.entered).toBe(true),
      release: () => control('/release/' + key, {}),
      applied: async () => {
        const eventId = (await control(''))[key].operation.event_id;
        await expect.poll(async () => (await operations()).some(item => item.event_id === eventId && item.phase === 'postprocess')).toBe(true);
        return (await operations()).find(item => item.event_id === eventId && item.phase === 'postprocess');
      },
    };
  }
  async function select(page, queue, name, id) {
    const before = (await operations()).length;
    await page.locator('#indices-tab svelte-virtual-table-viewport').getByText(name, {exact: true}).click();
    await expect.poll(async () => (await operations()).slice(before).some(item =>
      item.name === 'interact_group_list' && item.phase === 'postprocess' &&
      item.session_hash === queue.sessionHash && item.selected_group_id === id)).toBe(true);
    await expect(page.locator('#indices-tab').getByRole('button', {name: 'Go to Chat', exact: true})).toBeVisible();
  }
  async function chatApplied(queue, id) {
    await expect.poll(async () => (await operations()).some(item =>
      item.name === 'set_group_id_selector' && item.phase === 'return' &&
      item.session_hash === queue.sessionHash && item.inputs[0] === id && item.result.length === 3)).toBe(true);
    return (await operations()).filter(item => item.session_hash === queue.sessionHash);
  }
  return {holdClose, select, chatApplied};
};

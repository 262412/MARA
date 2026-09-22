// Deliberate failures on the real App; each is run alone with a fresh root.
const fs = require('node:fs');
const path = require('node:path');
const exit = require('./browser_exit.cjs');

module.exports = ({expect, login, selectSource, send, results, output, base}) => {
  async function run(kind) {
    const {page, queue} = await login();
    try {
      await selectSource(page);
      await send(page, 'HELD_STREAM owned exit probe');
      await expect.poll(async () => (await (await fetch(base + '/owned-model-gate')).json()).started,
        {timeout: 15000}).toBe(true);
      const gate = await (await fetch(base + '/owned-model-gate')).json();
      expect(gate.released).toBe(false);
      fs.writeFileSync(path.join(output, 'exit-probe-held.json'), JSON.stringify({kind, gate, session: queue.sessionHash,
        requests: queue.map((fn, i) => ({fn, event: queue.requestIds[i]}))}, null, 2));
      if (kind === 'node' || kind === 'app') {
        fs.writeFileSync(path.join(output, 'watchdog-' + kind), 'controlled watchdog trigger');
        await page.waitForEvent('close', {timeout: 20000});
        throw Error('Owned watchdog stopped browser');
      }
      if (kind === 'assertion') expect('owned actual').toBe('owned expected');
      results.scenarios.push({name: 'owned-exit-probe-' + kind, session: queue.sessionHash});
    } catch (error) {
      exit.primary(results, output, error);
      throw error;
    } finally {
      // Leave the model held so the independent App cleanup must release it.
      await exit.cleanup(results, [['probe page close', () => page.close()]]);
    }
  }
  async function fixtureExitNormal() { await run('normal'); }
  async function fixtureExitAssertion() { await run('assertion'); }
  async function fixtureExitNodeWatchdog() { await run('node'); }
  async function fixtureExitAppWatchdog() { await run('app'); }
  async function fixtureExitReleaseFailure() { await run('release-failure'); }
  return [fixtureExitNormal, fixtureExitAssertion, fixtureExitNodeWatchdog, fixtureExitAppWatchdog, fixtureExitReleaseFailure];
};

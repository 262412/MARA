// Failure handling for this owned browser harness, never production requests.
const fs = require('node:fs');
const path = require('node:path');

function save(output, results) {
  fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(results, null, 2));
}
function primary(results, output, error, kind = 'assertion_failure') {
  if (!results.currentFailure) results.currentFailure = {
    scenario: results.currentScenario, kind, error: error.stack || String(error), at: new Date().toISOString(),
  };
  save(output, results);
}
async function cleanup(results, steps, timeout = 5000) {
  for (const [stage, operation] of steps) {
    let timer;
    try {
      await Promise.race([Promise.resolve().then(operation), new Promise((_, reject) => {
        timer = setTimeout(() => reject(Error('Owned cleanup deadline: ' + stage)), timeout);
      })]);
    } catch (error) {
      (results.cleanupErrors ||= []).push({stage, scenario: results.currentScenario, error: error.stack || String(error)});
    } finally { clearTimeout(timer); }
  }
}
module.exports = {save, primary, cleanup};

// Validate the exact browser entrypoint before loading Playwright or spawning ZIP work.
const fs = require('node:fs');
const path = require('node:path');

function validate(env) {
  const root = env.MARA_PYTEST_RUNTIME_ROOT;
  if (!root || env.MARA_DIAGNOSTIC_ISOLATION_REQUIRED !== '1' ||
      env.MARA_DIAGNOSTIC_CHILD !== '1' || !env.MARA_PYTEST_OWNER_TOKEN) {
    throw Error('Browser diagnostic did not inherit runtime isolation');
  }
  if (fs.realpathSync(root) !== path.resolve(root) ||
      fs.lstatSync(path.join(root, '.mara-pytest-owner')).isSymbolicLink() ||
      fs.readFileSync(path.join(root, '.mara-pytest-owner'), 'utf8') !== env.MARA_PYTEST_OWNER_TOKEN) {
    throw Error('Browser diagnostic root ownership changed');
  }
  for (const key of ['MARA_RUNTIME_DIR', 'KH_APP_DATA_DIR', 'GRADIO_TEMP_DIR',
    'HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TMP', 'TEMP', 'TMPDIR',
    'KH_USER_DATA_DIR', 'KH_FILESTORAGE_PATH', 'THEFLOW_TEMP_PATH',
    'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'MARA_PYTEST_RUNTIME_PARENT']) {
    const value = env[key];
    if (!value || !contained(root, value)) throw Error('Browser diagnostic path escaped: ' + key);
  }
  const evidence = env.MARA_DIAGNOSTIC_EVIDENCE_DIR;
  if (!evidence || fs.readFileSync(path.join(evidence, '.mara-pytest-owner'), 'utf8') !== env.MARA_DIAGNOSTIC_EVIDENCE_OWNER) {
    throw Error('Browser diagnostic evidence ownership changed');
  }
  if (!env.KH_DATABASE?.startsWith('sqlite:///') ||
      !contained(root, env.KH_DATABASE.slice('sqlite:///'.length)) ||
      env.THEFLOW_SETTINGS_MODULE !== 'ktem.default_flowsettings') {
    throw Error('Browser diagnostic database or settings escaped');
  }
  return {root, evidence};
}

function contained(root, value) {
  let existing = path.resolve(value);
  while (!fs.existsSync(existing)) existing = path.dirname(existing);
  const relative = path.relative(root, fs.realpathSync(existing));
  return relative !== '..' && !relative.startsWith('..' + path.sep) && !path.isAbsolute(relative);
}

module.exports = {validate};

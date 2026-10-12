const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {validate} = require('./runtime_isolation.cjs');

test('browser rejects lost ownership and escaped paths before requiring Playwright', () => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'owned-browser-isolation-'));
  const root = path.join(base, 'root'), output = path.join(base, 'output');
  fs.mkdirSync(root); fs.mkdirSync(output);
  fs.writeFileSync(path.join(root, '.mara-pytest-owner'), 'owned');
  fs.writeFileSync(path.join(output, '.mara-pytest-owner'), 'evidence');
  const env = {MARA_PYTEST_RUNTIME_ROOT: root, MARA_PYTEST_OWNER_TOKEN: 'owned',
    MARA_DIAGNOSTIC_ISOLATION_REQUIRED: '1', MARA_DIAGNOSTIC_CHILD: '1',
    MARA_DIAGNOSTIC_EVIDENCE_DIR: output, MARA_DIAGNOSTIC_EVIDENCE_OWNER: 'evidence',
    THEFLOW_SETTINGS_MODULE: 'ktem.default_flowsettings', KH_DATABASE: 'sqlite:///' + path.join(root, 'db.sqlite')};
  const keys = ['MARA_RUNTIME_DIR', 'KH_APP_DATA_DIR', 'GRADIO_TEMP_DIR', 'HOME', 'USERPROFILE',
    'APPDATA', 'LOCALAPPDATA', 'TMP', 'TEMP', 'TMPDIR', 'KH_USER_DATA_DIR', 'KH_FILESTORAGE_PATH',
    'THEFLOW_TEMP_PATH', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'MARA_PYTEST_RUNTIME_PARENT'];
  for (const key of keys) env[key] = root;
  try {
    assert.deepEqual(validate(env), {root, evidence: output});
    for (const key of ['MARA_PYTEST_RUNTIME_ROOT', 'MARA_PYTEST_OWNER_TOKEN', 'MARA_DIAGNOSTIC_CHILD',
      'MARA_DIAGNOSTIC_ISOLATION_REQUIRED', ...keys]) {
      const missing = {...env}; delete missing[key];
      assert.throws(() => validate(missing), undefined, key);
    }
    for (const key of keys) assert.throws(() => validate({...env, [key]: base}), undefined, key);
    assert.throws(() => validate({...env, THEFLOW_SETTINGS_MODULE: 'outside.settings'}));
    assert.throws(() => validate({...env, KH_DATABASE: 'sqlite:///' + path.join(base, 'db.sqlite')}));
    const link = path.join(root, 'link');
    fs.symlinkSync(output, link, process.platform === 'win32' ? 'junction' : 'dir');
    assert.throws(() => validate({...env, TEMP: path.join(link, 'future-file')}));
    fs.unlinkSync(link);
    fs.unlinkSync(path.join(root, '.mara-pytest-owner'));
    assert.throws(() => validate(env));
    assert.equal(Object.keys(require.cache).some(name => name.includes('playwright')), false);
  } finally {
    fs.rmSync(base, {recursive: true});
  }
});

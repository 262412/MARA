const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');

function fixture() {
  const text = fs.readFileSync('libs/ktem/ktem/pages/chat/chat_conversation_events.py', 'utf8');
  const source = text.match(/CONVERSATION_BUSY_JS = """([\s\S]*?)"""/);
  assert.ok(source, 'Production conversation readiness function must exist');
  const dock = {inert: false, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }};
  const run = vm.runInNewContext('(' + source[1] + ')', {
    document: {querySelector(selector) { assert.equal(selector, '#conversation-dock'); return dock; }},
  });
  return {dock, run};
}

test('only unfinished conversation operations keep their own control area unavailable', () => {
  const {dock, run} = fixture();
  run('select', true); run('reload', true);
  assert.equal(dock.inert, true); assert.equal(dock.attrs['aria-busy'], 'true');
  run('select', false);
  assert.equal(dock.inert, true);
  run('reload', false);
  assert.equal(dock.inert, false); assert.equal(dock.attrs['aria-busy'], 'false');
});

test('finishing twice cannot unlock another operation or another browser session', () => {
  const a = fixture(), b = fixture();
  a.run('rename', true); b.run('select', true);
  a.run('rename', false); a.run('rename', false);
  assert.equal(a.dock.inert, false); assert.equal(b.dock.inert, true);
});

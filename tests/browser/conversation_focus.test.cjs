const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname,
  '../../libs/ktem/ktem/assets/js/chat_input_focus.js'), 'utf8');

function fixture(tagName = 'BODY', isContentEditable = false) {
  const active = {tagName, isContentEditable};
  const document = {activeElement: active};
  const chat = {tagName: 'TEXTAREA', focus() { document.activeElement = chat; }};
  document.querySelector = selector => { assert.equal(selector, '#chat-input textarea'); return chat; };
  const run = vm.runInNewContext('(' + source + ')', {document});
  return {active, chat, document, run};
}

for (const tag of ['BODY', 'BUTTON']) {
  test('idle or initiating ' + tag + ' retains normal chat autofocus', () => {
    const {run, document, chat} = fixture(tag);
    run();
    assert.equal(document.activeElement, chat);
  });
}
for (const tag of ['INPUT', 'TEXTAREA', 'SELECT']) {
  test('a late tail does not take focus from an active ' + tag, () => {
    const {run, document, active} = fixture(tag);
    run();
    assert.equal(document.activeElement, active);
  });
}
test('active content editing is retained', () => {
  const {run, document, active} = fixture('DIV', true);
  run();
  assert.equal(document.activeElement, active);
});
test('focus is checked at delivery, not captured when work starts', () => {
  const {run, document} = fixture();
  const later = {tagName: 'INPUT'};
  document.activeElement = later;
  run();
  assert.equal(document.activeElement, later);
});
test('already focused chat input remains focused', () => {
  const {run, document, chat} = fixture();
  document.activeElement = chat;
  run();
  assert.equal(document.activeElement, chat);
});

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// The pre-migration run reads the captured effective Python strings. Normal
// runs execute the packaged resources, including CI's existing Node suite.
const baseline = process.env.MARA_CHAT_CALLBACK_FIXTURE
  ? JSON.parse(fs.readFileSync(process.env.MARA_CHAT_CALLBACK_FIXTURE, 'utf8')) : null;

function callback(name, extra = {}) {
  const timers = [];
  const context = {
    setTimeout(fn, delay) { timers.push({fn, delay}); },
    Event: class { constructor(type, options) { Object.assign(this, {type}, options); } },
    KeyboardEvent: class { constructor(type, options) { Object.assign(this, {type}, options); } },
    ...extra,
  };
  const source = baseline ? baseline[name + '_js']
    : fs.readFileSync(path.join(__dirname, name + '.js'), 'utf8');
  const fn = vm.runInNewContext('(' + source + ')', context);
  assert.equal(typeof fn, 'function');
  return {fn, timers, context};
}

function documentFor(elements = {}, lists = {}) {
  return {
    querySelector: selector => elements[selector] || null,
    querySelectorAll: selector => lists[selector] || [],
    getElementById: id => elements['#' + id] || null,
    getElementsByClassName: cls => lists['.' + cls] || [],
  };
}

function preview() {
  const events = {};
  return {
    events, dataset: {}, style: {}, offsetLeft: 10, offsetTop: 20,
    scrollLeft: 100, scrollTop: 200,
    addEventListener(name, fn, options) {
      assert.equal(events[name], undefined, 'listeners are attached once');
      events[name] = {fn, options};
    },
  };
}

test('focus and URL submit retain selectors, event kind and missing-input error', () => {
  const calls = [];
  const document = documentFor({
    '#chat-input textarea': {focus: () => calls.push('focus')},
    '#quick-url-demo textarea': {dispatchEvent: event => calls.push({...event})},
  });
  assert.equal(callback('chat_input_focus', {document}).fn(), undefined);
  assert.equal(callback('quick_urls_submit', {document}).fn(), undefined);
  assert.deepEqual(calls, ['focus', {type: 'keypress', key: 'Enter'}]);
  assert.throws(() => callback('chat_input_focus', {document: documentFor()}).fn(),
    /Cannot read properties of null/);
});

test('paper links create a conversation before the delayed literal URL submit', () => {
  const calls = [];
  const links = [{}, {}];
  const input = {dispatchEvent: event => calls.push({...event})};
  const document = documentFor({
    '#new-conv-button': {click: () => calls.push('new')},
    '#quick-url-demo textarea': input,
  }, {'#related-papers a': links});
  const {fn, timers} = callback('recommended_papers', {document});
  fn();
  assert.equal(links[0].onclick, links[1].onclick);
  links[1].onclick({preventDefault: () => calls.push('prevent'),
    currentTarget: {getAttribute: key => { assert.equal(key, 'href'); return 'https://owned.invalid/?q=<>&'; }}});
  assert.deepEqual(calls, ['prevent', 'new']);
  assert.equal(input.value, undefined);
  assert.equal(timers[0].delay, 500);
  timers[0].fn();
  assert.equal(input.value, 'https://owned.invalid/?q=<>&');
  assert.deepEqual(calls.slice(2), [{type: 'input', bubbles: true}, {type: 'keypress', key: 'Enter'}]);
});

test('clear selection visits only bot rows; API-key callback preserves order and storage default', () => {
  const removed = [];
  callback('clear_bot_message_selection', {document: documentFor({}, {
    'div#main-chat-bot div.message-row.bot-row': [1, 2].map(i => ({
      classList: {remove: name => removed.push([i, name])},
    })),
  })}).fn();
  assert.deepEqual(removed, [[1, 'text_selection'], [2, 'text_selection']]);
  const {fn, context} = callback('fetch_api_key', {
    getStorage: (key, fallback) => { assert.equal(key, 'google_api_key'); assert.equal(fallback, ''); return 'owned-key'; },
  });
  assert.deepEqual(Array.from(fn('unchanged-input', 'ignored')), ['owned-key', 'unchanged-input']);
  assert.equal(context.api_key, 'owned-key');
});

test('scroll uses the panel or first overflowing child after 30 ms, tolerating absent panel', () => {
  for (const mode of ['panel', 'child', 'absent']) {
    const children = [0, 1, 2].map(i => ({scrollHeight: 20 + i * 100, clientHeight: 50}));
    const panel = {scrollHeight: mode === 'panel' ? 100 : 20, clientHeight: 50, children};
    const {fn, timers} = callback('scroll_answer_panel', {
      document: documentFor(mode === 'absent' ? {} : {'#answer-panel': panel}),
    });
    fn();
    assert.equal(panel.scrollTop, undefined);
    assert.equal(timers.length, 1);
    assert.equal(timers[0].delay, 30);
    timers[0].fn();
    assert.equal(panel.scrollTop, mode === 'panel' ? 100 : undefined);
    assert.equal(children[1].scrollTop, mode === 'child' ? 120 : undefined);
    assert.equal(children[2].scrollTop, undefined);
  }
});

test('PDF callback preserves immediate search, link delegates, timer order, mindmap and stream observer', () => {
  const calls = [];
  const pdfLinks = [{}, {}, {}], citations = [{}, {}], nodes = [{}];
  const tree = {style: {height: ''}}, svg = {}, toggle = {};
  const exportLink = {addEventListener: (name, fn) => { assert.equal(name, 'click'); exportLink.click = fn; }};
  const panel = {scrollHeight: 150, clientHeight: 80, scrollTo: options => calls.push({...options})};
  const expand = {}, container = preview();
  let observer;
  const document = documentFor({
    'div.markmap script': {}, 'svg.markmap': svg, 'div.markmap': tree,
    '#mindmap-toggle': toggle, '#mindmap-export': exportLink,
    '#answer-panel': panel, '#answer-expand': expand,
  }, {'.pdf-link': pdfLinks, 'a.citation': citations, 'svg.markmap div': nodes,
    '.pdf-preview-shell': [container]});
  const openModal = () => {}, scrollToCitation = () => {}, fillChatInput = () => {};
  const {fn, timers} = callback('pdfview', {document, openModal, scrollToCitation, fillChatInput,
    fullTextSearch: () => { calls.push('search'); return 'search-result'; },
    markmap: {autoLoader: {renderAll: () => calls.push('render')}},
    spawnDocument: (node, options) => { assert.equal(node, svg); calls.push({...options}); },
    MutationObserver: class {
      constructor(changed) { this.changed = changed; observer = this; }
      observe(target, options) { assert.equal(target, expand); this.options = {...options}; }
    },
  });
  assert.deepEqual(Array.from(fn()), [2]); // Original reassigned `links` counts citations.
  assert.deepEqual(calls, ['search', 'render']);
  assert.deepEqual(timers.map(timer => timer.delay), [100, 250, 30, 100, 150]);
  assert.equal(timers[0].fn, 'search-result'); // Preserve existing eager invocation.
  assert.ok(pdfLinks.every(link => link.onclick === openModal));
  assert.ok(citations.every(link => link.onclick === scrollToCitation));
  timers[1].fn();
  assert.equal(nodes[0].onclick, fillChatInput);
  const event = {preventDefault: () => calls.push('prevent')};
  toggle.onclick(event); assert.equal(tree.style.height, '650px');
  toggle.onclick(event); assert.equal(tree.style.height, '400px');
  exportLink.click(event); assert.deepEqual(calls.at(-1), {window: 'width=1000,height=1000'});
  timers[2].fn(); assert.deepEqual(calls.at(-1), {top: 150, behavior: 'smooth'});
  timers[3].fn(); assert.deepEqual(observer.options, {childList: true, subtree: true, characterData: true});
  observer.changed([]); assert.equal(panel.scrollTop, 150);
  timers[4].fn(); assert.equal(container.dataset.dragInitialized, 'true');
  assert.deepEqual(Object.keys(container.events), ['mousedown', 'mouseleave', 'mouseup', 'mousemove']);
  timers[4].fn(); // Re-registration keeps existing listeners.
});

test('PDF callback absent elements and child scroll fallbacks retain behavior', () => {
  let observer;
  const child = {scrollHeight: 100, clientHeight: 20, scrollTo: value => { child.scrolled = {...value}; }};
  const document = documentFor({'#answer-panel': {scrollHeight: 10, clientHeight: 20,
    children: [{scrollHeight: 5, clientHeight: 20}, child]}, '#answer-expand': {}});
  const {fn, timers} = callback('pdfview', {document, fullTextSearch: () => undefined,
    MutationObserver: class { constructor(changed) { observer = changed; } observe() {} },
  });
  assert.deepEqual(Array.from(fn()), [0]);
  for (const timer of timers) if (typeof timer.fn === 'function') timer.fn();
  assert.deepEqual(child.scrolled, {top: 100, behavior: 'smooth'});
  observer([]); assert.equal(child.scrollTop, 100);
});

test('drag alias retains mouse and single-touch behavior, styles, speed and one-time listeners', () => {
  const container = preview();
  const {fn, timers} = callback('preview_drag_pan', {document: documentFor({}, {
    '.pdf-preview-shell': [container], '.docx-preview': [container],
    '.pptx-preview-shell': [container], '.xlsx-preview-shell': [container],
  })});
  fn(); assert.deepEqual(Object.keys(container.events), []);
  assert.equal(timers[0].delay, 100); timers[0].fn();
  const fire = (name, rest = {}) => container.events[name].fn({preventDefault() {}, ...rest});
  fire('mousemove', {pageX: 40, pageY: 50}); assert.equal(container.scrollLeft, 100);
  fire('mousedown', {pageX: 20, pageY: 30});
  assert.equal(container.style.cursor, 'grabbing'); assert.equal(container.style.userSelect, 'none');
  fire('mousemove', {pageX: 40, pageY: 50});
  assert.equal(container.scrollLeft, 70); assert.equal(container.scrollTop, 170);
  fire('mouseleave'); assert.equal(container.style.cursor, 'grab'); assert.equal(container.style.userSelect, '');
  fire('mouseup');
  fire('touchstart', {touches: [{pageX: 20, pageY: 30}, {}]});
  fire('touchmove', {touches: [{pageX: 40, pageY: 50}]}); assert.equal(container.scrollLeft, 70);
  fire('touchstart', {touches: [{pageX: 20, pageY: 30}]});
  fire('touchmove', {touches: [{pageX: 40, pageY: 50}]}); assert.equal(container.scrollLeft, 40);
  fire('touchend');
  fire('touchmove', {touches: [{pageX: 70, pageY: 80}]}); assert.equal(container.scrollLeft, 40);
  assert.equal(container.events.touchstart.options.passive, false);
  assert.equal(container.events.touchmove.options.passive, false);
  timers[0].fn();
});

const test = require("node:test");
const assert = require("node:assert/strict");
const { createFileBrowserRefresh } = require("./file_browser_refresh.js");

function browser() {
  const listeners = {};
  const document = {
    root: {},
    querySelector: () => document.root,
    addEventListener: (type, callback, capture) => {
      assert.equal(capture, true);
      listeners[type] = callback;
    },
  };
  let epoch = 0;
  return {
    document, listeners,
    guard: createFileBrowserRefresh(document, () => String(++epoch)),
  };
}

const skipped = count => Array.from({ length: count }, () => ({ __type__: "update" }));
function files(guard, filter = "", selected = [], conversation = "") {
  return { stamp: guard.captureFiles(1), filter, selected, conversation,
    outputs: [[{ id: "owned" }], "cards", "focus", "summary"] };
}
function selector(guard, selected = [], index = 1, changed = false) {
  return { stamp: guard.captureSelector(index, changed), selected,
    update: { __type__: "update", value: selected, choices: [["owned", "owned"]] },
    options: [["owned", "owned"]], available_ids: ["owned"] };
}

test("late initialization and reverse filter returns cannot overwrite the latest intent", () => {
  const {guard} = browser();
  const initial = files(guard);
  guard.filterChanged();
  const a = files(guard, "A");
  guard.filterChanged();
  const b = files(guard, "B");
  assert.equal(guard.applyFiles(b, "B", [], ""), b.outputs);
  assert.deepEqual(guard.applyFiles(a, "B", [], ""), skipped(4));
  assert.deepEqual(guard.applyFiles(initial, "B", [], ""), skipped(4));
});

test("A to B to A invalidates old A before the next backend call starts", () => {
  const {guard, listeners} = browser();
  const a = files(guard, "A");
  const event = {target: {closest: query => query === "#chat-file-filter"}};
  listeners.input(event);
  listeners.input(event);
  assert.deepEqual(guard.applyFiles(a, "A", [], ""), skipped(4));
  const latest = files(guard, "A");
  assert.equal(latest.stamp.viewVersion, a.stamp.viewVersion);
  assert.equal(guard.applyFiles(latest, "A", [], ""), latest.outputs);
});

test("scope and conversation changes reject all four outputs together", () => {
  const {guard} = browser();
  const a = files(guard, "", ["owned"], "conversation-a");
  assert.deepEqual(guard.applyFiles(a, "", [], "conversation-a"), skipped(4));
  assert.deepEqual(guard.applyFiles(a, "", ["owned"], "conversation-b"), skipped(4));
  guard.viewChanged();
  assert.deepEqual(guard.applyFiles(a, "", ["owned"], "conversation-a"), skipped(4));
});

test("catalog notifications reject old selector and file results without canceling operations", () => {
  const {guard} = browser();
  const oldSelector = selector(guard);
  const oldFiles = files(guard);
  const notification = selector(guard, [], 1, true);
  assert.deepEqual(guard.applyFiles(oldFiles, "", [], ""), skipped(4));
  assert.deepEqual(guard.applySelector(oldSelector, []), skipped(2));
  assert.deepEqual(guard.applySelector(notification, []), [notification.update, notification.options]);
});

test("overlapping initial reads do not suspend a current filter result", () => {
  const {guard} = browser();
  const first = selector(guard);
  const payload = files(guard, ".txt");
  selector(guard);
  files(guard, "");
  assert.equal(guard.applyFiles(payload, ".txt", [], ""), payload.outputs);
  assert.equal(guard.applySelector(first, [])[1], first.options);
});

test("reverse results within the same intent retain browser issuance order", () => {
  const {guard} = browser();
  const first = files(guard), last = files(guard);
  assert.equal(guard.applyFiles(last, "", [], ""), last.outputs);
  assert.deepEqual(guard.applyFiles(first, "", [], ""), skipped(4));
  const initial = selector(guard), latest = selector(guard);
  assert.equal(guard.applySelector(latest, [])[1], latest.options);
  assert.deepEqual(guard.applySelector(initial, []), skipped(2));
});

test("a catalog refresh preserves later selections, but excludes deleted sources", () => {
  const {guard} = browser();
  const payload = selector(guard, ["old"]);
  guard.viewChanged();
  const [update, options] = guard.applySelector(payload, ["owned", "deleted"]);
  assert.deepEqual(update.value, ["owned"]);
  assert.equal(options, payload.options);
  assert.deepEqual(payload.update.value, ["old"]);
});

test("selector indexes, browsers and remounts have independent generations", () => {
  const a = browser(), b = browser();
  const first = selector(a.guard, [], 1), second = selector(a.guard, [], 2);
  selector(b.guard);
  selector(b.guard);
  assert.equal(a.guard.applySelector(first, [])[1], first.options);
  assert.equal(a.guard.applySelector(second, [])[1], second.options);
  const old = files(a.guard);
  a.document.root = {};
  assert.deepEqual(a.guard.applyFiles(old, "", [], ""), skipped(4));
  assert.deepEqual(a.guard.applySelector(first, []), skipped(2));
});

test("missing payloads skip; empty selection and new conversation remain valid", () => {
  const {guard, listeners} = browser();
  assert.deepEqual(guard.applyFiles(null, "", [], ""), skipped(4));
  assert.deepEqual(guard.applySelector(null, []), skipped(2));
  listeners.input({target: {}});
  listeners.click({target: {}});
  listeners.keydown({key: "Escape", target: {}});
  const payload = files(guard, "", null, null);
  assert.equal(guard.applyFiles(payload, "", [], ""), payload.outputs);
});

test("upload completion retains indexing while preserving a later source intent", () => {
  const {guard} = browser();
  const stamp = guard.captureUpload("file");
  const result = {stamp, ids: ["newly-indexed"], conversation: "original"};
  guard.viewChanged();
  assert.deepEqual(guard.applyUploadReset(result), [{__type__: "update", value: null}, ...skipped(1)]);
  assert.deepEqual(guard.applyUploadSelection(result, "original"), skipped(1));
  assert.deepEqual(result.ids, ["newly-indexed"]);
});

test("filtering leaves the normal uploaded selection intact; a newer upload owns the reset", () => {
  const {guard} = browser();
  const stamp = guard.captureUpload("file");
  const result = {stamp, ids: ["newly-indexed"], conversation: null};
  guard.filterChanged();
  assert.deepEqual(guard.applyUploadReset(result), [{__type__: "update", value: null}, {__type__: "update", value: "select"}]);
  assert.deepEqual(guard.applyUploadSelection(result, ""), [["newly-indexed"]]);
  assert.deepEqual(guard.applyUploadSelection(result, "different"), skipped(1));
  guard.uploadChanged("file");
  assert.deepEqual(guard.applyUploadReset(result), skipped(2));
});

test("card choices reject both late results and stale input snapshots before preview", () => {
  const {guard, listeners} = browser();
  const click = id => listeners.click({target: {
    closest: query => query === "[data-chat-file-id]" ? {dataset: {chatFileId: id}} : null,
  }});
  click("a");
  const first = {stamp: guard.captureFileSelection(), file_id: "a", outputs: ["select", ["a"], ""]};
  click("b");
  const latest = {stamp: guard.captureFileSelection(), file_id: "b", outputs: ["select", ["b"], ""]};
  assert.deepEqual(guard.applyFileSelection(first), skipped(4));
  assert.deepEqual(guard.applyFileSelection({...first, stamp: latest.stamp}), skipped(4));
  assert.deepEqual(guard.applyFileSelection(latest).slice(0, 3), latest.outputs);
  assert.equal(typeof guard.applyFileSelection(latest)[3], "string");
  assert.deepEqual(guard.applyFileSelection({...latest, file_id: ""}), skipped(4));
  assert.deepEqual(guard.applyFileSelection(null), skipped(4));
  assert.deepEqual(guard.applyUploadReset(null), skipped(2));
  assert.deepEqual(guard.applyUploadSelection(null, ""), skipped(1));
});

function card(guard, listeners, id, index = 1) {
  listeners.click({target: {closest: query => query === "[data-chat-file-id]" ? {dataset: {chatFileId: id}} : null}});
  return {stamp: guard.captureFileSelection(index), file_id: id,
    outputs: ["select", {__type__: "update", value: [id]}, ""]};
}

test("old initialization cannot clear a newer card choice in either assignment order", () => {
  for (const order of [["card", "selector"], ["selector", "card"]]) {
    const {guard, listeners} = browser();
    const initial = selector(guard);
    const choice = card(guard, listeners, "owned");
    // Real Gradio's async input collection can snapshot both calls before a flush.
    const updates = {card: guard.applyFileSelection(choice)[1], selector: guard.applySelector(initial, [])[0]};
    const component = {value: [], choices: []};
    for (const writer of order) {
      const {__type__, ...properties} = updates[writer];
      Object.assign(component, properties);
    }
    assert.deepEqual(component.value, ["owned"]);
    assert.deepEqual(component.choices, initial.update.choices);
    assert.deepEqual(initial.update.value, [], "the backend payload is not mutated");
  }
});

test("empty, revoked and unrelated selector updates still apply after a card intent", () => {
  const {guard, listeners} = browser();
  const initial = selector(guard), otherIndex = selector(guard, [], 2);
  card(guard, listeners, "owned");
  assert.deepEqual(guard.applySelector(otherIndex, [])[0].value, []);
  const revoked = {...initial, available_ids: [], update: {...initial.update, choices: [], value: []}};
  assert.deepEqual(guard.applySelector(revoked, [])[0].value, []);
  assert.deepEqual(guard.applySelector(initial, ["owned", "deleted"])[0].value, ["owned"]);
  guard.viewChanged(); // mode switch, explicit scope/clear, conversation or Group intent
  assert.deepEqual(guard.applySelector(initial, [])[0].value, []);
  assert.deepEqual(guard.applySelector(initial, ["owned"])[0].value, ["owned"]);
  const current = selector(guard);
  assert.deepEqual(guard.applySelector(current, [])[0].value, []);
});

test("a different browser's pending card does not change initialization", () => {
  const first = browser(), other = browser();
  const initial = selector(other.guard);
  card(first.guard, first.listeners, "owned");
  assert.deepEqual(other.guard.applySelector(initial, [])[0].value, []);
});

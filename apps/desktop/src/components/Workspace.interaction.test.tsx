import assert from "node:assert/strict";
import test from "node:test";

import type { SessionDetail } from "../../shared/session-contracts";
import { dispatch, renderInDom, setInputValue } from "../test-dom";
import { Workspace } from "./Workspace";

const detail: SessionDetail = {
  conversation_id: "session-1",
  name: "Keyboard task",
  messages: [],
  graph_source_ids: ["file-1"],
  origin: "desktop",
  is_public: false,
  date_created: "2026-08-11T10:00:00Z",
  date_updated: "2026-08-11T10:00:00Z",
};

function workspace(onSubmitQuestion: (prompt: string) => void) {
  return (
    <Workspace
      answerActionPending={false}
      modelName="desktop-chat"
      onCancelAnswer={() => undefined}
      onOpenSources={() => undefined}
      onRetryAnswer={() => undefined}
      onRetrySession={() => undefined}
      onSubmitQuestion={onSubmitQuestion}
      onToggleInspector={() => undefined}
      selectedSourceCount={1}
      session={{ status: "success", data: detail }}
    />
  );
}

test("Enter sends once while repeat and composing Enter do not submit", async () => {
  const submitted: string[] = [];
  const rendered = await renderInDom(workspace((prompt) => submitted.push(prompt)));
  try {
    const input = rendered.document.querySelector<HTMLTextAreaElement>("#task-input")!;
    await setInputValue(input, "One question");
    await dispatch(
      input,
      new rendered.window.KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Enter",
      }),
    );
    await dispatch(
      input,
      new rendered.window.KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Enter",
        repeat: true,
      }),
    );
    await dispatch(
      input,
      new rendered.window.KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        isComposing: true,
        key: "Enter",
      }),
    );

    assert.deepEqual(submitted, ["One question"]);
  } finally {
    await rendered.cleanup();
  }
});

test("Alt+Enter inserts one newline at the selection and restores the caret", async () => {
  const submitted: string[] = [];
  const rendered = await renderInDom(workspace((prompt) => submitted.push(prompt)));
  try {
    const input = rendered.document.querySelector<HTMLTextAreaElement>("#task-input")!;
    await setInputValue(input, "alpha beta");
    input.setSelectionRange(5, 6);
    const event = new rendered.window.KeyboardEvent("keydown", {
      altKey: true,
      bubbles: true,
      cancelable: true,
      key: "Enter",
    });
    await dispatch(input, event);

    assert.equal(event.defaultPrevented, true);
    assert.equal(input.value, "alpha\nbeta");
    assert.equal(input.selectionStart, 6);
    assert.equal(input.selectionEnd, 6);
    assert.deepEqual(submitted, []);
  } finally {
    await rendered.cleanup();
  }
});

test("Ctrl+Enter and Meta+Enter remain compatible single-submit shortcuts", async () => {
  for (const modifier of ["ctrlKey", "metaKey"] as const) {
    const submitted: string[] = [];
    const rendered = await renderInDom(workspace((prompt) => submitted.push(prompt)));
    try {
      const input = rendered.document.querySelector<HTMLTextAreaElement>("#task-input")!;
      await setInputValue(input, "Compatible shortcut");
      await dispatch(
        input,
        new rendered.window.KeyboardEvent("keydown", {
          bubbles: true,
          cancelable: true,
          key: "Enter",
          [modifier]: true,
        }),
      );
      assert.deepEqual(submitted, ["Compatible shortcut"]);
    } finally {
      await rendered.cleanup();
    }
  }
});

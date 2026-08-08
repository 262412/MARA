import assert from "node:assert/strict";
import test from "node:test";

import { chooseFilesForIndex } from "./file-import";

test("native import keeps selected paths in Main and supports cancellation", async () => {
  let receivedOptions: unknown;
  const selected = await chooseFilesForIndex(async (options) => {
    receivedOptions = options;
    return {
      canceled: false,
      filePaths: ["/private/source/paper.pdf", "/private/source/notes.md"],
    };
  });

  assert.deepEqual(selected, [
    "/private/source/paper.pdf",
    "/private/source/notes.md",
  ]);
  assert.deepEqual(receivedOptions, {
    title: "添加到 MARA",
    buttonLabel: "开始索引",
    properties: ["openFile", "multiSelections"],
  });
  assert.deepEqual(
    await chooseFilesForIndex(async () => ({ canceled: true, filePaths: [] })),
    [],
  );
});

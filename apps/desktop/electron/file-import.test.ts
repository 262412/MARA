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
  }, [".pdf", ".md", ".csv"]);

  assert.deepEqual(selected, [
    "/private/source/paper.pdf",
    "/private/source/notes.md",
  ]);
  assert.deepEqual(receivedOptions, {
    title: "添加到 MARA",
    buttonLabel: "开始索引",
    properties: ["openFile", "multiSelections"],
    filters: [
      {
        name: "MARA 支持的文档",
        extensions: ["pdf", "md", "csv"],
      },
    ],
  });
  assert.deepEqual(
    await chooseFilesForIndex(
      async () => ({ canceled: true, filePaths: [] }),
      [".txt"],
    ),
    [],
  );
});

test("native import rejects malformed or empty capability extensions", async () => {
  const showOpenDialog = async () => ({ canceled: true, filePaths: [] });

  await assert.rejects(
    chooseFilesForIndex(showOpenDialog, [".pdf", "../private"]),
    /invalid extension/,
  );
  await assert.rejects(
    chooseFilesForIndex(showOpenDialog, []),
    /no supported file extensions/,
  );
});

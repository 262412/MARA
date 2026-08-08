import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import {
  chooseFilesForIndex,
  validateDroppedPathsForIndex,
} from "./file-import";

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

test("dropped import accepts only absolute paths with supported extensions", () => {
  const paper = path.resolve("private", "source", "paper.pdf");
  const notes = path.resolve("private", "source", "notes.md");

  assert.deepEqual(
    validateDroppedPathsForIndex([paper, notes], [".pdf", ".md"]),
    [paper, notes],
  );
  assert.throws(
    () => validateDroppedPathsForIndex(["relative/paper.pdf"], [".pdf"]),
    /invalid dropped file path/,
  );
  assert.throws(
    () => validateDroppedPathsForIndex([paper], [".txt"]),
    /unsupported dropped file type/,
  );
  assert.throws(
    () => validateDroppedPathsForIndex([paper, paper], [".pdf"]),
    /must be unique/,
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

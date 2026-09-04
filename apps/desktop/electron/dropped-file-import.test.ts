import assert from "node:assert/strict";
import test from "node:test";

import { resolveDroppedFilePaths } from "./dropped-file-import";

test("resolves disk-backed drop paths without returning them to Renderer code", () => {
  const first = {} as File;
  const second = {} as File;
  const paths = new Map<File, string>([
    [first, "/private/source/paper.pdf"],
    [second, "/private/source/notes.md"],
  ]);

  assert.deepEqual(
    resolveDroppedFilePaths([first, second, first], (file) =>
      paths.get(file) ?? "",
    ),
    ["/private/source/paper.pdf", "/private/source/notes.md"],
  );
});

test("rejects synthetic, empty, and oversized dropped file lists", () => {
  assert.throws(
    () => resolveDroppedFilePaths([{} as File], () => ""),
    /disk-backed/,
  );
  assert.throws(() => resolveDroppedFilePaths([], () => "unused"), /1 and 64/);
  assert.throws(
    () =>
      resolveDroppedFilePaths(
        Array.from({ length: 65 }, () => ({}) as File),
        () => "/private/source/paper.pdf",
      ),
    /1 and 64/,
  );
});

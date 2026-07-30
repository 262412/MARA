import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import type { FileRecord } from "../../shared/file-contracts";
import type { ResourceState } from "../resource-state";
import { FilesPage } from "./FilesPage";

const file: FileRecord = {
  file_id: "file-1",
  name: "paper.pdf",
  size: 1024,
  tokens: 42,
  loader: "PDFLoader",
  date_created: "2026-07-30T10:00:00",
};

function render(state: ResourceState<FileRecord[]>) {
  return renderToStaticMarkup(<FilesPage files={state} onRetry={() => undefined} />);
}

test("Files page covers loading, success, empty, and failed states", () => {
  assert.match(render({ status: "loading" }), /正在读取文件/);
  assert.match(render({ status: "success", data: [file] }), /paper\.pdf/);
  assert.match(render({ status: "success", data: [] }), /还没有已索引文件/);
  assert.match(
    render({ status: "failed", message: "无法读取文件" }),
    /无法读取文件/,
  );
  assert.match(
    render({ status: "failed", message: "无法读取文件" }),
    /重试/,
  );
});

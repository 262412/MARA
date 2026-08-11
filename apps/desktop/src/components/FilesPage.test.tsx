import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import type { FileRecord } from "../../shared/file-contracts";
import type { IndexTask } from "../../shared/index-task-contracts";
import type { SidecarError } from "../../shared/runtime-contracts";
import type { ResourceState } from "../resource-state";
import {
  FilesPage,
  canAcceptFileDrop,
  isFileDrag,
} from "./FilesPage";

const file: FileRecord = {
  file_id: "file-1",
  name: "paper.pdf",
  size: 1024,
  tokens: 42,
  loader: "PDFLoader",
  date_created: "2026-07-30T10:00:00",
};

const task: IndexTask = {
  task_id: "task-1",
  status: "running",
  stage: "indexing",
  completed_files: 1,
  total_files: 2,
  file_names: ["paper.pdf", "notes.md"],
  success_count: 1,
  failure_count: 0,
  failures: [],
  error: null,
  retryable: false,
  created_at: "2026-08-08T10:00:00Z",
  updated_at: "2026-08-08T10:00:01Z",
  version: 2,
};

type IndexingReadiness = {
  indexing_ready: boolean;
  indexing_issue_code: string | null;
  indexing_message: string;
  indexing_action:
    | "none"
    | "configure_embedding"
    | "repair_installation"
    | "check_connection"
    | "free_storage"
    | "contact_support";
  request_id: string;
};

const readyIndexing: IndexingReadiness = {
  indexing_ready: true,
  indexing_issue_code: null,
  indexing_message: "File indexing is ready.",
  indexing_action: "none",
  request_id: "doctor-ready",
};

function render(
  state: ResourceState<FileRecord[]>,
  indexTask?: IndexTask,
  actionError?: SidecarError,
  selectedFileIds: string[] = [],
  indexing = readyIndexing,
) {
  return renderToStaticMarkup(
    <FilesPage
      actionError={actionError}
      deletingFileIds={[]}
      files={state}
      indexing={indexing}
      indexActionPending={false}
      indexTask={indexTask}
      onCancelIndexTask={() => undefined}
      onDelete={() => undefined}
      onDropFiles={() => undefined}
      onImport={() => undefined}
      onOpenEmbeddingConfiguration={() => undefined}
      onRetry={(): void => undefined}
      onRetryIndexTask={() => undefined}
      onSelectionChange={() => undefined}
      selectedFileIds={selectedFileIds}
    />,
  );
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

test("Files page exposes import, progress, cancellation, retry, and deletion", () => {
  const running = render({ status: "success", data: [file] }, task);
  assert.match(running, /添加文件/);
  assert.match(running, /正在索引 1\/2/);
  assert.match(running, /取消索引/);
  assert.match(running, /删除 paper\.pdf/);
  assert.match(running, /选择 paper\.pdf/);
  assert.match(running, /选择全部文件/);
  assert.match(running, /将文件拖到此页面/);
  assert.match(running, /Ctrl\+O/);

  const failed = render(
    { status: "success", data: [file] },
    {
      ...task,
      status: "failed",
      error: {
        code: "index_failed",
        message: "MARA could not index the selected files.",
        retryable: true,
      },
      retryable: true,
    },
    {
      code: "file_delete_failed",
      message: "无法删除文件",
      details: null,
      retryable: true,
      request_id: "delete-request",
    },
  );
  assert.match(failed, /索引失败/);
  assert.match(failed, /重试索引/);
  assert.match(failed, /无法删除文件/);

  const cancelled = render(
    { status: "success", data: [] },
    { ...task, status: "cancelled", retryable: true },
  );
  assert.match(cancelled, /索引已取消/);
  assert.doesNotMatch(cancelled, /下一个纵向切片/);
});

test("Files page exposes accessible bulk selection and destructive action state", () => {
  const secondFile: FileRecord = {
    ...file,
    file_id: "file-2",
    name: "notes.md",
  };
  const selected = render(
    { status: "success", data: [file, secondFile] },
    undefined,
    undefined,
    ["file-1", "file-2"],
  );

  assert.match(selected, /已选 2 个/);
  assert.match(selected, /删除所选/);
  assert.match(selected, /aria-selected="true"/);
  assert.match(selected, /aria-label="选择全部文件"/);
});

test("Files page activates its drop target only for file payloads", () => {
  assert.equal(isFileDrag(["Files"]), true);
  assert.equal(isFileDrag(["text/plain"]), false);
  assert.equal(canAcceptFileDrop(true, false), true);
  assert.equal(canAcceptFileDrop(false, false), false);
  assert.equal(canAcceptFileDrop(true, true), false);
});

test("Files page blocks import and drop until embedding is configured", () => {
  const blocked = render(
    { status: "success", data: [] },
    undefined,
    undefined,
    [],
    {
      indexing_ready: false,
      indexing_issue_code: "embedding_not_configured",
      indexing_message: "Configure an embedding model before indexing files.",
      indexing_action: "configure_embedding",
      request_id: "doctor-no-embedding",
    },
  );

  assert.match(blocked, /配置 Embedding/);
  assert.match(blocked, /embedding_not_configured/);
  assert.match(blocked, /doctor-no-embedding/);
  assert.match(blocked, /保存配置后重启 MARA Desktop/);
  assert.match(blocked, /添加文件<\/button>/);
  assert.match(blocked, /disabled=""/);
  assert.doesNotMatch(blocked, /释放文件以开始索引/);
});

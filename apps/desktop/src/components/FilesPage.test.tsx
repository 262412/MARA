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
  assert.match(render({ status: "loading" }), /Loading files/);
  assert.match(render({ status: "success", data: [file] }), /paper\.pdf/);
  assert.match(render({ status: "success", data: [] }), /No indexed files yet/);
  assert.match(
    render({ status: "failed", message: "Could not read files" }),
    /Could not read files/,
  );
  assert.match(
    render({ status: "failed", message: "Could not read files" }),
    /Retry/,
  );
});

test("Files page exposes import, progress, cancellation, retry, and deletion", () => {
  const running = render({ status: "success", data: [file] }, task);
  assert.match(running, /Add files/);
  assert.match(running, /Indexing 1\/2/);
  assert.match(running, /Cancel indexing/);
  assert.match(running, /Delete paper\.pdf/);
  assert.match(running, /Select paper\.pdf/);
  assert.match(running, /Select all files/);
  assert.match(running, /Drop files on this page/);
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
      message: "Could not delete files",
      details: null,
      retryable: true,
      request_id: "delete-request",
    },
  );
  assert.match(failed, /Indexing failed/);
  assert.match(failed, /Retry indexing/);
  assert.match(failed, /Could not delete files/);

  const cancelled = render(
    { status: "success", data: [] },
    { ...task, status: "cancelled", retryable: true },
  );
  assert.match(cancelled, /Indexing cancelled/);
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

  assert.match(selected, /Selected 2/);
  assert.match(selected, /Delete selected/);
  assert.match(selected, /aria-selected="true"/);
  assert.match(selected, /aria-label="Select all files"/);
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

  assert.match(blocked, /Configure Embedding/);
  assert.match(blocked, /embedding_not_configured/);
  assert.match(blocked, /doctor-no-embedding/);
  assert.match(blocked, /Restart MARA Desktop after saving the configuration/);
  assert.match(blocked, /Add files<\/button>/);
  assert.match(blocked, /disabled=""/);
  assert.doesNotMatch(blocked, /Release files to start indexing/);
});

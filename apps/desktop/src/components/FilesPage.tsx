import {
  useEffect,
  useRef,
  useState,
  type DragEvent,
} from "react";

import type { DoctorPayload } from "../../shared/doctor-contracts";
import type { FileRecord } from "../../shared/file-contracts";
import type { IndexTask } from "../../shared/index-task-contracts";
import type { SidecarError } from "../../shared/runtime-contracts";
import { useLanguage, type Translate } from "../i18n";
import type { ResourceState } from "../resource-state";
import { Icon } from "./Icon";

type FilesPageProps = {
  actionError?: SidecarError;
  deletingFileIds: string[];
  files: ResourceState<FileRecord[]>;
  indexing: Pick<
    DoctorPayload,
    | "indexing_ready"
    | "indexing_issue_code"
    | "indexing_message"
    | "indexing_action"
    | "request_id"
  >;
  indexActionPending: boolean;
  indexTask?: IndexTask;
  onCancelIndexTask: () => void;
  onDelete: (files: FileRecord[]) => void;
  onDropFiles: (files: File[]) => void;
  onImport: () => void;
  onOpenEmbeddingConfiguration: () => void;
  onRetry: () => void;
  onRetryIndexTask: () => void;
  onSelectionChange: (fileIds: string[]) => void;
  selectedFileIds: string[];
};

export function FilesPage({
  actionError,
  deletingFileIds,
  files,
  indexing,
  indexActionPending,
  indexTask,
  onCancelIndexTask,
  onDelete,
  onDropFiles,
  onImport,
  onOpenEmbeddingConfiguration,
  onRetry,
  onRetryIndexTask,
  onSelectionChange,
  selectedFileIds,
}: FilesPageProps) {
  const { t, language } = useLanguage();
  const [dropActive, setDropActive] = useState(false);
  const dragDepth = useRef(0);
  const availableFiles = files.status === "success" ? files.data : [];
  const selectedSet = new Set(selectedFileIds);
  const selectedFiles = availableFiles.filter((file) =>
    selectedSet.has(file.file_id),
  );
  const allSelected =
    availableFiles.length > 0 && selectedFiles.length === availableFiles.length;
  const selectionDisabled = deletingFileIds.length > 0;
  const dropEnabled = canAcceptFileDrop(
    indexing.indexing_ready,
    indexActionPending,
  );

  const handleDragEnter = (event: DragEvent<HTMLElement>) => {
    if (!hasFilePayload(event)) {
      return;
    }
    event.preventDefault();
    dragDepth.current += 1;
    if (dropEnabled) {
      setDropActive(true);
    }
  };
  const handleDragOver = (event: DragEvent<HTMLElement>) => {
    event.preventDefault();
    if (!hasFilePayload(event)) {
      event.dataTransfer.dropEffect = "none";
      return;
    }
    event.dataTransfer.dropEffect = dropEnabled ? "copy" : "none";
  };
  const handleDragLeave = () => {
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) {
      setDropActive(false);
    }
  };
  const handleDrop = (event: DragEvent<HTMLElement>) => {
    event.preventDefault();
    if (!hasFilePayload(event)) {
      return;
    }
    dragDepth.current = 0;
    setDropActive(false);
    if (!dropEnabled) {
      return;
    }
    const droppedFiles = Array.from(event.dataTransfer.files);
    if (droppedFiles.length > 0) {
      onDropFiles(droppedFiles);
    }
  };

  return (
    <main
      aria-busy={indexActionPending}
      aria-describedby="file-drop-instructions"
      className={`workspace files-page${dropActive ? " drop-active" : ""}`}
      id="main-workspace"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      <span className="sr-only" id="file-drop-instructions">
        {t("files.dropInstructions")}
      </span>
      <header className="workspace-toolbar">
        <div>
          <p className="eyebrow">{t("files.eyebrow")}</p>
          <h1>{t("nav.files")}</h1>
        </div>
        <div className="files-toolbar-actions">
          {selectedFiles.length > 0 ? (
            <>
              <span className="source-count" role="status">
                {t("files.selectedCount", { count: selectedFiles.length })}
              </span>
              <button
                className="danger-button"
                disabled={selectionDisabled}
                onClick={() => onDelete(selectedFiles)}
                type="button"
              >
                {selectionDisabled
                  ? t("files.deletePending")
                  : t("files.deleteSelected")}
              </button>
            </>
          ) : null}
          {files.status === "success" ? (
            <span className="source-count">
              {t("files.fileCount", { count: files.data.length })}
            </span>
          ) : null}
          <button
            className="primary-button"
            disabled={!indexing.indexing_ready || indexActionPending}
            onClick={onImport}
            type="button"
          >
            {indexActionPending ? t("files.addPending") : t("files.add")}
          </button>
        </div>
      </header>
      <div className="files-content">
        {dropActive && dropEnabled ? (
          <div className="file-drop-overlay" role="status" aria-live="polite">
            <strong>{t("files.dropTitle")}</strong>
            <span>{t("files.dropDetail")}</span>
          </div>
        ) : null}
        {!indexing.indexing_ready ? (
          <IndexingReadinessCard
            indexing={indexing}
            onOpenEmbeddingConfiguration={onOpenEmbeddingConfiguration}
            pending={indexActionPending}
          />
        ) : null}
        {indexTask ? (
          <IndexTaskStatus
            onCancel={onCancelIndexTask}
            onRetry={onRetryIndexTask}
            pending={indexActionPending}
            task={indexTask}
          />
        ) : null}
        {actionError ? (
          <section className="file-action-error" role="alert">
            <strong>{actionError.message}</strong>
            <span>{t("common.errorCode", { code: actionError.code })}</span>
            <span>{t("common.requestId", { id: actionError.request_id })}</span>
            <span>{indexingActionGuidance(actionError.code, t)}</span>
          </section>
        ) : null}
        {files.status === "loading" ? (
          <ResourceMessage
            title={t("files.loadingTitle")}
            detail={t("files.loadingDetail")}
          />
        ) : null}
        {files.status === "failed" ? (
          <ResourceMessage
            title={files.message}
            detail={requestDetail(files.error?.request_id, t)}
            onRetry={onRetry}
          />
        ) : null}
        {files.status === "success" && files.data.length === 0 ? (
          <ResourceMessage
            title={t("files.emptyTitle")}
            detail={t("files.emptyDetail")}
          />
        ) : null}
        {files.status === "success" && files.data.length > 0 ? (
          <div
            className="file-table"
            role="table"
            aria-label={t("files.tableAria")}
          >
            <div className="file-table-header" role="row">
              <span role="columnheader">
                <SelectAllCheckbox
                  checked={allSelected}
                  disabled={selectionDisabled}
                  mixed={selectedFiles.length > 0 && !allSelected}
                  onChange={(checked) =>
                    onSelectionChange(
                      checked ? availableFiles.map((file) => file.file_id) : [],
                    )
                  }
                />
              </span>
              <span role="columnheader">{t("files.name")}</span>
              <span role="columnheader">{t("files.loader")}</span>
              <span role="columnheader">{t("files.tokens")}</span>
              <span role="columnheader">{t("files.size")}</span>
              <span role="columnheader">{t("files.created")}</span>
              <span role="columnheader">{t("files.actions")}</span>
            </div>
            {files.data.map((file) => (
              <div
                aria-selected={selectedSet.has(file.file_id)}
                className="file-table-row"
                role="row"
                key={file.file_id}
              >
                <span role="cell">
                  <label className="file-select-control">
                    <input
                      aria-label={t("files.selectAria", {
                        name: file.name || t("common.unnamedFile"),
                      })}
                      checked={selectedSet.has(file.file_id)}
                      disabled={selectionDisabled}
                      onChange={(event) =>
                        onSelectionChange(
                          event.currentTarget.checked
                            ? [...selectedFileIds, file.file_id]
                            : selectedFileIds.filter(
                                (fileId) => fileId !== file.file_id,
                              ),
                        )
                      }
                      type="checkbox"
                    />
                  </label>
                </span>
                <span className="file-name" role="cell">
                  <span className="file-record-icon" aria-hidden="true">
                    <Icon name="files" size={15} />
                  </span>
                  <strong>{file.name || t("common.unnamedFile")}</strong>
                </span>
                <span role="cell">{file.loader || t("common.none")}</span>
                <span role="cell">{file.tokens.toLocaleString()}</span>
                <span role="cell">{formatBytes(file.size)}</span>
                  <span role="cell">
                    {formatDate(file.date_created, language)}
                  </span>
                <span role="cell">
                  <button
                    aria-label={t("files.deleteAria", {
                      name: file.name || t("common.unnamedFile"),
                    })}
                    className="file-delete-button"
                    disabled={selectionDisabled}
                    onClick={() => onDelete([file])}
                    type="button"
                  >
                    {deletingFileIds.includes(file.file_id)
                      ? t("files.deletePending")
                      : t("common.delete")}
                  </button>
                </span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </main>
  );
}

function hasFilePayload(event: DragEvent<HTMLElement>): boolean {
  return isFileDrag(Array.from(event.dataTransfer.types));
}

export function isFileDrag(types: readonly string[]): boolean {
  return types.includes("Files");
}

export function canAcceptFileDrop(
  indexingReady: boolean,
  indexActionPending: boolean,
): boolean {
  return indexingReady && !indexActionPending;
}

function IndexingReadinessCard({
  indexing,
  onOpenEmbeddingConfiguration,
  pending,
}: {
  indexing: FilesPageProps["indexing"];
  onOpenEmbeddingConfiguration: () => void;
  pending: boolean;
}) {
  const { t } = useLanguage();
  return (
    <section className="indexing-readiness-card" role="status">
      <div>
        <p className="eyebrow">{t("files.indexingEyebrow")}</p>
        <h2>{t("files.indexingNotReady")}</h2>
        <p>{indexing.indexing_message}</p>
        {indexing.indexing_issue_code ? (
          <p>
            {t("files.issueCode", { code: indexing.indexing_issue_code })}
          </p>
        ) : null}
        <p>{t("common.requestId", { id: indexing.request_id })}</p>
        <p>{indexingActionGuidance(indexing.indexing_issue_code, t)}</p>
      </div>
      {indexing.indexing_action === "configure_embedding" ? (
        <div className="index-task-actions">
          <button
            className="small-button"
            disabled={pending}
            onClick={onOpenEmbeddingConfiguration}
            type="button"
          >
            {pending ? t("common.opening") : t("files.configureEmbedding")}
          </button>
          <span>{t("files.saveConfigRestart")}</span>
        </div>
      ) : null}
    </section>
  );
}

function SelectAllCheckbox({
  checked,
  disabled,
  mixed,
  onChange,
}: {
  checked: boolean;
  disabled: boolean;
  mixed: boolean;
  onChange: (checked: boolean) => void;
}) {
  const { t } = useLanguage();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.indeterminate = mixed;
    }
  }, [mixed]);

  return (
    <label className="file-select-control">
      <input
        aria-checked={mixed ? "mixed" : checked}
        aria-label={t("files.selectAll")}
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.currentTarget.checked)}
        ref={inputRef}
        type="checkbox"
      />
    </label>
  );
}

function IndexTaskStatus({
  onCancel,
  onRetry,
  pending,
  task,
}: {
  onCancel: () => void;
  onRetry: () => void;
  pending: boolean;
  task: IndexTask;
}) {
  const { t, language } = useLanguage();
  const active = task.status === "queued" || task.status === "running";
  const title = indexTaskTitle(task, t);
  return (
    <section className={`index-task-card status-${task.status}`} role="status">
      <div>
        <p className="eyebrow">{t("files.backgroundTask")}</p>
        <h2>{title}</h2>
        <p>{task.file_names.join(language === "zh" ? "、" : ", ")}</p>
        <p>{t("common.taskId", { id: task.task_id })}</p>
        {task.error ? (
          <>
            <p>{task.error.message}</p>
            <p>{t("common.errorCode", { code: task.error.code })}</p>
            <p>{indexingActionGuidance(task.error.code, t)}</p>
          </>
        ) : null}
      </div>
      <div className="index-task-actions">
        {active ? (
          <button
            className="small-button"
            disabled={pending}
            onClick={onCancel}
            type="button"
          >
            {pending ? t("common.processing") : t("files.cancelIndex")}
          </button>
        ) : null}
        {task.retryable ? (
          <button
            className="small-button"
            disabled={pending}
            onClick={onRetry}
            type="button"
          >
            {pending ? t("common.processing") : t("files.retryIndex")}
          </button>
        ) : null}
      </div>
    </section>
  );
}

function indexTaskTitle(task: IndexTask, t: Translate): string {
  switch (task.status) {
    case "queued":
      return t("files.taskQueued");
    case "running":
      return t("files.taskRunning", {
        completed: task.completed_files,
        total: task.total_files,
      });
    case "partial":
      return t("files.taskPartial", {
        completed: task.success_count,
        total: task.total_files,
      });
    case "success":
      return t("files.taskSuccess", { count: task.success_count });
    case "failed":
      return t("files.taskFailed");
    case "cancelled":
      return t("files.taskCancelled");
  }
}

function ResourceMessage({
  title,
  detail,
  onRetry,
}: {
  title: string;
  detail: string;
  onRetry?: () => void;
}) {
  const { t } = useLanguage();
  return (
    <section className="resource-message" role="status">
      <span className="resource-message-mark" aria-hidden="true">
        M
      </span>
      <h2>{title}</h2>
      <p>{detail}</p>
      {onRetry ? (
        <button className="small-button" onClick={onRetry} type="button">
          {t("common.retry")}
        </button>
      ) : null}
    </section>
  );
}

function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string | null, language: "en" | "zh"): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(language === "zh" ? "zh-CN" : "en-US", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

function requestDetail(requestId: string | undefined, t: Translate): string {
  return requestId
    ? t("files.requestDetail", { id: requestId })
    : t("files.sidecarRetry");
}

function indexingActionGuidance(code: string | null, t: Translate): string {
  switch (code) {
    case "embedding_not_configured":
      return t("files.guidanceEmbeddingNotConfigured");
    case "embedding_dependency_missing":
      return t("files.guidanceDependencyMissing");
    case "embedding_unavailable":
      return t("files.guidanceUnavailable");
    case "index_runtime_storage_unwritable":
      return t("files.guidanceStorageUnwritable");
    case "source_permission_denied":
      return t("files.guidanceSourcePermission");
    case "index_database_locked":
      return t("files.guidanceDatabaseLocked");
    case "index_storage_full":
      return t("files.guidanceStorageFull");
    case "index_failed":
      return t("files.guidanceFailed");
    default:
      return t("files.guidancePending");
  }
}

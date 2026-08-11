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
        将文件拖到此页面，或按 Ctrl+O 使用原生文件选择器。
      </span>
      <header className="workspace-toolbar">
        <div>
          <p className="eyebrow">本地数据空间</p>
          <h1>Files</h1>
        </div>
        <div className="files-toolbar-actions">
          {selectedFiles.length > 0 ? (
            <>
              <span className="source-count" role="status">
                已选 {selectedFiles.length} 个
              </span>
              <button
                className="danger-button"
                disabled={selectionDisabled}
                onClick={() => onDelete(selectedFiles)}
                type="button"
              >
                {selectionDisabled ? "删除中…" : "删除所选"}
              </button>
            </>
          ) : null}
          {files.status === "success" ? (
            <span className="source-count">{files.data.length} 个文件</span>
          ) : null}
          <button
            className="primary-button"
            disabled={!indexing.indexing_ready || indexActionPending}
            onClick={onImport}
            type="button"
          >
            {indexActionPending ? "处理中…" : "添加文件"}
          </button>
        </div>
      </header>
      <div className="files-content">
        {dropActive && dropEnabled ? (
          <div className="file-drop-overlay" role="status" aria-live="polite">
            <strong>释放文件以开始索引</strong>
            <span>也可以按 Ctrl+O 使用原生文件选择器</span>
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
            <span>错误代码：{actionError.code}</span>
            <span>请求 ID：{actionError.request_id}</span>
            <span>{indexingActionGuidance(actionError.code)}</span>
          </section>
        ) : null}
        {files.status === "loading" ? (
          <ResourceMessage
            title="正在读取文件"
            detail="正在从 MARA 索引加载真实文件记录。"
          />
        ) : null}
        {files.status === "failed" ? (
          <ResourceMessage
            title={files.message}
            detail={requestDetail(files.error?.request_id)}
            onRetry={onRetry}
          />
        ) : null}
        {files.status === "success" && files.data.length === 0 ? (
          <ResourceMessage
            title="还没有已索引文件"
            detail="添加本地文件后，MARA 会在后台建立索引。"
          />
        ) : null}
        {files.status === "success" && files.data.length > 0 ? (
          <div className="file-table" role="table" aria-label="已索引文件">
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
              <span role="columnheader">名称</span>
              <span role="columnheader">Loader</span>
              <span role="columnheader">Tokens</span>
              <span role="columnheader">大小</span>
              <span role="columnheader">创建时间</span>
              <span role="columnheader">操作</span>
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
                      aria-label={`选择 ${file.name || "未命名文件"}`}
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
                  <strong>{file.name || "未命名文件"}</strong>
                </span>
                <span role="cell">{file.loader || "—"}</span>
                <span role="cell">{file.tokens.toLocaleString()}</span>
                <span role="cell">{formatBytes(file.size)}</span>
                <span role="cell">{formatDate(file.date_created)}</span>
                <span role="cell">
                  <button
                    aria-label={`删除 ${file.name || "未命名文件"}`}
                    className="file-delete-button"
                    disabled={selectionDisabled}
                    onClick={() => onDelete([file])}
                    type="button"
                  >
                    {deletingFileIds.includes(file.file_id) ? "删除中…" : "删除"}
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
  return (
    <section className="indexing-readiness-card" role="status">
      <div>
        <p className="eyebrow">索引准备状态</p>
        <h2>文件索引尚未准备好</h2>
        <p>{indexing.indexing_message}</p>
        {indexing.indexing_issue_code ? (
          <p>问题代码：{indexing.indexing_issue_code}</p>
        ) : null}
        <p>请求 ID：{indexing.request_id}</p>
        <p>{indexingActionGuidance(indexing.indexing_issue_code)}</p>
      </div>
      {indexing.indexing_action === "configure_embedding" ? (
        <div className="index-task-actions">
          <button
            className="small-button"
            disabled={pending}
            onClick={onOpenEmbeddingConfiguration}
            type="button"
          >
            {pending ? "正在打开…" : "配置 Embedding"}
          </button>
          <span>保存配置后重启 MARA Desktop。</span>
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
        aria-label="选择全部文件"
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
  const active = task.status === "queued" || task.status === "running";
  const title = indexTaskTitle(task);
  return (
    <section className={`index-task-card status-${task.status}`} role="status">
      <div>
        <p className="eyebrow">后台索引任务</p>
        <h2>{title}</h2>
        <p>{task.file_names.join("、")}</p>
        <p>任务 ID：{task.task_id}</p>
        {task.error ? (
          <>
            <p>{task.error.message}</p>
            <p>错误代码：{task.error.code}</p>
            <p>{indexingActionGuidance(task.error.code)}</p>
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
            {pending ? "处理中…" : "取消索引"}
          </button>
        ) : null}
        {task.retryable ? (
          <button
            className="small-button"
            disabled={pending}
            onClick={onRetry}
            type="button"
          >
            {pending ? "处理中…" : "重试索引"}
          </button>
        ) : null}
      </div>
    </section>
  );
}

function indexTaskTitle(task: IndexTask): string {
  switch (task.status) {
    case "queued":
      return "等待索引";
    case "running":
      return `正在索引 ${task.completed_files}/${task.total_files}`;
    case "partial":
      return `部分完成：${task.success_count}/${task.total_files}`;
    case "success":
      return `索引完成：${task.success_count} 个文件`;
    case "failed":
      return "索引失败";
    case "cancelled":
      return "索引已取消";
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
  return (
    <section className="resource-message" role="status">
      <span className="resource-message-mark" aria-hidden="true">
        M
      </span>
      <h2>{title}</h2>
      <p>{detail}</p>
      {onRetry ? (
        <button className="small-button" onClick={onRetry} type="button">
          重试
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

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("zh-CN", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

function requestDetail(requestId: string | undefined): string {
  return requestId ? `请求 ID：${requestId}` : "请确认 Sidecar 状态后重试。";
}

function indexingActionGuidance(code: string | null): string {
  switch (code) {
    case "embedding_not_configured":
      return "打开配置文件，填写受支持的 Embedding 配置。";
    case "embedding_dependency_missing":
      return "当前安装包缺少所选 provider；请安装受支持的 MARA Desktop 包。";
    case "embedding_unavailable":
      return "检查模型服务和网络连接后重试。";
    case "index_runtime_storage_unwritable":
      return "检查 MARA Desktop 应用数据目录的写入权限。";
    case "source_permission_denied":
      return "检查源文件读取权限后重新选择该文件。";
    case "index_database_locked":
      return "关闭占用 MARA 数据库的进程后重试。";
    case "index_storage_full":
      return "释放应用数据所在磁盘的空间后重试。";
    case "index_failed":
      return "保留任务和请求 ID，并查看本地索引日志。";
    default:
      return "等待索引准备检查完成后再添加文件。";
  }
}

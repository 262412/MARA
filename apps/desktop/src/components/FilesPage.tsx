import type { FileRecord } from "../../shared/file-contracts";
import type { IndexTask } from "../../shared/index-task-contracts";
import type { ResourceState } from "../resource-state";
import { Icon } from "./Icon";

type FilesPageProps = {
  actionError?: string;
  deletingFileId?: string;
  files: ResourceState<FileRecord[]>;
  indexActionPending: boolean;
  indexTask?: IndexTask;
  onCancelIndexTask: () => void;
  onDelete: (file: FileRecord) => void;
  onImport: () => void;
  onRetry: () => void;
  onRetryIndexTask: () => void;
};

export function FilesPage({
  actionError,
  deletingFileId,
  files,
  indexActionPending,
  indexTask,
  onCancelIndexTask,
  onDelete,
  onImport,
  onRetry,
  onRetryIndexTask,
}: FilesPageProps) {
  return (
    <main className="workspace files-page" id="main-workspace">
      <header className="workspace-toolbar">
        <div>
          <p className="eyebrow">本地数据空间</p>
          <h1>Files</h1>
        </div>
        <div className="files-toolbar-actions">
          {files.status === "success" ? (
            <span className="source-count">{files.data.length} 个文件</span>
          ) : null}
          <button
            className="primary-button"
            disabled={indexActionPending}
            onClick={onImport}
            type="button"
          >
            {indexActionPending ? "处理中…" : "添加文件"}
          </button>
        </div>
      </header>
      <div className="files-content">
        {indexTask ? (
          <IndexTaskStatus
            onCancel={onCancelIndexTask}
            onRetry={onRetryIndexTask}
            pending={indexActionPending}
            task={indexTask}
          />
        ) : null}
        {actionError ? (
          <p className="file-action-error" role="alert">
            {actionError}
          </p>
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
              <span role="columnheader">名称</span>
              <span role="columnheader">Loader</span>
              <span role="columnheader">Tokens</span>
              <span role="columnheader">大小</span>
              <span role="columnheader">创建时间</span>
              <span role="columnheader">操作</span>
            </div>
            {files.data.map((file) => (
              <div className="file-table-row" role="row" key={file.file_id}>
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
                    disabled={deletingFileId !== undefined}
                    onClick={() => onDelete(file)}
                    type="button"
                  >
                    {deletingFileId === file.file_id ? "删除中…" : "删除"}
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
        {task.error ? <p>{task.error.message}</p> : null}
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

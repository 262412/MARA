import type { FileRecord } from "../../shared/file-contracts";
import type { ResourceState } from "../resource-state";
import { Icon } from "./Icon";

type FilesPageProps = {
  files: ResourceState<FileRecord[]>;
  onRetry: () => void;
};

export function FilesPage({ files, onRetry }: FilesPageProps) {
  return (
    <main className="workspace files-page" id="main-workspace">
      <header className="workspace-toolbar">
        <div>
          <p className="eyebrow">本地数据空间</p>
          <h1>Files</h1>
        </div>
        {files.status === "success" ? (
          <span className="source-count">{files.data.length} 个文件</span>
        ) : null}
      </header>
      <div className="files-content">
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
            detail="文件导入和索引将在下一个纵向切片接入。"
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
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </main>
  );
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

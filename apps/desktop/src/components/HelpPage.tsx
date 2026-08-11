type HelpPageProps = {
  onOpenResources: () => void;
  onOpenSettings: () => void;
  version?: string;
};

export function HelpPage({
  onOpenResources,
  onOpenSettings,
  version,
}: HelpPageProps) {
  return (
    <main className="standalone-page help-page" id="main-workspace">
      <header className="standalone-header">
        <div>
          <p className="eyebrow">Help</p>
          <h1 data-page-title tabIndex={-1}>帮助与快捷键</h1>
          <p>MARA Desktop {version ? `v${version}` : ""} 离线使用指南</p>
        </div>
      </header>
      <section>
        <h2>基础流程</h2>
        <ol>
          <li>在 Settings 配置 Chat LLM 与 Embedding。</li>
          <li>从 Files 导入并等待索引完成。</li>
          <li>新建任务，在 Sources 选择文件，然后输入问题。</li>
          <li>在答案中核对引用，在 Run 查看安全诊断状态。</li>
        </ol>
      </section>
      <section>
        <h2>模型配置</h2>
        <p>支持 OpenAI-compatible、Azure OpenAI 和本地 Ollama。凭据不会返回 Renderer。</p>
        <button onClick={onOpenSettings} type="button">打开 Settings</button>
      </section>
      <section>
        <h2>快捷键</h2>
        <dl className="shortcut-list">
          <div><dt>Ctrl/⌘+N</dt><dd>新建草稿任务</dd></div>
          <div><dt>Ctrl/⌘+,</dt><dd>打开 Settings</dd></div>
          <div><dt>Ctrl/⌘+L</dt><dd>聚焦输入框</dd></div>
          <div><dt>Enter</dt><dd>发送问题</dd></div>
          <div><dt>Alt+Enter</dt><dd>在问题中插入换行</dd></div>
          <div><dt>Ctrl/⌘+Enter</dt><dd>兼容发送快捷键</dd></div>
        </dl>
      </section>
      <section>
        <h2>诊断</h2>
        <p>Resources 显示 Sidecar、Index、LLM、Embedding 和 Doctor 的脱敏状态。</p>
        <button onClick={onOpenResources} type="button">打开 Resources</button>
      </section>
    </main>
  );
}

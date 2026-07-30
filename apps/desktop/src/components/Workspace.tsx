import { useState, type FormEvent } from "react";

import { Icon } from "./Icon";

type WorkspaceProps = {
  onOpenCitation: () => void;
  onToggleInspector: () => void;
};

export function Workspace({
  onOpenCitation,
  onToggleInspector,
}: WorkspaceProps) {
  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!draft.trim()) {
      return;
    }
    setNotice("原型已记录输入；正式版本将在这里启动 MARA 任务。");
    setDraft("");
  };

  return (
    <main className="workspace" id="main-workspace">
      <header className="workspace-toolbar">
        <div>
          <p className="eyebrow">研究任务</p>
          <h1>Agent 研究方向研报</h1>
        </div>
        <div className="toolbar-actions">
          <span className="source-count">8 个来源</span>
          <button
            aria-label="显示或隐藏检查器"
            className="icon-button"
            onClick={onToggleInspector}
            type="button"
          >
            <Icon name="panel" />
          </button>
        </div>
      </header>

      <section className="conversation" aria-label="任务对话">
        <div className="message user-message">
          <div className="message-label">你</div>
          <p>
            基于上传的论文，整理 Agent 研究的四个主要方向，并说明它们之间的关系。
          </p>
        </div>

        <article className="message assistant-message">
          <div className="assistant-heading">
            <span className="assistant-mark" aria-hidden="true">M</span>
            <div>
              <div className="message-label">MARA</div>
              <small>基于 8 个来源</small>
            </div>
          </div>
          <p>
            这批资料可以归纳为四条相互连接的主线：长轨数据合成、交互轨迹可验证性、
            群体智能体，以及自递归智能体。它们不是彼此孤立的分类，而是从数据、
            可信执行到协同与自我改进逐层推进的研究链条。
          </p>
          <div className="direction-grid">
            <section>
              <span>01</span>
              <h2>长轨数据合成</h2>
              <p>构造覆盖长时程决策、工具调用和环境反馈的训练与评测轨迹。</p>
            </section>
            <section>
              <span>02</span>
              <h2>交互轨迹可验证性</h2>
              <p>让过程约束、执行结果和证据链能够被复核，而不仅评价最终答案。</p>
            </section>
            <section>
              <span>03</span>
              <h2>群体智能体</h2>
              <p>研究分工、通信、共识和冲突处理如何影响群体任务表现。</p>
            </section>
            <section>
              <span>04</span>
              <h2>自递归智能体</h2>
              <p>把反思、工具生成和策略修订纳入可控的闭环改进过程。</p>
            </section>
          </div>
          <p>
            四个方向的共同约束是“可追溯”：合成数据需要来源和生成过程，
            验证层需要稳定身份，群体协作需要责任归属，自我改进则需要可回滚记录。
            <button className="citation" onClick={onOpenCitation} type="button">
              [1]
            </button>
            <button className="citation" onClick={onOpenCitation} type="button">
              [2]
            </button>
          </p>
          <div className="message-actions">
            <button type="button">复制</button>
            <button type="button">保存为笔记</button>
            <button type="button">生成 Studio 产物</button>
          </div>
        </article>
      </section>

      <form className="composer-wrap" onSubmit={submit}>
        {notice ? <div className="prototype-notice" role="status">{notice}</div> : null}
        <div className="context-row">
          <button className="context-chip" type="button">
            <Icon name="files" size={14} />
            8 个来源
          </button>
          <button className="context-chip" type="button">智能执行</button>
        </div>
        <div className="composer">
          <label className="sr-only" htmlFor="task-input">描述研究任务</label>
          <textarea
            id="task-input"
            onChange={(event) => setDraft(event.target.value)}
            placeholder="描述研究问题，或添加文件、页面与选中文本……"
            rows={2}
            value={draft}
          />
          <div className="composer-footer">
            <button className="add-source" type="button">
              <Icon name="add" size={16} />
              添加
            </button>
            <div>
              <button className="model-button" type="button">
                deepseek-v4-pro
                <Icon name="chevron" size={13} />
              </button>
              <button
                aria-label="发送"
                className="send-button"
                disabled={!draft.trim()}
                type="submit"
              >
                <Icon name="send" size={17} />
              </button>
            </div>
          </div>
        </div>
      </form>
    </main>
  );
}

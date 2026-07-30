import { Icon, type IconName } from "./Icon";

type SidebarProps = {
  active: string;
  onNavigate: (value: string) => void;
  selectedTask: number;
  onSelectTask: (taskId: number) => void;
};

const navigation: Array<{ id: string; label: string; icon: IconName }> = [
  { id: "workbench", label: "工作台", icon: "workbench" },
  { id: "files", label: "Files", icon: "files" },
  { id: "resources", label: "Resources", icon: "resources" },
  { id: "help", label: "Help", icon: "help" },
];

const tasks = [
  { id: 1, title: "Agent 研究方向研报", detail: "8 个来源" },
  { id: 2, title: "蛋白质最适 pH 值预测", detail: "3 个来源" },
  { id: 3, title: "多模态 RAG 评估整理", detail: "12 个来源" },
  { id: 4, title: "QASPER 引用误差分析", detail: "5 个来源" },
];

export function Sidebar({
  active,
  onNavigate,
  selectedTask,
  onSelectTask,
}: SidebarProps) {
  return (
    <aside className="sidebar" aria-label="应用导航">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">M</span>
        <div>
          <strong>MARA</strong>
          <span>Local research</span>
        </div>
      </div>

      <button className="new-task" type="button">
        <Icon name="add" />
        新建任务
        <kbd>Ctrl N</kbd>
      </button>

      <nav className="primary-nav" aria-label="主要页面">
        {navigation.map((item) => (
          <button
            aria-current={active === item.id ? "page" : undefined}
            className={active === item.id ? "nav-item active" : "nav-item"}
            key={item.id}
            onClick={() => onNavigate(item.id)}
            type="button"
          >
            <Icon name={item.icon} />
            {item.label}
          </button>
        ))}
      </nav>

      <div className="recent-heading">
        <span>最近任务</span>
        <button aria-label="搜索任务" className="icon-button" type="button">
          <Icon name="search" size={16} />
        </button>
      </div>
      <div className="task-list" role="list">
        {tasks.map((task) => (
          <button
            aria-current={selectedTask === task.id ? "true" : undefined}
            className={selectedTask === task.id ? "task active" : "task"}
            key={task.id}
            onClick={() => onSelectTask(task.id)}
            role="listitem"
            type="button"
          >
            <span>{task.title}</span>
            <small>{task.detail}</small>
          </button>
        ))}
      </div>

      <div className="sidebar-footer">
        <button className="nav-item" type="button">
          <Icon name="settings" />
          Settings
        </button>
        <div className="data-space">
          <span className="status-dot healthy" />
          <div>
            <strong>本地数据空间</strong>
            <span>默认工作区</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

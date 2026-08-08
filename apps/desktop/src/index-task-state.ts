import type { IndexTask } from "../shared/index-task-contracts";

export function refreshFilesForTerminalTask(
  task: IndexTask,
  lastRefresh: string | undefined,
  refresh: () => void,
): string | undefined {
  if (!["partial", "success", "failed", "cancelled"].includes(task.status)) {
    return lastRefresh;
  }
  const refreshKey = `${task.task_id}:${task.version}:${task.status}`;
  if (refreshKey !== lastRefresh) {
    refresh();
  }
  return refreshKey;
}

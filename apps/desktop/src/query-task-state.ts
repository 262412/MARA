import type { QueryTask } from "../shared/query-contracts";

export function mergeQueryTaskSnapshot(
  current: QueryTask | undefined,
  incoming: QueryTask,
  replace = false,
): QueryTask {
  if (!current || replace) {
    return incoming;
  }
  if (incoming.task_id === current.task_id) {
    return incoming.version > current.version ? incoming : current;
  }
  if (incoming.retry_of_task_id === current.task_id) {
    return incoming;
  }
  if (current.retry_of_task_id === incoming.task_id) {
    return current;
  }
  return current;
}

export function submittedPromptTransition(
  prompt: string,
  task: Pick<QueryTask, "prompt" | "task_id"> | undefined,
  consumedTaskId: string | undefined,
): { prompt: string; consumedTaskId: string | undefined } {
  if (!task || task.task_id === consumedTaskId) {
    return { prompt, consumedTaskId };
  }
  return {
    prompt: prompt.trim() === task.prompt ? "" : prompt,
    consumedTaskId: task.task_id,
  };
}

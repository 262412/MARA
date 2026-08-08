import type { OpenDialogOptions, OpenDialogReturnValue } from "electron";

export type ShowOpenDialog = (
  options: OpenDialogOptions,
) => Promise<OpenDialogReturnValue>;

export async function chooseFilesForIndex(
  showOpenDialog: ShowOpenDialog,
): Promise<string[]> {
  const result = await showOpenDialog({
    title: "添加到 MARA",
    buttonLabel: "开始索引",
    properties: ["openFile", "multiSelections"],
  });
  return result.canceled ? [] : [...result.filePaths];
}

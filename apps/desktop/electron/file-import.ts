import type { OpenDialogOptions, OpenDialogReturnValue } from "electron";

export type ShowOpenDialog = (
  options: OpenDialogOptions,
) => Promise<OpenDialogReturnValue>;

export async function chooseFilesForIndex(
  showOpenDialog: ShowOpenDialog,
  supportedExtensions: string[],
): Promise<string[]> {
  const extensions = normalizeDialogExtensions(supportedExtensions);
  const result = await showOpenDialog({
    title: "添加到 MARA",
    buttonLabel: "开始索引",
    properties: ["openFile", "multiSelections"],
    filters: [{ name: "MARA 支持的文档", extensions }],
  });
  return result.canceled ? [] : [...result.filePaths];
}

function normalizeDialogExtensions(supportedExtensions: string[]): string[] {
  const extensions: string[] = [];
  for (const value of supportedExtensions) {
    const normalized = value.toLowerCase();
    if (!/^\.[a-z0-9]{1,16}$/.test(normalized)) {
      throw new Error(
        `MARA import capabilities contain an invalid extension: ${value}`,
      );
    }
    const extension = normalized.slice(1);
    if (!extensions.includes(extension)) {
      extensions.push(extension);
    }
  }
  if (extensions.length === 0) {
    throw new Error(
      "MARA import capabilities contain no supported file extensions",
    );
  }
  return extensions;
}

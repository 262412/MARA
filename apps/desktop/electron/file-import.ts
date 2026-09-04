import path from "node:path";

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

export function validateDroppedPathsForIndex(
  filePaths: string[],
  supportedExtensions: string[],
): string[] {
  const extensions = new Set(normalizeDialogExtensions(supportedExtensions));
  if (filePaths.length === 0 || filePaths.length > 64) {
    throw new Error("MARA requires between 1 and 64 dropped files");
  }
  if (new Set(filePaths).size !== filePaths.length) {
    throw new Error("MARA dropped file paths must be unique");
  }
  for (const filePath of filePaths) {
    if (
      !path.isAbsolute(filePath) ||
      filePath.includes("\0") ||
      filePath.length > 32_768
    ) {
      throw new Error("MARA received an invalid dropped file path");
    }
    const extension = path.extname(filePath).toLowerCase().slice(1);
    if (!extensions.has(extension)) {
      throw new Error("MARA received an unsupported dropped file type");
    }
  }
  return [...filePaths];
}

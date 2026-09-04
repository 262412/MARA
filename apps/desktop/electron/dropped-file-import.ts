const MAX_DROPPED_FILES = 64;

export function resolveDroppedFilePaths(
  files: unknown,
  getPathForFile: (file: File) => string,
): string[] {
  if (
    !Array.isArray(files) ||
    files.length === 0 ||
    files.length > MAX_DROPPED_FILES
  ) {
    throw new Error("MARA requires between 1 and 64 dropped files");
  }

  const paths: string[] = [];
  for (const value of files) {
    const filePath = getPathForFile(value as File);
    if (
      !filePath ||
      filePath.includes("\0") ||
      filePath.length > 32_768
    ) {
      throw new Error("MARA only accepts disk-backed dropped files");
    }
    if (!paths.includes(filePath)) {
      paths.push(filePath);
    }
  }
  return paths;
}

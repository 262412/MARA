import { mkdir, open } from "node:fs/promises";
import path from "node:path";

const DESKTOP_EMBEDDING_TEMPLATE = `# MARA Desktop model configuration moved
# Configure chat and embedding routes in MARA Desktop Settings.
# Credentials are protected by Electron safeStorage and must not be written here.
`;

export function embeddingConfigurationPath(dataRoot: string): string {
  return path.join(path.resolve(dataRoot), "state", "config", ".env");
}

export async function prepareEmbeddingConfiguration(
  dataRoot: string,
): Promise<string> {
  const configPath = embeddingConfigurationPath(dataRoot);
  await mkdir(path.dirname(configPath), { recursive: true });
  let handle: Awaited<ReturnType<typeof open>>;
  try {
    handle = await open(configPath, "wx", 0o600);
  } catch (error) {
    if (isAlreadyExists(error)) {
      return configPath;
    }
    throw error;
  }
  try {
    await handle.writeFile(DESKTOP_EMBEDDING_TEMPLATE, "utf8");
  } finally {
    await handle.close();
  }
  return configPath;
}

function isAlreadyExists(error: unknown): boolean {
  return (
    error instanceof Error &&
    "code" in error &&
    (error as NodeJS.ErrnoException).code === "EEXIST"
  );
}

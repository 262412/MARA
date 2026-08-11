import { mkdir, open } from "node:fs/promises";
import path from "node:path";

const DESKTOP_EMBEDDING_TEMPLATE = `# MARA Desktop embedding configuration
# Add one supported provider, save this file, then restart MARA Desktop.
# Credentials remain in this Desktop-owned file and are never sent to Renderer.

OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=
OPENAI_EMBEDDINGS_MODEL=text-embedding-3-small

# Azure OpenAI embedding service (optional)
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=

# OpenAI-compatible local embedding service (optional)
KH_OLLAMA_URL=http://localhost:11434/v1/
LOCAL_MODEL=
LOCAL_MODEL_EMBEDDINGS=
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

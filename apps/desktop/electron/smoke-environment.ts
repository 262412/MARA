type SourceEnvironment = Record<string, string | undefined>;
type Environment = Record<string, string>;

const QUERY_PERSISTENCE_SMOKE_MODE = "query_persistence";

export function mergeSidecarEnvironment(
  inherited: SourceEnvironment,
  trusted: Environment,
): Environment {
  const sanitized = Object.fromEntries(
    Object.entries(inherited).filter(
      (entry): entry is [string, string] =>
        entry[1] !== undefined && !isDesktopSmokeVariable(entry[0]),
    ),
  ) as Environment;
  return { ...sanitized, ...trusted };
}

export function createQueryPersistenceSmokeEnvironment({
  enabled,
  markerPath,
  token,
}: {
  enabled: boolean;
  markerPath: string;
  token: string;
}): Environment {
  if (!enabled) {
    return {};
  }
  return {
    MARA_DESKTOP_QUERY_SMOKE_FAULT_MARKER: markerPath,
    MARA_DESKTOP_QUERY_SMOKE_FAULT_TOKEN: token,
    MARA_DESKTOP_QUERY_SMOKE_MODE: QUERY_PERSISTENCE_SMOKE_MODE,
  };
}

export function createStartupDelaySmokeEnvironment({
  enabled,
  value,
}: {
  enabled: boolean;
  value: string | undefined;
}): Environment {
  if (!enabled || value === undefined) {
    return {};
  }
  if (!/^\d{1,5}$/.test(value) || Number(value) > 10_000) {
    throw new Error("Desktop smoke startup delay is invalid");
  }
  return { MARA_DESKTOP_SMOKE_STARTUP_DELAY_MS: value };
}

function isDesktopSmokeVariable(key: string): boolean {
  const normalized = key.toUpperCase();
  return normalized.startsWith("MARA_DESKTOP_") && normalized.includes("SMOKE");
}

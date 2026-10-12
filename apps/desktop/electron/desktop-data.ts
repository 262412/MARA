import path from "node:path";

type Environment = Record<string, string | undefined>;

export function resolveDesktopDataRoot(
  platform: NodeJS.Platform,
  environment: Environment,
  homeDirectory: string,
  applicationDataDirectory: string,
): string {
  const appHome = environment.MARA_APP_HOME?.trim();
  if (appHome) {
    const paths = platform === "win32" ? path.win32 : path.posix;
    return paths.resolve(appHome, "desktop");
  }
  if (platform === "win32") {
    return path.win32.join(applicationDataDirectory, "MARA");
  }

  const dataHome =
    environment.XDG_DATA_HOME || path.posix.join(homeDirectory, ".local", "share");
  return path.posix.join(dataHome, "MARA");
}

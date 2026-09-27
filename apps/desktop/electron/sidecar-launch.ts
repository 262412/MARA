import path from "node:path";

import { mergeSidecarEnvironment } from "./smoke-environment";

type Environment = Record<string, string | undefined>;

export function resolveDevelopmentPython(
  appPath: string,
  environment: Environment,
  platform: NodeJS.Platform,
  exists: (filename: string) => boolean,
): string {
  if (environment.MARA_DESKTOP_PYTHON) {
    return environment.MARA_DESKTOP_PYTHON;
  }
  const workspacePython = path.resolve(
    appPath, "..", "..", ".venv",
    platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
  if (exists(workspacePython)) {
    return workspacePython;
  }
  return platform === "win32" ? "python" : "python3";
}

export function resolveSidecarCommand(
  configuration: { isPackaged: boolean; resourcesPath: string; platform: NodeJS.Platform },
  developmentPython: () => string,
): { executable: string; args: string[] } {
  if (configuration.isPackaged) {
    const executableName = configuration.platform === "win32"
      ? "mara-desktop-sidecar.exe" : "mara-desktop-sidecar";
    return {
      executable: path.join(configuration.resourcesPath, "sidecar", "mara-desktop-sidecar", executableName),
      args: [],
    };
  }
  return { executable: developmentPython(), args: ["-m", "sidecar.server"] };
}

export function sidecarWorkingDirectory(dataRoot: string): string {
  return path.join(dataRoot, "tmp");
}

export function sidecarEnvironment(
  configuration: { appPath: string; dataRoot: string; isPackaged: boolean; smokeFault?: string },
  inherited: Environment,
  trusted: Record<string, string>,
  token: string,
): Record<string, string> {
  const repositoryRoot = path.resolve(configuration.appPath, "..", "..");
  const developmentPythonPath = [
    configuration.appPath,
    path.join(repositoryRoot, "libs", "ktem"),
    path.join(repositoryRoot, "libs", "kotaemon"),
    path.join(repositoryRoot, "libs", "slide_cli"),
    inherited.PYTHONPATH,
  ]
    .filter((entry): entry is string => Boolean(entry))
    .join(path.delimiter);
  return {
    ...mergeSidecarEnvironment(inherited, trusted),
    KH_APP_DATA_DIR: path.join(configuration.dataRoot, "state", "ktem_app_data"),
    MARA_DESKTOP_DATA_DIR: configuration.dataRoot,
    MARA_DESKTOP_TOKEN: token,
    MARA_DESKTOP_SMOKE_FAULT: configuration.smokeFault ?? "",
    THEFLOW_SETTINGS_MODULE: "ktem.default_flowsettings",
    KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED: "1",
    ...(!configuration.isPackaged ? { PYTHONPATH: developmentPythonPath } : {}),
  };
}

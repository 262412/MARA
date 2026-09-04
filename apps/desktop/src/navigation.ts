export type AppPage =
  | "workbench"
  | "files"
  | "resources"
  | "help"
  | "settings";

export const PAGE_TITLES: Record<AppPage, string> = {
  workbench: "Workbench",
  files: "Files",
  resources: "Resources",
  help: "Help",
  settings: "Settings",
};

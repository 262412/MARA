import assert from "node:assert/strict";
import test from "node:test";

import { resolveDesktopDataRoot } from "./desktop-data";

test("uses an independent Windows application data directory", () => {
  assert.equal(
    resolveDesktopDataRoot("win32", {}, "C:\\Users\\Mara", "C:\\Users\\Mara\\AppData\\Roaming"),
    "C:\\Users\\Mara\\AppData\\Roaming\\MARA",
  );
});

test("uses XDG_DATA_HOME on Linux and never inherits KH_APP_DATA_DIR", () => {
  const environment = {
    XDG_DATA_HOME: "/home/mara/.xdg-data",
    KH_APP_DATA_DIR: "/legacy/ktem_app_data",
  };

  assert.equal(
    resolveDesktopDataRoot("linux", environment, "/home/mara", "/home/mara/.config"),
    "/home/mara/.xdg-data/MARA",
  );
});

test("uses the freedesktop fallback on Linux", () => {
  assert.equal(
    resolveDesktopDataRoot("linux", {}, "/home/mara", "/home/mara/.config"),
    "/home/mara/.local/share/MARA",
  );
});

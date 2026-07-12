import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";

const repoRoot = fileURLToPath(new URL("../../", import.meta.url));

export default defineConfig({
  testDir: ".",
  testMatch: ["security_smoke.spec.mjs", "preview_flow.spec.mjs"],
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: "line",
  use: {
    browserName: "chromium",
    headless: true,
  },
  webServer: [
    {
      command:
        "python -m http.server 8765 --bind 127.0.0.1 --directory .",
      url: "http://127.0.0.1:8765/tests/browser/dom_xss_smoke.html",
      cwd: repoRoot,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "uv run python tests/browser/serve_render_xss_smoke.py --port 8766",
      url: "http://127.0.0.1:8766/",
      cwd: repoRoot,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command:
        "uv run --no-sync python tests/browser/serve_preview_flow.py --port 8767",
      url: "http://127.0.0.1:8767/",
      cwd: repoRoot,
      env: {
        KH_APP_DATA_DIR: "/tmp/mara-preview-browser/app-data",
        GRADIO_TEMP_DIR: "/tmp/mara-preview-browser/gradio",
      },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});

import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "vite";

const desktopRoot = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  build: {
    emptyOutDir: false,
    lib: {
      entry: path.join(desktopRoot, "electron", "preload.ts"),
      fileName: () => "preload.js",
      formats: ["cjs"],
    },
    minify: false,
    outDir: path.join(desktopRoot, "dist-electron", "electron"),
    rolldownOptions: {
      external: ["electron"],
    },
    sourcemap: false,
  },
});

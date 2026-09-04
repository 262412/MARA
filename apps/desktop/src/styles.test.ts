import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

test("Sources checkbox styles close before later top-level selectors", () => {
  const stylesheet = readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8");
  const checkboxBlock = stylesheet.match(/\.source-row input\s*\{([^{}]*)\}/);

  assert.ok(checkboxBlock, "source-row input must be a closed flat CSS rule");
  assert.match(checkboxBlock[1] ?? "", /accent-color:\s*var\(--accent\)/);
  assert.equal(
    (stylesheet.match(/\{/g) ?? []).length,
    (stylesheet.match(/\}/g) ?? []).length,
  );
});

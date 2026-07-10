const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const safeDom = require("./safe_dom.js");

const ASSET_DIR = __dirname;
const MAIN_JS = fs.readFileSync(path.join(ASSET_DIR, "main.js"), "utf8");
const PDF_VIEWER_JS = fs.readFileSync(
  path.join(ASSET_DIR, "pdf_viewer.js"),
  "utf8"
);

test("splitTextForHighlight keeps hostile markup as inert text", () => {
  const payload =
    '<img src=x onerror="globalThis.__xss=1"><script>globalThis.__xss=2</script></mark><svg onload="globalThis.__xss=3">';
  const source = `prefix ${payload} suffix`;

  const parts = safeDom.splitTextForHighlight(source, payload);

  assert.deepEqual(parts, {
    before: "prefix ",
    match: payload,
    after: " suffix",
  });
  assert.equal(parts.match.includes("<script>"), true);
});

test("preview sandbox policies never grant navigation, forms, or popup powers", () => {
  for (const mode of ["document", "pdf", "scripted-document"]) {
    const policy = safeDom.previewPolicy(mode);
    const tokens = new Set(policy.sandbox.split(/\s+/).filter(Boolean));

    assert.equal(policy.referrerPolicy, "no-referrer");
    assert.equal(tokens.has("allow-forms"), false);
    assert.equal(tokens.has("allow-popups"), false);
    assert.equal(tokens.has("allow-popups-to-escape-sandbox"), false);
    assert.equal(tokens.has("allow-top-navigation"), false);
    assert.equal(tokens.has("allow-top-navigation-by-user-activation"), false);
  }
});

test("scripted document previews run with an opaque origin", () => {
  const policy = safeDom.previewPolicy("scripted-document");
  const tokens = new Set(policy.sandbox.split(/\s+/).filter(Boolean));

  assert.equal(tokens.has("allow-scripts"), true);
  assert.equal(tokens.has("allow-same-origin"), false);
});

test("only the exact same-origin PDF.js viewer receives the PDF policy", () => {
  const origin = "https://mara.example.test";
  const trustedViewer =
    "https://mara.example.test/gradio_api/file=/runtime/pdfjs/web/viewer.html";

  assert.equal(
    safeDom.previewModeForSource(
      `${trustedViewer}?embed=1&file=%2Fgradio_api%2Ffile%3Dreport.pdf`,
      origin,
      trustedViewer
    ),
    "pdf"
  );
  assert.equal(
    safeDom.previewModeForSource(
      "data:text/html;ktem-scripted=1,<script>parent.__xss=1</script>",
      origin,
      trustedViewer
    ),
    "scripted-document"
  );
  assert.equal(
    safeDom.previewModeForSource(
      "https://mara.example.test/gradio_api/file=/uploads/viewer.html",
      origin,
      trustedViewer
    ),
    "document"
  );
  assert.equal(
    safeDom.previewModeForSource(
      "https://attacker.invalid/gradio_api/file=/runtime/pdfjs/web/viewer.html",
      origin,
      trustedViewer
    ),
    "document"
  );
});

test("untrusted evidence and PDF text never flow through HTML string sinks", () => {
  assert.doesNotMatch(MAIN_JS, /mark\.outerHTML\s*=/);
  assert.doesNotMatch(MAIN_JS, /p\.innerHTML\s*=/);
  assert.doesNotMatch(PDF_VIEWER_JS, /span\.innerHTML\s*=/);
  assert.match(MAIN_JS, /KtemSafeDom\.highlightText/);
  assert.match(MAIN_JS, /KtemSafeDom\.clearHighlights/);
  assert.match(PDF_VIEWER_JS, /KtemSafeDom\.setTextHighlight/);
});

test("answer-derived popup content is not passed to document.write", () => {
  assert.doesNotMatch(MAIN_JS, /\.document\.write\s*\(/);
});

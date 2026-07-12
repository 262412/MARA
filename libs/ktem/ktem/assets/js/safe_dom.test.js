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
  for (const mode of ["document", "pdf", "invalid"]) {
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

test("only exact safe preview sources are classified as renderable", () => {
  const origin = "https://mara.example.test";
  const trustedViewer =
    "https://mara.example.test/gradio_api/file=/runtime/pdfjs/web/viewer.html";

  assert.equal(
    safeDom.previewModeForSource(
      `${trustedViewer}?embed=1&file=%2Fgradio_api%2Ffile%3D%2Ftmp%2Freport.pdf`,
      origin,
      trustedViewer
    ),
    "pdf"
  );
  assert.equal(
    safeDom.previewModeForSource(
      "data:text/html;charset=utf-8,%3Cp%3Esafe%3C%2Fp%3E",
      origin,
      trustedViewer
    ),
    "document"
  );
  assert.equal(
    safeDom.previewModeForSource(
      "data:image/png;base64,iVBORw0KGgo=",
      origin,
      trustedViewer
    ),
    "image"
  );
  for (const unsafe of [
    "<p>raw html</p>",
    "data:text/html;ktem-scripted=1,<script>parent.__xss=1</script>",
    "data:image/svg+xml;base64,PHN2Zy8+",
    "https://attacker.invalid/image.png",
    `${trustedViewer}?file=https%3A%2F%2Fattacker.invalid%2Freport.pdf`,
    `${trustedViewer}?file=%2Fgradio_api%2Ffile%3D..%252Fsecret.pdf`,
    `${trustedViewer}?file=%2Fgradio_api%2Ffile%3D%2Ftmp%2Fa.pdf&file=%2Fgradio_api%2Ffile%3D%2Ftmp%2Fb.pdf`,
  ]) {
    assert.equal(safeDom.previewModeForSource(unsafe, origin, trustedViewer), "invalid");
  }
  assert.equal(
    safeDom.previewModeForSource(
      "https://mara.example.test/gradio_api/file=/uploads/viewer.html",
      origin,
      trustedViewer
    ),
    "invalid"
  );
  assert.equal(
    safeDom.previewModeForSource(
      "https://attacker.invalid/gradio_api/file=/runtime/pdfjs/web/viewer.html",
      origin,
      trustedViewer
    ),
    "invalid"
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

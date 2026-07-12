import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { expect, test } from "@playwright/test";

const fixtureDir = path.join(os.tmpdir(), "mara-preview-flow-fixtures");

test.beforeAll(() => {
  fs.rmSync(fixtureDir, { recursive: true, force: true });
  execFileSync(
    ".venv/bin/python",
    ["tests/browser/preview_fixture_factory.py", "--output", fixtureDir],
    { cwd: process.cwd() }
  );
});

async function selectFixture(page, name) {
  const upload = page.locator("#preview-upload input[type=file]");
  await upload.setInputFiles(path.join(fixtureDir, name));
  const selector = page.locator("#preview-source-selector input");
  await expect(selector).toBeEnabled();
  await selector.click();
  await page.getByRole("option").click();
}

function installSideEffectAudit(page) {
  const audit = { attackerRequests: 0, dialogs: 0, popups: 0 };
  page.on("request", (request) => {
    if (new URL(request.url()).hostname === "attacker.invalid") {
      audit.attackerRequests += 1;
    }
  });
  page.on("dialog", async (dialog) => {
    audit.dialogs += 1;
    await dialog.dismiss();
  });
  page.on("popup", () => {
    audit.popups += 1;
  });
  return audit;
}

test("Gradio denies sibling runtime and source paths", async ({ request }) => {
  for (const filePath of [
    "/tmp/mara-preview-browser/app-data/private.txt",
    "/tmp/mara-preview-browser/app-data/assets/pdfjs/other-version/secret.txt",
    "/tmp/mara-preview-browser/app-data/files/victim.pdf",
  ]) {
    const response = await request.get(`http://127.0.0.1:8767/file=${filePath}`);
    expect(response.status(), filePath).not.toBe(200);
  }
});

test("hostile PDF upload renders in pinned PDF.js without active content", async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.__maraPdfXss = 0;
  });
  const audit = installSideEffectAudit(page);
  await page.goto("http://127.0.0.1:8767/");
  await selectFixture(page, "malicious.pdf");

  const iframe = page.locator("#main-pdf-preview-frame");
  await expect(iframe).toHaveAttribute("sandbox", "allow-scripts allow-same-origin");
  await expect(iframe).toHaveAttribute("referrerpolicy", "no-referrer");
  await expect(iframe).toHaveAttribute("src", /viewer\.html.*embed=1.*file=/, {
    timeout: 20_000,
  });
  const viewer = iframe.contentFrame();
  await expect(viewer.locator("#viewerContainer")).toBeVisible({ timeout: 20_000 });
  await expect(viewer.locator("body")).toContainText("MARA PDF PAGE", {
    timeout: 20_000,
  });
  const initialFrame = page.frames().find((frame) => frame.url().includes("viewer.html"));
  expect(initialFrame).toBeTruthy();
  await expect
    .poll(() => initialFrame.evaluate(() => window.PDFViewerApplication?.page))
    .toBe(1);
  const pageInput = page.locator("#pdf-page-number input");
  await pageInput.fill("2");
  await pageInput.press("Enter");
  await expect
    .poll(() => initialFrame.evaluate(() => window.PDFViewerApplication?.page))
    .toBe(2);
  await expect
    .poll(() => initialFrame.url())
    .toMatch(/ktempage=2.*#page=2$/);
  await pageInput.fill("3");
  await pageInput.press("Enter");
  await expect
    .poll(() => initialFrame.evaluate(() => window.PDFViewerApplication?.page))
    .toBe(3);
  expect(page.frames().find((frame) => frame.url().includes("viewer.html"))).toBe(
    initialFrame
  );
  expect(await page.evaluate(() => window.__maraPdfXss)).toBe(0);
  expect(audit).toEqual({ attackerRequests: 0, dialogs: 0, popups: 0 });
});

for (const [name, marker, safeText, unsafeLink] of [
  ["malicious.docx", "__maraDocxXss", "MARA DOCX SAFE TEXT", "DOCX JS LINK"],
  ["malicious.pptx", "__maraPptxXss", "PPTX JS LINK", "PPTX JS LINK"],
]) {
  test(`hostile ${name} upload is inert in the document sandbox`, async ({ page }) => {
    await page.addInitScript((property) => {
      window[property] = 0;
    }, marker);
    const audit = installSideEffectAudit(page);
    await page.goto("http://127.0.0.1:8767/");
    await selectFixture(page, name);

    const iframe = page.locator("#main-pdf-preview-frame");
    await expect(iframe).toHaveAttribute("sandbox", "allow-same-origin");
    await expect(iframe).toHaveAttribute("referrerpolicy", "no-referrer");
    const documentFrame = iframe.contentFrame();
    await expect(documentFrame.locator("body")).toContainText(safeText, {
      timeout: 15_000,
    });
    const unsafe = documentFrame.getByText(unsafeLink, { exact: true });
    await expect(unsafe).toBeVisible();
    await expect(unsafe).not.toHaveAttribute("href", /javascript:/i);
    await expect(documentFrame.locator("script, form, img[src*='svg']")).toHaveCount(0);
    expect(await page.evaluate((property) => window[property], marker)).toBe(0);
    expect(audit).toEqual({ attackerRequests: 0, dialogs: 0, popups: 0 });
  });
}

for (const extension of ["docx", "pptx"]) {
  test(`corrupt ${extension} diagnostics remain escaped and inert`, async ({ page }) => {
    await page.addInitScript(() => {
      window.__maraNoticeXss = 0;
    });
    await page.goto("http://127.0.0.1:8767/");
    const name = fs
      .readdirSync(fixtureDir)
      .find((candidate) => candidate.startsWith("corrupt-") && candidate.endsWith(extension));
    expect(name).toBeTruthy();
    await selectFixture(page, name);
    const notice = page.locator("#pdf-preview-notice");
    await expect(notice).toContainText("PREVIEW_SOURCE_ERROR", { timeout: 15_000 });
    await expect(notice).toContainText("corrupt-img srcx onerror");
    await expect(notice.locator("img, script, form")).toHaveCount(0);
    expect(await page.evaluate(() => window.__maraNoticeXss)).toBe(0);
  });
}

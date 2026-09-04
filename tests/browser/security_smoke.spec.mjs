import { expect, test } from "@playwright/test";

async function expectSmokePassed(page, url, markerName) {
  await page.goto(url);
  const body = page.locator("body");
  await expect(body).toHaveAttribute("data-test-status", "passed", {
    timeout: 10_000,
  });
  const marker = await page.evaluate((name) => window[name], markerName);
  expect(marker).toBe(0);
  await expect(body).not.toHaveAttribute("data-test-error", /.+/);
}

test("hostile document text remains inert in real Chromium", async ({ page }) => {
  await expectSmokePassed(
    page,
    "http://127.0.0.1:8765/tests/browser/dom_xss_smoke.html",
    "__maraXssExecuted",
  );
});

test("hostile rendered answers remain inert in real Chromium", async ({ page }) => {
  await expectSmokePassed(
    page,
    "http://127.0.0.1:8766/",
    "__maraRenderXss",
  );
});

import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("example review keeps source uncertainty and actions together across screen sizes", async ({ page }, testInfo) => {
  const mutations: string[] = [];
  page.on("request", (request) => { if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) mutations.push(request.url()); });
  await page.goto("/ui/");
  await page.getByRole("button", { name: "Review an example", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Trailhead Logistics" })).toBeVisible();
  const context = page.getByRole("region", { name: "Customer objectives" });
  await expect(context).toContainText("maintain exemplary adoption");
  await expect(context.getByText("Completion not reported", { exact: true })).toHaveCount(2);
  await expect(page.locator(".hyp-disclaimer")).toBeVisible();
  await expect(page.locator(".decision-reasoning")).not.toHaveAttribute("open");
  expect(await page.locator(".detail-scroll .draft").count()).toBe(1);
  expect(await page.locator(".detail-scroll .decision-controls").count()).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  if (testInfo.project.name.startsWith("mobile")) {
    const detail = await page.locator(".detail-scroll").evaluate((element) => ({ height: element.clientHeight, scroll: element.scrollHeight }));
    expect(detail.scroll).toBeLessThanOrEqual(detail.height + 1);
    await expect(page.getByRole("complementary", { name: "Decision queue" })).toBeHidden();
    await page.getByRole("button", { name: "← Back to queue", exact: true }).click();
    await expect(page.getByRole("complementary", { name: "Decision queue" })).toBeVisible();
    await page.keyboard.press("a");
    await expect(page.locator(".lane-h .c").first()).toHaveText("10");
    await page.getByRole("button", { name: /^Trailhead Logistics/ }).click();
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  }
  await page.getByRole("link", { name: "Inspect sources ↗" }).click();
  await expect(page.locator(".drawer-b").filter({ hasText: "maintain exemplary adoption" })).toContainText("maintain exemplary adoption");
  await page.getByRole("button", { name: /Edit draft/ }).click();
  const editor = page.getByLabel("Edit draft text");
  const originalDraft = await editor.inputValue();
  await editor.fill(`${originalDraft} Ask for completion evidence.`);
  await page.getByRole("button", { name: "Save edit", exact: true }).click();
  await expect(page.locator(".draft-body")).toContainText("Ask for completion evidence.");
  await page.getByText("Decision receipt", { exact: false }).first().click();
  await expect(page.getByRole("log")).toContainText("Edited by operator");
  await page.getByRole("button", { name: /^Deny/ }).click();
  expect(mutations).toEqual([]);
  await expect(page.getByRole("log").getByText("Denied", { exact: true })).toBeVisible();
  expect(await page.getByRole("log").locator(".sim-chip").count()).toBeGreaterThanOrEqual(2);
  await page.reload();
  await page.getByRole("tab", { name: /Queue/ }).click();
  await expect(page.locator(".lane-h .c").first()).toHaveText("10");
});

test("review navigation and text meet WCAG A and AA", async ({ page }) => {
  await page.goto("/ui/");
  await page.getByRole("button", { name: "Review an example", exact: true }).click();
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(result.violations).toEqual([]);
});

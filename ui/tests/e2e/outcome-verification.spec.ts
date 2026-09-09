import { expect, test } from "@playwright/test";

test("Trailhead asks for objective evidence without asserting a failed rollout", async ({ page }, testInfo) => {
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) mutations.push(request.url());
  });
  await page.goto("/ui/");
  await page.getByRole("button", { name: /^Trailhead Logistics/ }).click();
  await expect(page.getByText(/could you confirm the current status of Trailhead Logistics/)).toBeVisible();
  await expect(page.getByText(/share any completion evidence or updates we should record/)).toBeVisible();
  await page.getByText("Decision reasoning", { exact: true }).click();
  await expect(page.getByText(/outcome verification needed/).first()).toBeVisible();
  await expect(page.getByText(/onboarding risk|activation blockers|rollout is unsuccessful/)).toHaveCount(0);
  await expect(page.getByText("Example draft — needs your approval", { exact: true })).toBeVisible();
  expect(mutations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("trailhead-verification.png"), fullPage: true });
});

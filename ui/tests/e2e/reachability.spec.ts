import { expect, test, type Page } from "@playwright/test";

async function openTrailheadDecision(page: Page) {
  const response = await page.goto("/ui/");
  expect(response?.status()).toBe(200);

  await page.getByRole("tab", { name: /Queue/ }).click();
  await page.getByRole("button", { name: /Trailhead Logistics/ }).click();
  await expect(page.getByRole("heading", { name: "Trailhead Logistics" })).toBeVisible();
}

test("Evidence mapping route is present in the exported application", async ({ page }) => {
  const response = await page.goto("/ui/comms-review/");

  expect(response?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Evidence mapping" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to the book" })).toBeVisible();
});

test("populated Evidence mapping owns a viewport-height scroll region", async ({ page }) => {
  const mapping = (index: number, sourceType: "slack_channel" | "notion_meeting") => ({
    source_type: sourceType,
    external_id: `${sourceType}-${index}`,
    title: `${sourceType === "slack_channel" ? "Slack" : "Notion"} mapping ${index}`,
    candidates: [
      {
        account_id: `account-${index}`,
        confidence: 0.91,
        reason: `synthetic candidate ${index}`,
        signal: "account name",
      },
    ],
  });
  await page.route("**/ui/demo-api/comms-slack.json", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        pending: Array.from({ length: 15 }, (_, index) =>
          mapping(index + 1, "slack_channel")
        ),
        auth: "hosted-readonly",
      }),
    });
  });
  await page.route("**/ui/demo-api/comms-notion.json", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        pending: Array.from({ length: 15 }, (_, index) =>
          mapping(index + 16, "notion_meeting")
        ),
        auth: "hosted-readonly",
      }),
    });
  });

  await page.goto("/ui/comms-review/");
  const evidenceRegion = page.locator("main.evidence-review");
  await expect(page.getByText("Notion mapping 30", { exact: true })).toBeAttached();
  const dimensions = await evidenceRegion.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }));
  expect(dimensions.clientHeight).toBeLessThanOrEqual(await page.evaluate(() => innerHeight));
  expect(dimensions.scrollHeight).toBeGreaterThan(dimensions.clientHeight);

  await evidenceRegion.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  await expect(page.getByText("Notion mapping 30", { exact: true })).toBeVisible();
  expect(await evidenceRegion.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
});

test("versioned Action Control contract ships with the static demo", async ({ request }) => {
  const response = await request.get("/ui/demo-api/action-control-vertical-slice-v1.json");

  expect(response.status()).toBe(200);
  const contract = await response.json();
  expect(contract.schema_version).toBe("action-control.vertical-slice.v1");
  expect(contract.simulated_receipt).toMatchObject({
    state: "simulated_committed",
    committed: true,
    external_effect: false,
  });
  expect(contract.tamper_refusal).toMatchObject({
    state: "refused_payload_mismatch",
    code: "PAYLOAD_HASH_MISMATCH",
    committed: false,
  });
});

test("proposal draft and governance controls are reachable without document overflow", async ({ page }) => {
  await openTrailheadDecision(page);

  // The draft is the artifact being approved — it now leads the detail
  // pane (visible without scrolling), with evidence below it.
  await expect(page.getByText("Proposed draft", { exact: true })).toBeVisible();

  const detail = page.locator(".detail-scroll");
  const dimensions = await detail.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }));
  expect(dimensions.scrollHeight).toBeGreaterThan(dimensions.clientHeight);

  await detail.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  await expect(page.getByText("Chosen action — and why", { exact: true })).toBeVisible();

  const releasePanel = page.getByRole("complementary", {
    name: "Decision controls and receipt",
  });
  await expect(releasePanel).toBeVisible();
  await expect(releasePanel.getByRole("button", { name: /Approve exact draft/ })).toBeVisible();
  await expect(releasePanel.getByText("Decision receipt", { exact: true })).toBeVisible();

  const documentOverflows = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth
  );
  expect(documentOverflows).toBe(false);
});

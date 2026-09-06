import { expect, test } from "@playwright/test";

for (const legacy of [false, true]) {
  test("Trailhead interpretation stays unverified with " + (legacy ? "legacy" : "current") + " metadata", async ({ page }, testInfo) => {
    let servedLegacyPacket = false;
    const mutations: string[] = [];
    page.on("request", (request) => {
      if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) mutations.push(request.url());
    });
    await page.route("**/ui/demo-api/sweep-day-140.json", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      const item = body.work_items.find((entry: { account_id: string }) =>
        entry.account_id === "21830db9-7182-5d97-b22e-d57c4e28f696");
      const hypothesis = item.work_packet.diagnostic_hypothesis;
      expect(hypothesis.confidence_method).toBe("packet_structure_heuristic");
      expect(hypothesis.confidence_calibrated).toBe(false);
      if (legacy) {
        delete hypothesis.confidence_method;
        delete hypothesis.confidence_calibrated;
        servedLegacyPacket = !("confidence_method" in hypothesis) && !("confidence_calibrated" in hypothesis);
      }
      await route.fulfill({ response, json: body });
    });
    await page.goto("/ui/");
    await page.getByRole("button", { name: "Dismiss intro" }).click();
    await page.getByRole("button", { name: /^Trailhead Logistics/ }).click();
    await expect(page.getByRole("heading", { name: "Trailhead Logistics" })).toBeVisible();

    const hypothesisRow = page.locator(".packet-hyp");
    await expect(hypothesisRow).toBeVisible();
    await expect(hypothesisRow).not.toContainText(/\d+\s*%/);
    await expect(hypothesisRow).not.toContainText(/\b(low|medium)\b/i);
    const explanation = page.locator("p.hyp-disclaimer").filter({
      hasText: "This interpretation has not been independently validated.",
    });
    await expect(explanation).toContainText("Inspect the source evidence before acting.");
    await expect(page.getByText(/could you confirm the current status of Trailhead Logistics/)).toBeVisible();
    await expect(page.getByRole("button", { name: /Approve exact draft/ })).toBeVisible();
    expect(servedLegacyPacket).toBe(legacy);
    expect(mutations).toEqual([]);
    await explanation.scrollIntoViewIfNeeded();
    await expect(explanation).toBeInViewport();
    await page.screenshot({ path: testInfo.outputPath("confidence-semantics.png") });
  });
}

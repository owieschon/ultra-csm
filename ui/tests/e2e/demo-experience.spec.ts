import { expect, test, type Page } from "@playwright/test";

// The hosted read-only demo must PERFORM the product story (UI_DESIGN_BRIEF:
// coverage -> trust -> action -> payoff -> quiet book), not just display
// state. These tests drive that arc against the static export.

const INTRO_KEY = "ucsm-demo-intro-dismissed";

async function dismissIntro(page: Page) {
  await page.addInitScript(
    ([key]) => window.localStorage.setItem(key, "1"),
    [INTRO_KEY]
  );
}

async function openQueue(page: Page) {
  const response = await page.goto("/ui/");
  expect(response?.status()).toBe(200);
  await page.getByRole("tab", { name: /Queue/ }).click();
}

async function showInbox(page: Page) {
  const back = page.getByRole("button", { name: "← Back to queue", exact: true });
  if (await back.isVisible()) await back.click();
}

test("first visit shows the orientation strip; dismissal persists", async ({ page }) => {
  await page.goto("/ui/");
  const strip = page.getByRole("note").filter({ hasText: "An agent works this" });
  await expect(strip).toBeVisible();
  await expect(strip).toContainText("nothing is sent");

  await page.getByRole("button", { name: "Dismiss intro" }).click();
  await expect(strip).toBeHidden();

  await page.reload();
  await expect(page.getByRole("heading", { name: /Book/ })).toBeVisible();
  await expect(
    page.getByRole("note").filter({ hasText: "An agent works this" })
  ).toHaveCount(0);
});

test("entering the queue lands on the top pending decision", async ({ page }) => {
  await dismissIntro(page);
  await openQueue(page);

  // Auto-selection: the detail pane and rail load without a manual click.
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();
  await expect(page.locator(".rail-top .gate").first()).toContainText(
    "needs your approval"
  );
});

test("approving simulates the full receipt and advances the queue", async ({ page }) => {
  await dismissIntro(page);
  await openQueue(page);
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();

  const pendingCount = page.locator(".lane-h .c").first();
  await expect(pendingCount).toHaveText("10");

  // No verdict, sweep, or commit call ever leaves the browser for a
  // simulated decision — the hosted build is read-only and the decision
  // is client-side state only.
  const mutatingRequests: string[] = [];
  page.on("request", (req) => {
    const method = req.method();
    if (method !== "GET" && method !== "HEAD") mutatingRequests.push(`${method} ${req.url()}`);
  });

  await page.keyboard.press("a");

  // Count decrements at once; the resolved item HOLDS while its receipt
  // streams into the rail, then selection auto-advances.
  await expect(pendingCount).toHaveText("9");
  await expect(page.getByText("Approved (simulated)")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Pinehill Transport" })).toBeVisible({
    timeout: 5000,
  });

  // The resolved row strikes through; inspecting it shows the simulated
  // receipt, honesty-labeled — no claim of a verified payload hash, a real
  // ActionGate call, a committer receipt, or a sent message.
  await showInbox(page);
  await page.locator(".row.resolved", { hasText: "Ironhorse" }).click();
  await expect(page.getByText("Approved (simulated)")).toBeVisible();
  const ledger = page.getByRole("log");
  await expect(ledger.getByText("Send simulated")).toBeVisible();
  await expect(ledger.getByText("no message sent — demo only")).toBeVisible();
  await expect(ledger.getByText("Commit simulated")).toBeVisible();
  await expect(ledger.getByText("no committer ran — nothing released")).toBeVisible();
  await expect(ledger.getByText(/message-id/)).toHaveCount(0);
  expect(await ledger.locator(".sim-chip").count()).toBeGreaterThanOrEqual(4);
  // Original backend receipts survive alongside the simulated ones.
  await expect(ledger.getByText("Proposed", { exact: true })).toBeVisible();

  // Step 04 reflects the recorded decision.
  await page.getByText("Decision reasoning", { exact: true }).click();
  await expect(page.getByText("Decision recorded")).toBeVisible();

  expect(mutatingRequests).toEqual([]);
});

test("reloading clears simulated decisions and restores the full pending queue", async ({ page }) => {
  await dismissIntro(page);
  await openQueue(page);
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();

  const pendingCount = page.locator(".lane-h .c").first();
  await expect(pendingCount).toHaveText("10");
  await page.keyboard.press("a");
  await expect(pendingCount).toHaveText("9");

  await page.reload();
  await openQueue(page);
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();
  await expect(pendingCount).toHaveText("10");
  await showInbox(page);
  await page.locator(".row", { hasText: "Ironhorse" }).click();
  const ledger = page.getByRole("log");
  await expect(ledger.locator(".sim-chip")).toHaveCount(0);
});

test("draft provenance is labeled by draft_mode, not asserted as AI-written", async ({ page }) => {
  await dismissIntro(page);

  async function draftLabelFor(draftMode: string | null): Promise<string> {
    await page.route("**/ui/demo-api/sweep-day-140.json", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.work_items[0].draft_mode = draftMode;
      await route.fulfill({ response, json: body });
    });
    await openQueue(page);
    await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();
    const chip = page.locator(".chip-llm").first();
    const text = (await chip.textContent()) ?? "";
    await page.unroute("**/ui/demo-api/sweep-day-140.json");
    return text;
  }

  expect(await draftLabelFor("fixture")).toContain("Example draft");
  expect(await draftLabelFor("live")).toContain("AI-generated draft (not a current live call)");
  expect(await draftLabelFor("template_fallback")).toContain("Template fallback");
  expect(await draftLabelFor(null)).toContain("Draft provenance unavailable");
  expect(await draftLabelFor("unknown")).toContain("Draft provenance unavailable");
  // Regression: a lookup keyed off prototype-chain membership (`key in obj`)
  // resolves "toString" to Object.prototype.toString and renders it as a
  // legitimate provenance label — the label must come from an own-property
  // check only.
  expect(await draftLabelFor("toString")).toContain("Draft provenance unavailable");
});

for (const scenario of [
  { name: "writer failure", reason: "writer_error", label: "Writer call failed", mode: "template_fallback", noDraft: false },
  { name: "rejected output", reason: "contract_rejected", label: "Writer output rejected", mode: "template_fallback", noDraft: false },
  { name: "validation failure", reason: "validation_error", label: "Output validation failed", mode: "template_fallback", noDraft: false },
  { name: "blocked action without a draft", reason: "customer_action_blocked", label: "Customer action blocked", mode: "template_fallback", noDraft: true },
  { name: "legacy snapshot", reason: undefined, label: null, mode: "template_fallback", noDraft: false },
  { name: "unknown reason", reason: "unrecognized-private-error", label: null, mode: "template_fallback", noDraft: false },
  { name: "healthy draft", reason: "writer_error", label: null, mode: "fixture", noDraft: false },
]) {
  test(`fallback reason: ${scenario.name}`, async ({ page }, testInfo) => {
    await dismissIntro(page);
    await page.route("**/ui/demo-api/sweep-day-140.json", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      const item = body.work_items[0];
      item.draft_mode = scenario.mode;
      if (scenario.reason === undefined) delete item.draft_fallback_reason;
      else item.draft_fallback_reason = scenario.reason;
      if (scenario.noDraft) { item.customer_draft = null; item.proposal = null; item.work_packet = null; item.customer_contact_allowed = false; item.disposition = "internal_review"; }
      await route.fulfill({ response, json: body });
    });
    await openQueue(page);
    if (scenario.noDraft) { await showInbox(page); await page.getByRole("button", { name: "Inspect fallback for Ironhorse Freight Co", exact: true }).click(); }
    await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();
    const chip = page.locator(".chip-fallback-reason");
    if (scenario.label) await expect(chip).toHaveText(scenario.label);
    else await expect(chip).toHaveCount(0);
    await expect(page.locator("body")).not.toContainText("unrecognized-private-error");
    if (scenario.noDraft) {
      await expect(page.locator(".sec-h .t").filter({ hasText: /^Draft status$/ })).toBeVisible();
      await expect(page.locator(".draft-body")).toHaveCount(0);
      await page.getByText("Decision reasoning", { exact: true }).click();
      await expect(page.locator(".control-path")).toContainText("No customer draft");
      await expect(page.locator(".control-path")).toContainText("Human review");
      await expect(page.getByRole("button", { name: /^Approve/, exact: false })).toBeDisabled();
      await expect(page.getByRole("button", { name: /^Deny/, exact: false })).toBeDisabled();
      await expect(page.locator(".sec-h").filter({ has: page.locator(".chip-fallback-reason") }).locator(".chip-llm")).not.toContainText("needs your approval");
      await page.screenshot({ path: testInfo.outputPath("blocked-fallback.png"), fullPage: true });
    }
  });
}

test("hosted account sources are named as synthetic, not claimed live", async ({ page }) => {
  await dismissIntro(page);
  await openQueue(page);
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();

  const sourcesChip = page.locator(".sec-h", { hasText: "Account sources" }).locator(".chip-det");
  await expect(sourcesChip).toHaveText("Synthetic account records");
  await expect(page.getByText(/\d+ systems? — \d+ live/)).toHaveCount(0);
});

test("clearing the queue composes the payoff and returns to a quiet book", async ({ page }) => {
  test.slow();
  await dismissIntro(page);
  await openQueue(page);
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();

  const pendingCount = page.locator(".lane-h .c").first();
  for (let expected = 9; expected >= 0; expected--) {
    const previousAccount = await page.locator(".id-name").first().innerText();
    await page.keyboard.press("a");
    await expect(pendingCount).toHaveText(String(expected));
    if (expected > 0) {
      // Wait for a different account's decision to load; the old approval label can survive one render.
      await expect(page.locator(".id-name").first()).not.toHaveText(previousAccount);
      await expect(page.locator(".rail-top .gate").first()).toContainText(
        "needs your approval",
        { timeout: 5000 }
      );
    }
  }

  // Composed payoff, not a generic empty state.
  await expect(page.getByRole("heading", { name: "Queue clear." })).toBeVisible();
  await expect(page.getByText("0 decisions pending · agent operating")).toBeVisible();

  await page.getByRole("button", { name: "Back to a quiet book" }).click();
  await expect(page.getByRole("heading", { name: "Book quiet." })).toBeVisible();
  await expect(page.getByText("✓ nothing needs you").first()).toBeVisible();
  await expect(page.locator(".tile", { hasText: "Ironhorse Freight Co" })).toContainText(
    "approved"
  );
});

test("day scrubber is clamped to the exported window and re-renders real data", async ({ page }) => {
  await dismissIntro(page);
  await page.goto("/ui/");
  await expect(page.getByRole("heading", { name: /Book/ })).toBeVisible();

  await page.getByText("Options", { exact: true }).click();
  const slider = page.locator('input[type="range"]');
  await expect(slider).toHaveAttribute("min", "134");
  await expect(slider).toHaveAttribute("max", "140");

  await slider.evaluate((element) => {
    const input = element as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value"
    )!.set!;
    setter.call(input, "137");
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });

  // A different day renders from its own fixture — no raw error banner.
  await expect(page.getByText(/day 137/).first()).toBeVisible();
  await expect(page.locator(".notice-error")).toHaveCount(0);
  await expect(page.getByText(/need you\.$/)).toBeVisible();
});

test("palette speaks plain English and lands quiet accounts in the book", async ({ page }) => {
  await dismissIntro(page);
  await page.goto("/ui/");
  await expect(page.getByRole("heading", { name: /Book/ })).toBeVisible();

  await page.getByRole("button", { name: "Search accounts and commands" }).click();
  const input = page.getByRole("combobox", { name: "Search accounts and commands" });
  await input.fill("Bison");

  const option = page.getByRole("option", { name: /Bison Transport Group/ });
  await expect(option).toContainText("High touch");
  await expect(option).not.toContainText("high_touch");

  await option.click();
  // Quiet account: no queue item, so the jump lands on its book tile.
  const tile = page.locator(".tile.flash", { hasText: "Bison Transport Group" });
  await expect(tile).toBeVisible();
});

test("queue rows carry no raw system enums as primary labels", async ({ page }) => {
  await dismissIntro(page);
  await openQueue(page);
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();

  await showInbox(page);
  const lanes = page.locator(".lanes");
  await expect(lanes.getByText("Personal email").first()).toBeVisible();
  await expect(lanes.getByText("needs_judgment")).toHaveCount(0);
  await expect(lanes.getByText("high_touch")).toHaveCount(0);
});

test("evidence page explains itself when nothing is pending", async ({ page }) => {
  await page.goto("/ui/comms-review/");
  await expect(page.getByRole("heading", { name: "Evidence mapping" })).toBeVisible();
  await expect(page.getByText("unmapped evidence never reaches a score or a draft")).toBeVisible();
  await expect(page.getByText("Nothing pending").first()).toBeVisible();
  await expect(page.getByText(/A channel the agent can't place/)).toBeVisible();
});

test("objectives drawer preserves unresolved goals and source reports", async ({ page }, testInfo) => {
  await page.route("**/ui/demo-api/account-*-brief-day-*.json", async (route) => {
    const response = await route.fetch();
    const brief = await response.json();
    brief.objective_evidence = [
      { objective: "Reduce detention time", plan_id: "plan-unresolved", plan_status: "active",
        source_reported_complete: false,
        evidence: [{ source: "cs_platform", source_id: "plan-unresolved" }] },
      { objective: "Cut onboarding time", plan_id: "plan-reported", plan_status: "realized",
        source_reported_complete: true,
        evidence: [{ source: "cs_platform", source_id: "plan-reported" }] },
    ];
    await route.fulfill({ response, json: brief });
  });
  await dismissIntro(page);
  await openQueue(page);
  const drawer = page.locator(".drawer").filter({ has: page.getByRole("button", { name: /^Objectives/ }) });
  await expect(drawer).toContainText("2 records");
  await drawer.getByRole("button").click();
  const unresolved = drawer.locator(".stake-row").filter({ hasText: /Reduce detention time/i });
  await expect(unresolved).toContainText("unresolved (plan active)");
  await expect(unresolved).toContainText("cs_platform:plan-unresolved");
  const reported = drawer.locator(".stake-row").filter({ hasText: /Cut onboarding time/i });
  await expect(reported).toContainText("source-reported complete (plan realized)");
  await expect(reported).toContainText("cs_platform:plan-reported");
  await page.screenshot({ path: testInfo.outputPath("objective-evidence.png"), fullPage: true });
});

for (const missing of [true, false]) {
  test(`objectives drawer distinguishes ${missing ? "missing evidence" : "an empty objective list"}`, async ({ page }) => {
    await page.route("**/ui/demo-api/account-*-brief-day-*.json", async (route) => {
      const response = await route.fetch();
      const brief = await response.json();
      if (missing) delete brief.objective_evidence;
      else brief.objective_evidence = [];
      await route.fulfill({ response, json: brief });
    });
    await dismissIntro(page);
    await openQueue(page);
    const drawer = page.locator(".drawer").filter({ has: page.getByRole("button", { name: /^Objectives/ }) });
    await expect(drawer).toContainText(missing ? "objective evidence unavailable in this snapshot" : "0 records");
    await drawer.getByRole("button").click();
    await expect(drawer.locator(".drawer-b")).toHaveText(missing ? "objective evidence unavailable in this snapshot" : "none");
  });
}

// NOTE: the sandbox's backend-absent composition (the "static export" note
// instead of a red alert, with the reset control disabled) only exists in
// the hosted build — build:e2e bakes NEXT_PUBLIC_ACTION_CONTROL_SANDBOX_API
// in, so that branch is unreachable here. It is pinned by source checks in
// the session DoD and verified against the hosted-parity dev build.

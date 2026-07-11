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

  await page.keyboard.press("a");

  // Count decrements at once; the resolved item HOLDS while its receipt
  // streams into the rail, then selection auto-advances.
  await expect(pendingCount).toHaveText("9");
  await expect(page.getByText("approved · sent (simulated)")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Pinehill Transport" })).toBeVisible({
    timeout: 5000,
  });

  // The resolved row strikes through; inspecting it shows the simulated
  // receipt, honesty-labeled.
  await page.locator(".row.resolved", { hasText: "Ironhorse" }).click();
  await expect(page.getByText("approved · sent (simulated)")).toBeVisible();
  const ledger = page.getByRole("log");
  await expect(ledger.getByText("Email sent")).toBeVisible();
  await expect(ledger.getByText(/message-id sim-/)).toBeVisible();
  expect(await ledger.locator(".sim-chip").count()).toBeGreaterThanOrEqual(4);
  // Original backend receipts survive alongside the simulated ones.
  await expect(ledger.getByText("Proposed", { exact: true })).toBeVisible();

  // Step 04 reflects the recorded decision.
  await expect(page.getByText("Decision recorded")).toBeVisible();
});

test("clearing the queue composes the payoff and returns to a quiet book", async ({ page }) => {
  test.slow();
  await dismissIntro(page);
  await openQueue(page);
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();

  const pendingCount = page.locator(".lane-h .c").first();
  for (let expected = 9; expected >= 0; expected--) {
    await page.keyboard.press("a");
    await expect(pendingCount).toHaveText(String(expected));
    if (expected > 0) {
      // Wait out the receipt hold: the next `a` only lands once selection
      // has advanced to a pending item again.
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

test("day scrubber is clamped to the exported window and re-renders real data", async ({ page, viewport }) => {
  test.skip(
    !!viewport && viewport.width < 640,
    "the scrubber is display:none at phone widths"
  );
  await dismissIntro(page);
  await page.goto("/ui/");
  await expect(page.getByRole("heading", { name: /Book/ })).toBeVisible();

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

test("palette speaks plain English and lands quiet accounts in the book", async ({ page, viewport }) => {
  test.skip(
    !!viewport && viewport.width < 640,
    "the search affordance is display:none at phone widths"
  );
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

  const lanes = page.locator(".lanes");
  await expect(lanes.getByText("Needs judgment").first()).toBeVisible();
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

// NOTE: the sandbox's backend-absent composition (the "static export" note
// instead of a red alert, with the reset control disabled) only exists in
// the hosted build — build:e2e bakes NEXT_PUBLIC_ACTION_CONTROL_SANDBOX_API
// in, so that branch is unreachable here. It is pinned by source checks in
// the session DoD and verified against the hosted-parity dev build.

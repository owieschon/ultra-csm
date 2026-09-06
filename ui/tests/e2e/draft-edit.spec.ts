import { expect, test, type Page } from "@playwright/test";

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

test("saved edit replaces the displayed draft and no network write leaves the tab", async ({ page }) => {
  await dismissIntro(page);
  await openQueue(page);
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();

  const mutatingRequests: string[] = [];
  page.on("request", (req) => {
    const method = req.method();
    if (method !== "GET" && method !== "HEAD") mutatingRequests.push(`${method} ${req.url()}`);
  });

  await page.getByRole("button", { name: "Edit draft" }).click();
  const textarea = page.getByRole("textbox", { name: "Edit draft text" });
  await expect(textarea).toBeVisible();
  await expect(textarea).toHaveValue(/Marcus/);

  const newText = "Hi Marcus, quick check — any update on the objectives review?";
  await textarea.fill(newText);
  await page.getByRole("button", { name: "Save edit" }).click();

  await expect(page.locator(".draft-body")).toHaveText(newText);
  await expect(page.getByText("Edited by operator — simulated")).toBeVisible();
  await page.locator(".decision-reasoning summary").click();
  await expect(page.locator(".draft-body")).toHaveCount(1);
  await expect(page.getByText("Operator edited · review required")).toBeVisible();

  expect(mutatingRequests).toEqual([]);
});

test("a saved edit and its approval receipt survive navigating away and back", async ({ page }) => {
  await dismissIntro(page);
  await openQueue(page);
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();

  const newText = "Hi Marcus, could we get a quick objectives status update this week?";
  await page.getByRole("button", { name: "Edit draft" }).click();
  await page.getByRole("textbox", { name: "Edit draft text" }).fill(newText);
  await page.getByRole("button", { name: "Save edit" }).click();
  await expect(page.locator(".draft-body")).toHaveText(newText);

  // Account/view navigation within the page — the edit is still there.
  await page.getByRole("tab", { name: /Book/ }).click();
  await page.getByRole("tab", { name: /Queue/ }).click();
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();
  await expect(page.locator(".draft-body")).toHaveText(newText);

  await page.keyboard.press("a"); // Approve exact draft
  await expect(page.getByText("Approved (simulated)")).toBeVisible();

  // Navigate away (auto-advances to the next pending item) and back to the
  // now-resolved item — the exact approved text is still inspectable,
  // matching what was saved, not the pre-edit original.
  await showInbox(page);
  await page.locator(".row.resolved", { hasText: "Ironhorse" }).click();
  const receipt = page.locator(".approved-message");
  await expect(receipt).toBeVisible();
  await expect(receipt.locator(".approved-draft-body")).toHaveText(newText);
});

test("cancelling an edit leaves the displayed draft unchanged", async ({ page }) => {
  await dismissIntro(page);
  await openQueue(page);
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();
  const before = await page.locator(".draft-body").innerText();

  await page.getByRole("button", { name: "Edit draft" }).click();
  await page.getByRole("textbox", { name: "Edit draft text" }).fill("Something entirely different.");
  await page.getByRole("button", { name: "Cancel" }).click();

  await expect(page.locator(".edit-panel")).toHaveCount(0);
  await expect(page.locator(".draft-body")).toHaveText(before);
  await expect(page.getByText("Edited by operator — simulated")).toHaveCount(0);
});

test("blank or unchanged draft text cannot be saved as a revision", async ({ page }) => {
  await dismissIntro(page);
  await openQueue(page);
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();

  await page.getByRole("button", { name: "Edit draft" }).click();
  const saveButton = page.getByRole("button", { name: "Save edit" });
  await expect(saveButton).toBeDisabled(); // unchanged from the prefilled draft

  await page.getByRole("textbox", { name: "Edit draft text" }).fill("   ");
  await expect(saveButton).toBeDisabled(); // blank after trimming

  await expect(page.getByText("Edited by operator — simulated")).toHaveCount(0);
});

test("approval is blocked while an edit is open, even via the keyboard shortcut", async ({ page }) => {
  await dismissIntro(page);
  await openQueue(page);
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();

  await page.getByRole("button", { name: "Edit draft" }).click();
  await expect(page.getByRole("button", { name: "Approve exact draft" })).toBeDisabled();

  await page.keyboard.press("a");
  await expect(page.getByText("Approved (simulated)")).toHaveCount(0);
});

test("an approved proposal is terminal: its old snapshot cannot be edited again", async ({ page }) => {
  await dismissIntro(page);
  await openQueue(page);
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();

  await page.keyboard.press("a");
  await expect(page.getByText("Approved (simulated)")).toBeVisible();

  await showInbox(page);
  await page.locator(".row.resolved", { hasText: "Ironhorse" }).click();
  await expect(page.getByRole("button", { name: "Edit draft" })).toBeDisabled();
});

test("switching accounts clears an unsaved editor instead of applying it elsewhere", async ({ page }) => {
  await dismissIntro(page);
  await openQueue(page);
  await expect(page.getByRole("heading", { name: "Ironhorse Freight Co" })).toBeVisible();

  await page.getByRole("button", { name: "Edit draft" }).click();
  await page.getByRole("textbox", { name: "Edit draft text" }).fill("Meant only for Ironhorse.");

  await showInbox(page);
  await page.locator(".row", { hasText: "Pinehill" }).click();
  await expect(page.getByRole("heading", { name: "Pinehill Transport" })).toBeVisible();
  await expect(page.locator(".edit-panel")).toHaveCount(0);
  await expect(page.locator(".draft-body")).not.toHaveText("Meant only for Ironhorse.");
});

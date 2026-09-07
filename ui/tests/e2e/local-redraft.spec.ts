import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

const fixture = (name: string) => JSON.parse(readFileSync(`public/demo-api/${name}.json`, "utf8"));
const revisedBody = "Hi Marcus, could you share the objectives review evidence this week?";

async function setup(page: Page, mode: "normal" | "refused" | "retry" | "wrong-recipient" = "normal") {
  const sweep = fixture("sweep-day-140");
  const item = sweep.work_items.find((i: { proposal?: { action_type: string; status: string } }) =>
    i.proposal?.action_type === "draft_customer_outreach" && i.proposal.status === "pending");
  sweep.work_items = [item];
  const originalId = item.proposal.proposal_id;
  const replacementId = "persisted-replacement";
  const payload = {
    account_id: item.account_id, contact_id: "fixture-contact", contact_email: "marcus@example.test",
    body: item.customer_draft, evidence_ids: ["source-a", "source-b"],
  };
  const original = { proposal_id: originalId, intent: "outreach", action: "draft_customer_outreach", payload,
    autonomy_tier: 1, required_permission: "draft", status: "denied" };
  const replacement = { ...original, proposal_id: replacementId, status: "pending", payload: {
    ...payload, body: revisedBody, contact_email: mode === "wrong-recipient" ? "wrong@example.test" : payload.contact_email,
    revise_chain: { parent_proposal_id: originalId },
  } };
  const verdicts: { id: string; verdict: string }[] = [];
  let listReads = 0;
  let sweepReads = 0;
  await page.route("**/*", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ json: body, status });
    if (path === "/health") return json(fixture("health"));
    if (path === "/accounts") return json(fixture("accounts-day-140"));
    if (path === "/sweep") { sweepReads++; return json(sweep); }
    if (path === "/ledger") return json({ events: [], ledger_gap: [] });
    if (path.match(/^\/accounts\/.+\/brief$/)) return json(fixture(`account-${item.account_id}-brief-day-140`));
    if (path === "/proposals") {
      listReads++;
      if (mode === "retry" && listReads === 1) return json({ error: "temporary" }, 503);
      return json({ tenant_id: item.tenant_id, pending_count: 1, proposals: [original, replacement] });
    }
    const match = path.match(/^\/proposals\/([^/]+)\/verdict$/);
    if (match) {
      const body = request.postDataJSON();
      verdicts.push({ id: match[1], verdict: body.verdict });
      if (mode === "refused") return json({ error: "REVISE_REFUSED" }, 409);
      return json({ proposal_id: match[1], status: body.verdict === "revise" ? "denied" : "approved",
        authorized: body.verdict === "approve", verdict: body.verdict,
        payload_sha256: "fixture-hash", superseding_proposal_id: body.verdict === "revise" ? replacementId : null });
    }
    return route.continue();
  });
  await page.goto("/ui/");
  await page.getByRole("tab", { name: /Queue/ }).click();
  await expect(page.locator(".draft-body")).toHaveText(item.customer_draft);
  await page.getByRole("button", { name: "Request redraft" }).click();
  await page.getByRole("textbox", { name: "Edit instruction" }).fill("Make the tone warmer.");
  await page.getByRole("button", { name: "Send redraft request" }).click();
  return { verdicts, originalId, replacementId, sweepReads: () => sweepReads };
}

test("persisted replacement is reviewed and separately approved even when sweep contains only the original", async ({ page }) => {
  const state = await setup(page);
  await expect(page.locator(".draft-body")).toHaveText(revisedBody);
  await expect(page.locator(".decision-controls")).toHaveAttribute("data-proposal-id", state.replacementId);
  expect(state.verdicts).toEqual([{ id: state.originalId, verdict: "revise" }]);
  await page.getByRole("button", { name: "Approve exact draft" }).click();
  await expect(page.locator(".approved-draft-body")).toHaveText(revisedBody);
  expect(state.verdicts).toEqual([{ id: state.originalId, verdict: "revise" }, { id: state.replacementId, verdict: "approve" }]);
  expect(state.sweepReads()).toBe(1);
  await page.getByText("Options", { exact: true }).click();
  await expect(page.locator("#scenario-day")).toBeVisible();
  await page.locator("#scenario-day").focus();
  await page.locator("#scenario-day").press("ArrowLeft");
  await expect(page.locator("#scenario-day")).toHaveValue("139");
  await expect.poll(state.sweepReads).toBe(2);
  await expect(page.locator(".lane-h .c").first()).toHaveText("1");

});

test("retrieval failure keeps original closed and retries only the read", async ({ page }) => {
  const state = await setup(page, "retry");
  await expect(page.locator(".decision-controls").getByRole("alert")).toContainText("original draft is closed");
  await expect(page.getByRole("button", { name: "Approve exact draft" })).toBeDisabled();
  await page.getByRole("button", { name: "Load replacement draft" }).click();
  await expect(page.locator(".draft-body")).toHaveText(revisedBody);
  expect(state.verdicts).toEqual([{ id: state.originalId, verdict: "revise" }]);
});

test("refused redraft preserves original pending draft", async ({ page }) => {
  const state = await setup(page, "refused");
  await expect(page.locator(".decision-controls").getByRole("alert")).toContainText("Redraft request did not complete");
  await expect(page.getByRole("button", { name: "Load replacement draft" })).toHaveCount(0);
  await expect(page.locator(".decision-controls")).toHaveAttribute("data-proposal-id", state.originalId);
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("button", { name: "Approve exact draft" })).toBeEnabled();
});

test("a replacement for a different recipient cannot be displayed or approved", async ({ page }) => {
  await setup(page, "wrong-recipient");
  await expect(page.locator(".decision-controls").getByRole("alert")).toContainText("Could not load a verified replacement");
  await expect(page.locator(".draft-body")).not.toHaveText(revisedBody);
  await expect(page.getByRole("button", { name: "Approve exact draft" })).toBeDisabled();
});

import { expect, test, type Page, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const H = {
  proposed: "1".repeat(64),
  revised: "2".repeat(64),
  attempted: "9".repeat(64),
  state: "a".repeat(64),
  key: "b".repeat(64),
};

function sandboxResponse(body: any) {
  const types = body.commands.map((command: any) => command.type);
  const revised = types.includes("revise_and_approve");
  const denied = types.includes("deny");
  const committed = types.includes("commit_simulated");
  const retried = types.includes("retry_same_commit");
  const tampered = types.includes("probe_tamper");
  const approved = types.includes("approve_exact") || revised;
  const hash = revised ? H.revised : H.proposed;
  const state = denied
    ? "denied_terminal"
    : tampered
      ? "refused_payload_mismatch"
      : committed
        ? "simulated_committed"
        : approved
          ? "approved_payload_bound"
          : "pending_human_decision";
  const allowed = state === "pending_human_decision"
    ? ["approve_exact", "revise_and_approve", "deny"]
    : state === "approved_payload_bound"
      ? ["commit_simulated"]
      : state === "simulated_committed"
        ? retried ? ["probe_tamper"] : ["retry_same_commit", "probe_tamper"]
        : [];
  const commandLabels: Record<string, [string, string]> = {
    approve_exact: ["Exact draft approved", "gate.approve"],
    revise_and_approve: ["Revised draft approved", "gate.revise"],
    deny: ["Draft denied", "gate.deny"],
    commit_simulated: ["Simulated outbox committed", "sim_outbound.commit"],
    retry_same_commit: ["Duplicate commit suppressed", "idempotency.duplicate"],
    probe_tamper: ["Altered payload refused", "committer.payload_mismatch"],
  };
  return {
    schema_version: "action-control.sandbox-session.v1",
    run_id: body.run_id,
    revision: body.commands.length,
    state,
    state_sha256: `${body.commands.length}`.repeat(64),
    allowed_commands: allowed,
    mode: "rollback_isolated_synthetic",
    outbound_effects_enabled: false,
    scenario: {
      scenario_id: "trailhead-logistics.payload-binding",
      account_id: "081b380c-99e7-5073-992a-9e0d8b27d8c0",
      account_name: "Trailhead Logistics",
      contact_name: "Vanessa Torres",
      recipient: "vanessa.torres@trailhead-logistics.example",
      original_draft: "Hi Vanessa, can we review the activation blockers?",
      evidence: [
        { evidence_id: "11111111-1111-4111-8111-111111111111", label: "Activation gap remains unresolved", provenance: "synthetic_fixture" },
        { evidence_id: "22222222-2222-4222-8222-222222222222", label: "Success plan is overdue", provenance: "synthetic_fixture" },
      ],
    },
    proposal: {
      proposal_id: "33333333-3333-4333-8333-333333333333",
      action: "draft_customer_outreach",
      status: denied ? "denied" : approved ? "approved" : "pending",
      draft: revised ? body.commands.find((command: any) => command.type === "revise_and_approve").draft : "Hi Vanessa, can we review the activation blockers?",
      payload_sha256: hash,
    },
    decision: approved || denied ? {
      verdict: denied ? "deny" : revised ? "revise" : "approve",
      human_principal_id: "44444444-4444-4444-8444-444444444444",
      approved_payload_sha256: denied ? null : hash,
    } : null,
    committed_receipt: committed ? {
      state: "simulated_committed",
      receipt_id: "abcdefabcdefabcdefabcdef",
      proposal_id: "33333333-3333-4333-8333-333333333333",
      idempotency_key: H.key,
      target: "simulated_outbox",
      committed: true,
      dry_run: false,
      external_effect: false,
      payload_sha256: hash,
    } : null,
    idempotency_probe: retried ? {
      state: "duplicate_suppressed",
      receipt_id: "abcdefabcdefabcdefabcdef",
      idempotency_key: H.key,
      committed: false,
      outbox_rows: 1,
    } : null,
    tamper_refusal: tampered ? {
      state: "refused_payload_mismatch",
      code: "PAYLOAD_HASH_MISMATCH",
      reason: "payload hash does not match the authorized verdict",
      committed: false,
      approved_payload_sha256: hash,
      attempted_payload_sha256: H.attempted,
      outbox_rows: 1,
    } : null,
    events: [
      { sequence: 0, state: "pending_human_decision", label: "Draft proposed", technical_event: "gate.propose", detail: "Waiting for a human decision.", payload_sha256: H.proposed },
      ...body.commands.map((command: any, index: number) => ({
        sequence: index + 1,
        state: command.type === "probe_tamper" ? "refused_payload_mismatch" : state,
        label: commandLabels[command.type][0],
        technical_event: commandLabels[command.type][1],
        detail: `Verified sandbox event ${index + 1}.`,
        payload_sha256: command.type === "probe_tamper" ? H.attempted : hash,
      })),
    ],
    isolation: { database_transaction: "rolled_back", filesystem: "temporary_directory_removed", external_effect: false },
  };
}

async function mockSandbox(page: Page) {
  let delayNextApproval = false;
  await page.route("**/demo/action-control/sandbox/evaluate", async (route: Route) => {
    const body = route.request().postDataJSON();
    const delayed = delayNextApproval
      && body.commands.length === 1
      && body.commands[0].type === "approve_exact";
    if (delayed) {
      delayNextApproval = false;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    try {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(sandboxResponse(body)),
      });
    } catch (error) {
      if (!delayed) throw error;
    }
  });
  return {
    delayNextApproval() {
      delayNextApproval = true;
    },
  };
}

async function expectNoAccessibilityViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const summary = results.violations
    .map((violation) => `${violation.id}: ${violation.nodes.length}`)
    .join(", ");
  expect(results.violations, summary).toEqual([]);
}

test("no-login sandbox completes approve, commit, retry, tamper, and reset", async ({ page }) => {
  const transport = await mockSandbox(page);
  const response = await page.goto("/ui/action-control/");
  expect(response?.status()).toBe(200);

  await expect(page.getByRole("heading", { name: /Try to move one customer draft/ })).toBeVisible();
  await page.getByRole("button", { name: "Approve exact draft" }).click();
  await expect(page.getByText("authorization sealed", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Commit to temporary outbox" }).click();
  await expect(page.getByText("simulated receipt verified", { exact: true })).toBeVisible();
  await expect(page.getByText("false", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Retry same commit" }).click();
  await expect(page.getByText("duplicate suppressed", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Alter payload and try again" }).click();
  const dialog = page.getByRole("dialog", { name: "Alter the committed payload" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Run tamper attempt" }).click();
  await expect(page.getByText("altered attempt refused", { exact: true })).toBeVisible();
  await expect(page.getByRole("log").getByText("Altered payload refused", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Reset with a new run" }).click();
  await expect(page.getByRole("button", { name: "Approve exact draft" })).toBeVisible();

  transport.delayNextApproval();
  await page.getByRole("button", { name: "Approve exact draft" }).click();
  const reset = page.getByRole("button", { name: "Reset with a new run" });
  await expect(page.getByText("Running real controls…", { exact: true })).toBeVisible();
  await reset.click();
  await expect(page.getByText("awaiting human decision", { exact: true })).toBeVisible();
  await page.waitForTimeout(350);
  await expect(page.getByText("authorization sealed", { exact: true })).toHaveCount(0);

  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
});

test("revise dialog traps focus, authorizes revised bytes, and restores focus", async ({ page }) => {
  await mockSandbox(page);
  await page.goto("/ui/action-control/");
  const trigger = page.getByRole("button", { name: "Revise and approve" });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Revise and approve this payload" });
  const textarea = dialog.getByLabel("Draft body");
  await expect(textarea).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await trigger.click();
  await textarea.fill("Hi Vanessa, can we review the two documented blockers together?");
  await dialog.getByRole("button", { name: "Revise and approve" }).click();
  await expect(page.getByRole("log").getByText("Revised draft approved", { exact: true })).toBeVisible();
  await expect(page.getByText(/two documented blockers/)).toBeVisible();
});

test("review, dialog, and refusal states have no WCAG A or AA violations", async ({ page }) => {
  await mockSandbox(page);
  await page.goto("/ui/action-control/");
  await expect(page.getByText("awaiting human decision", { exact: true })).toBeVisible();
  await expectNoAccessibilityViolations(page);

  await page.getByRole("button", { name: "Revise and approve" }).click();
  const reviseDialog = page.getByRole("dialog", { name: "Revise and approve this payload" });
  await expect(reviseDialog).toBeVisible();
  await expectNoAccessibilityViolations(page);
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Approve exact draft" }).click();
  await page.getByRole("button", { name: "Commit to temporary outbox" }).click();
  await page.getByRole("button", { name: "Retry same commit" }).click();
  await page.getByRole("button", { name: "Alter payload and try again" }).click();
  const tamperDialog = page.getByRole("dialog", { name: "Alter the committed payload" });
  await expect(tamperDialog).toBeVisible();
  await expectNoAccessibilityViolations(page);
  await tamperDialog.getByRole("button", { name: "Run tamper attempt" }).click();
  await expect(page.getByText("altered attempt refused", { exact: true })).toBeVisible();
  await expectNoAccessibilityViolations(page);
});

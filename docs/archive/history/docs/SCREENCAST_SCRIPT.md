# Screencast script — Ultra CSM (target: 6 minutes)

<!-- sourcebound:purpose -->
Every command below runs green in order on a synced checkout. This script's DoD is that
property, not production polish — the agent cannot record video; the owner records the
screen following this script. Beats mirror the README/TOUR order: (1) morning briefing,
(2) deployment-readiness at scale, (3) the differentiator, (4) mechanics for anyone who
wants them.
<!-- sourcebound:end purpose -->

Prerequisites: repo cloned, `make setup` already run once (not part of the recording —
run it beforehand so the terminal starts warm). Terminal font large enough to read on
a 1080p capture. No credentials needed for any command below.

---

## Beat 1 — the morning briefing (~90s)

**Say:** "Here's what a CSM opens with — not a health-score dashboard, a triage queue
with receipts."

```sh
make mcp-operator-demo-csm
```

**Expect on screen:** log lines ending in a JSON summary block —
`"tool_calls": 12`, `"refusal_codes": ["CONSENT_MISSING", "PRECEDENCE_HELD"]`,
`"artifact": "eval/mcp_operator_transcript.json"`.

```sh
cat eval/mcp_operator_transcript.json | python3 -m json.tool | head -60
```

**Expect on screen:** a readable JSON transcript — briefing, work queue entries with
cited evidence, an approval, two refusals. Point out one work item's `evidence` array
and one refusal's `refusal_code` on screen.

**Say:** "That's a scripted transcript. It also runs for real, every morning, against
the live book — `docs/PROGRAM_REPORT_21.md` has one verified real run: story day 51,
Ironhorse Freight Co at Time-to-Value score 143, 12 real work items across 5 motions,
and the quality judge scoring 3 of that day's drafts for $0.231 against a $2 cap, all
passing."

---

## Beat 2 — why you can trust this at scale (~90s)

**Say:** "The claim isn't 'it works on my fixture' — it's tested cold-start across four
distributionally different tenants."

```sh
LC_ALL=en_US.UTF-8 make deployment-readiness
```

**Expect on screen:** `wrote docs/DEPLOYMENT_READINESS.md` then
`docs/DEPLOYMENT_READINESS.md is current`.

```sh
cat docs/DEPLOYMENT_READINESS.md
```

**Expect on screen:** the tenant-coverage table (fleetops 180 / fieldstone 12 /
crateworks 10 / loopway 400 accounts, four different vendor-CRM shapes), the battery
results table (every row `hard_ok: true`), and the "zero ad-hoc per-tenant rules"
paragraph. Point out the onboarding-cost table on screen: 3-6 questions per tenant,
no relationship to account count.

**Say:** "Two of those four tenants — Salesforce and Rocketlane — are proven live, not
just fixture-tested: real read-only CRM fetch, a real create-only write-back,
documented in `docs/PROGRAM_REPORT_6.md`."

---

## Beat 3 — the differentiator: a validated judge (~90s)

**Say:** "The LLM piece is a judge that scores draft quality — and the judge itself was
measured before it was trusted to gate anything."

```sh
grep -n "The gate flips\|aggregated false negatives\|Never re-litigate this gate" docs/DECISION_LOG.md
```

**Expect on screen:** matching lines including "The gate flips: cot@N is now the
validated hard-layer instrument, not terse@N" and the aggregated false-negative counts
for both arms (terse@5: 3 false negatives, disqualified; cot@5: zero).

**Say:** "The gate judge changed once the team ran a proper 5-run aggregation study —
the cheaper single-run-stable choice turned out to still pass bad outputs after
aggregation, so the validated instrument today is Sonnet with chain-of-thought
reasoning, picked because the adversarial gold data says so, not because it looked good
on a smaller sample. Every draft this system produces stays propose-only — a human
approves before anything reaches a customer."

---

## Beat 4 — the mechanics, for whoever wants them (~90s)

**Say:** "Underneath: one deterministic value model, a proposal-only gate, and an
oversight ledger rendered from real events, not asserted."

```sh
LC_ALL=en_US.UTF-8 make oversight-report
```

**Expect on screen:** a JSON summary — `"verdict_events": 34`, `"suppressions": 0`,
`"not_instrumented": 7`.

```sh
head -40 demo_state/oversight_report.md
```

**Expect on screen:** a rendered Markdown oversight report — verdicts, receipts,
breaker events, and an explicit "not instrumented" section.

**Say:** "The report says what it doesn't cover as plainly as what it does. That's the
whole discipline in one document: measurement, control, and capability, in one
provenance chain — never inflate a claim past what a test can prove."

---

## Closing card (~30s)

**Say:** "Ultra CSM: one deterministic customer-value model, three thin agent lenses,
a validated judge, and a proposal-only action gate — tested across four tenants, proven
live on two, with every claim traceable to a committed artifact. `README.md` and
`docs/TOUR.md` have the full ten-minute version; `docs/DEPLOYMENT_READINESS.md` and
`docs/DECISION_LOG.md` are the receipts."

---

## Verified run log (this script's own DoD)

Every command above was executed in order on branch `codex/act3-curation`; outputs
matched the "Expect on screen" descriptions. See `docs/PROGRAM_REPORT_22.md`'s receipts
appendix for the pasted terminal output.

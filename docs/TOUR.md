# A ten-minute tour

Three beats. **Beat 1** is what this finds in a book of business — that's the demo's opening
narrative, not a footnote. **Beat 2** is why you can point it at a real tenant: two live vendors
onboard in one conversation, and the drafts are scored by a validated judge. **Beat 3** is the
receipts — the artifacts a skeptical reviewer would ask for. The machinery (deterministic value
model, proposal-only gate, N-run judge) is the objection-handler underneath all three, never the
headline.

Everything below runs locally with **no credentials, no cloud, and no customer data**, except
where a beat is explicitly marked live.

## Beat 1 — the morning briefing: what it finds in a book of business

```sh
make setup && make doctor   # preflight: proves your environment can boot the test harness
make mcp-operator-demo-csm
```

Open `eval/mcp_operator_transcript.json`. This is the demo's opening beat: a simulated morning
over the real proposal gate, run against a 35-account book. Briefing, work queue, evidence per
item, a plain-English revise, an approval with a payload-hash-bound receipt, a draft-never-send
placement artifact, then two refusals (no-consent outreach, a held expansion) — the gate says no
exactly when it should, not just when it's convenient to demo. This is the account triage a CSM
opens with, not a health-score dashboard: green-but-quiet accounts, stalling onboardings, and
single-threaded relationships all surface with cited evidence and a drafted next move.

For the zero-setup version of this same evidence-grounded question-answering (no Postgres, no
`make setup`), talk to the book directly:

```sh
git clone https://github.com/owieschon/ultra-csm.git && cd ultra-csm
python3 -m venv .venv && .venv/bin/pip install -q -e ".[mcp]"
claude mcp add ultra-csm --env ULTRA_CSM_MCP_READONLY=1 -- \
  "$(pwd)/.venv/bin/python" -m ultra_csm.mcp_server
```

Then ask things like *"Which accounts are most at risk right now, and what evidence says so?"* or
*"Approve the pending proposal for Sagebrush Transport"* — the last one refuses: write tools
return a typed `MCP_READONLY` error enforced in the server process, not left to the model's
judgment. A captured transcript of this session shape lives at
`demo_state/mcp_readonly_transcript.json`.

## Beat 2 — why you can point it at a real tenant

Two live vendors onboard into the same value model, each in one conversation:

```sh
make mcp-relational-demo-csm   # normalized multi-table CRM (the Salesforce shape)
make mcp-relay-demo-csm        # a foreign-shaped book via the generic relay
```

Open `eval/mcp_relational_transcript.json`: three tables relay through `ingest_table` with
source-declared foreign keys, `confirm_book` joins them, and exactly five questions reach the
user — four identity picks and one value direction. Every unmapped foreign field is declared
`not_mappable` rather than silently guessed. This is the same shape a real Salesforce onboarding
takes, proven live: `docs/LIVE_INTEGRATION_FINDINGS.md` and `docs/PROGRAM_REPORT_6.md` document
real read-only Salesforce fetch, a real create-only Salesforce write-back, and real Rocketlane
onboarding-phase evidence lighting up the Time-to-Value rail end-to-end, including a live
cross-system beat that joins a real Salesforce account to real Rocketlane evidence through the
unchanged sweep and action gate.

The drafts that come out the other end are not judged by impression. `eval/gold/live_semantic_quality.json`
is a real run: live Slot B drafts over live corpus B accounts, scored by the same judge validated
against human-labeled gold data (`docs/DECISION_LOG.md`) under N-run (cot@5) modal aggregation.
`eval.judge_validation.live_semantic_quality_status` derives the pass/fail from that artifact —
never a hand-set boolean — and it currently derives **proven**.

## Beat 3 — the receipts

```sh
make oversight-report
```

Open `demo_state/oversight_report.md`. This is the document a reviewer, auditor, or security team
asks for when someone claims "humans oversee this AI": every verdict with its proposal id,
payload-hash-bound outbound receipts, suppression history, breaker trips and operator resets, the
judge-validation evidence quoted verbatim, and autonomy tier provenance. Section 8 lists what is
NOT instrumented — the report would rather admit a gap than imply coverage.

The other receipts a skeptical reviewer would want:

- `docs/PROGRAM_REPORT_6.md` — the live connector and live-judged-quality run, with claim
  boundaries and deviations stated.
- `docs/LIVE_INTEGRATION_FINDINGS.md` — the full live battery matrix (Salesforce D1-D6,
  Rocketlane D1-D5) with exact-number assertions against a ground truth authored before any
  record was created.
- `eval/scorecard_csm.json`, `eval/relational_battery.json`, `eval/relay_battery.json` — the
  deterministic spine: tenant isolation, consent gating, payload-hash binding, and
  no-authority-minting, enforced in code and failing the build if broken.
- `STATUS.md` — rendered from artifacts, never hand-written (`make status` fails if stale).
- `docs/DECISION_LOG.md` — the append-only record of non-obvious decisions and the evidence
  behind them, including the full judge validation methodology.

Every artifact here carries a machine-readable `claim_boundary` stating what it does and does not
prove. Simulation is labeled simulation; live is labeled live; everywhere.

## The rest of the mechanics (run anytime, in any order)

```sh
make scorecard-csm     # 24/24 hard_ok=True -- the deterministic spine, proven not sampled
PYTHONPATH=src:. .venv/bin/python -m eval.year_in_life_digest   # a 35-account book over 365 days
make tick-demo-csm     # schedule/deadline/event triggers fire -- and get suppressed, logged either way
make demo              # the full artifact bundle: scorecard, regression, Slot A, all connectors, transcripts
```

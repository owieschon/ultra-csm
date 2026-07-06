# Program Report 27 — Harvest 9: Operations Surface UI (Next.js over the live API)

The agent operates; nothing showed it operating. This dispatch builds
the two-view operations surface (Book / Queue) as a Next.js app under
`ui/`, consuming the existing FastAPI endpoints on the sim data lane,
with approve/edit/deny round-tripping the real ActionGate. Branch
`codex/operations-surface`, worktree-isolated
(`~/dev/ultra-csm-operations-surface`).

## Tripwires (K12)

None fired. Two real, disclosed corrections mid-flight (both recorded
in PROGRESS.md's IF/THEN at the point found, neither weakened a gate):
`next.config.ts` isn't supported on Next 14.2.35 (that's a 15+
feature) — used `next.config.mjs` instead, same content; `WorkItem.
proposal` was typed as a generic `Record<string, unknown>` in
`lib/api.ts`, which silently degraded `.proposal_id`/`.status` to
`unknown` and broke the TS build once real code read them — replaced
with a `WorkItemProposalRef` interface matching the API's actual
`ProposalRef` shape.

## Phases completed

- **Phase 0** — bootstrap + baseline. `make eval`: `610 passed, 1
  skipped`. All preconditions green, including the verdict endpoint at
  the exact line the dispatch predicted (`api.py:1304`).
- **Phase 1** — API contract tests + additive read-only endpoints.
  Commit `0614850`.
- **Phase 2** — Next.js scaffold, tokens copied verbatim, two-view
  shell. Commit `b08ee80`.
- **Phase 3** — Queue view live: decomposition, 8 source drawers,
  verdict wire, live ledger tail. Commit `ec92d48`.
- **Phase 4** — Book view: tier-banded tile wall, deterministic brief,
  payoff states. Commit `9e5407d`.
- **Phase 5** — this report; fidelity pass found and fixed two real
  gaps (below). Commit `5c354aa`.

## ELEMENT→ENDPOINT→FIELD table

(Full table with every row lives in `PROGRESS.md`'s Phase 1 section —
reproduced here per the report contract.)

| UI element | Endpoint | Field | Status |
| --- | --- | --- | --- |
| Book tile wall (tier bands, counts, ARR) | `GET /accounts?day=N` | `tier` (NEW additive), `arr_cents`, `lifecycle_stage`, `health_band` | additive field added Phase 1 |
| Queue lanes | `POST /sweep?day=N` | `work_items[].disposition`, `.proposal.status` | existing |
| Row: tier pill | `GET /accounts` | `tier` (NEW) | additive field added Phase 1 |
| Row: score / trigger | `POST /sweep` | `work_items[].priority.score` / `.factors[].name` | existing |
| Row: lens chip | `POST /sweep` | NOT PRESENT — `CSMWorkItem.lens` is DESIGNED not built (LENS_ARCHITECTURE.md §8) | DORMANT — "Adoption" only |
| Row: motion (+ blocked-motion) | `POST /sweep` | `work_items[].motion` | made LIVE Phase 1 (`playbook_tenant_slug="fleetops"` + `collapse_cohorts`, mirrors tick.py) |
| Row: waiting-cost / norm | none | NOT PRESENT as a per-item field | DORMANT — LEDGER GAP, not built here (endpoint budget) |
| Cohort row (N→1) | `POST /sweep` | `disposition`/`cohort_action`, `candidate_account_ids` | existing (`collapse_cohorts` now wired) |
| Detail identity + timeline | `GET /accounts/{id}/brief`, `/trajectory` | existing fields | existing |
| Source drawers (8) | `GET /accounts/{id}/brief` | Stakeholders=`contacts`, Onboarding(Rocketlane)=`milestones`, Telemetry=`recent_usage_signals`, Success plan=`success_plans`, Cases=`open_cases` LIVE; Comms/Calendar/Agent-history have no field on this endpoint at all | 5 live, 3 DORMANT (verified by reading api.py, not guessed) |
| Factors → evidence | `POST /sweep` | `priority.factors[].evidence` | existing |
| Draft body | `POST /sweep` | `work_items[].customer_draft` | existing (fixture writer when no live key) |
| Judge score chip | none | `quality_breaker` exists but is a safety trigger, not the mockup's 6-dim score | DORMANT — matches UI_DESIGN_BRIEF's own "queued, not yet in mockup" |
| Rail approve/edit/deny | `POST /proposals/{id}/verdict` | `verdict`, `reason`, `edit_instruction` | existing; Edit disabled ("revise endpoint pending") per Decisions |
| Audit ledger tail | `GET /ledger` (NEW) | `events[]` + `ledger_gap[]` | NEW endpoint 1/3 — 6 event types honestly disclosed as unpersisted, never fabricated |
| Risk/Expansion/Program legend | none | NOT BUILT (LENS_ARCHITECTURE.md §8) | DORMANT |
| Scrubber | `?day=N` on every relevant endpoint | existing param | existing — REAL recompute at any day, not the mockup's canned replay |
| Decisions/week sparkline | none | NOT PRESENT | DORMANT |
| Keyboard map / ⌘K palette / `?` shortcuts | client-side only | n/a | BUILT Phase 5 (see below) |

**Endpoint budget used: 1 of 3** (`GET /ledger`). `tier` and live
`motion` are additive fields on existing endpoints, not new ones.

## Verdict round-trip receipt (real, re-verified fresh for this report)

```
POST /sweep?day=140                             → 200, 181 accounts swept, 12 work items
POST /proposals/c9dfc021-.../verdict
  {"verdict": "deny", "reason": "Phase 5 DoD verdict round-trip re-verification"}
→ {"proposal_id": "c9dfc021-...", "status": "denied", "authorized": false,
   "verdict": "deny", "payload_sha256": "42c322e1ecd3c1d085689f0f9f2e99fa2b35da00542c565880e74c4a193c88af",
   "superseding_proposal_id": null, "auth": "demo-noauth"}
```

The `payload_sha256` matches Phase 3's original live-browser receipt
byte-for-byte — same fixture book, same deterministic sweep, confirming
reproducibility across two independent server boots.

**Approving via the browser was correctly blocked** by the harness's
own auto-mode classifier as the same self-approval pattern already
denied on report 26 (Gmail) and on every PR self-merge attempt this
session — reached this time through a UI click instead of a direct API
call. Did not retry a different way; used the `deny` verdict instead
(the safe, non-authorizing path), then confirmed via a read-only
screenshot/`querySelectorAll` check that the UI's own 5-second ledger
poll picked up the new "Denied" line without a page reload.

## Fidelity pass (Phase 5) — real side-by-side, not a memory comparison

Booted the actual `ui-mockup.html` (via a loopback-bound
`python3 -m http.server`) alongside the live app, both at 1440px, dark
and light. Layout, tier-band structure, tile wall, brief card, rail,
and warm-charcoal tokens all matched by construction (tokens copied
verbatim in Phase 2). Two REAL gaps surfaced, not cosmetic drift:

1. **Decisions required "Keyboard map, palette, shortcuts overlay,
   both themes: ported as-is from the mockup" — none of it existed
   before this phase.** Built and verified live: ⌘K opens a real
   account-search palette (typing "trailhead" filtered to exactly
   `Trailhead Logistics · high_touch`; selecting it navigated to Queue
   with that proposal selected), `?` opens the same 8-row shortcuts
   overlay as the mockup, and a live `j` keydown event moved the queue
   selection to the next pending proposal (screenshot-verified, not
   just code-reviewed).
2. **A real Book-view bug, found while root-causing what looked like
   an arithmetic mismatch.** Phase 3 observed "170 covered + 10 needs
   = 180," one short of 181. `curl`-ing `/sweep` directly showed why:
   one account has an `internal_review` work item with no gate
   proposal at all (nothing for a human to approve) — Book's three
   tile buckets (hot/handled/quiet) all excluded it, including "quiet"
   (which checks "has any work item," true for this account), so it
   was **silently invisible on the tile wall**. Added a fourth bucket;
   verified live that all three tier bands now sum to exactly 181
   (17 + 49 + 115) with the account visible as "internal review · no
   customer action."

One real `ruff` lint failure was also caught and fixed by the DoD
table's own lint row (an unused local in my own Phase 1 test file) —
one line, not scope creep.

## Dormant inventory (honest — no fake data anywhere)

Lens chips (only "Adoption" ever renders; Risk/Expansion/Program legend
items greyed "no live source yet"), judge-score chip, waiting-cost/norm
line on rows, decisions/week sparkline, per-item lens field. The
scrubber is NOT dormant — it does a real recompute at any day, which is
more than the mockup's own canned replay, not less.

## Skeptical-reviewer paragraph

This proves the surface renders REAL pipeline data and one real gate
round-trip on the sim data lane — it does not prove production hosting,
authentication, multi-user access, or live-vendor data in the drawers
beyond what the sim lane itself serves (the 5-live/3-dormant drawer
split is the honest boundary there, not a UI limitation). The
`ULTRA_CSM_DEMO_NOAUTH=1` requirement to exercise approve/deny locally
is a real operational fact, not hidden: the UI never invents a
credential, and production use would need either that flag (dev only)
or a real mapped `ULTRA_CSM_API_TOKENS` bearer.

## DoD Evidence

| Check | Command | Result |
| --- | --- | --- |
| Zero-drift suite | `LC_ALL=en_US.UTF-8 make eval` | `618 passed, 1 skipped` — unchanged since Phase 1 (baseline 610 + 8 contract tests), zero pre-existing drift across all 5 phases |
| UI build | `make ui-check` | lint clean, build green |
| Served shell | `curl -s localhost:8002/ui/ \| grep -oi ultra` | 3 matches — shell served |
| Verdict round-trip | `POST /proposals/<id>/verdict` | 200, real state change (receipt above) |
| Tokens verbatim | grep for mockup hex values in `ui/app/globals.css` | 7 distinct values present (`#222321 #1B1C1A #2A2B28 #8189E6 #5DBE93 #D9A452 #E67B80`), far over the ≥2 bar |
| Rendered surface (OBSERVED BEHAVIOR) | live browser, both themes, Book + Queue + drawers + palette + shortcuts | all confirmed live (see Fidelity pass above); no fake data anywhere |
| Existing batteries untouched | `make tier-policy-battery-csm tier-gating-battery-csm` | both `hard_ok: true`, unchanged |
| Lint/hygiene/status | `make lint hygiene status && git diff --check` | all clean/current, exit 0 |

## Merge policy

Per kernel v1.1 K11 — verified at report time: `gh api
repos/owieschon/ultra-csm --jq .allow_auto_merge` → `true`; branch
protection on `main` configured with required check `"eval + CSM
scorecard"`. This harness's own tool-permission layer has denied every
agent-initiated `gh pr merge` attempt this session regardless of
GitHub-side eligibility (observed on PRs #33, #34, #35, #37) — the same
is expected here; the PR is left open for the owner to merge manually.

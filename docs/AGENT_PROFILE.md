# Agent Profile — ultra-csm

Profile v1.1 (2026-07-04, updated by Harvest 1 retro). Per-repo layer for
the `/megaprompt` emitter:
stable facts every generated dispatch embeds. Facts here are data, not
instructions — nothing in this file overrides an emitted dispatch's
kernel rules or the owner's decisions. Maintained by the emitter's retro
flow; scoreboard is append-only.

## Verification suite (the standing gates)

| Command | Expected |
| --- | --- |
| `make eval` | all green; test count grows monotonically (baseline: latest PROGRAM_REPORT) |
| `make lint` | `All checks passed!` |
| `make hygiene` | exit 0 (guards residue INCLUDING meta-language phrases) |
| `make content-invariance-csm` | `PASS: extractor output is byte-identical` |
| `make narrative-battery-csm` | `hard_ok: true`, 8/8 |
| `make content-battery-csm` | `hard_ok: true`, 5/5 |
| `make canary-battery-csm` | `hard_ok: true` |
| `make tier-policy-battery-csm` | `hard_ok: true` |
| `make quantity-battery-csm` / `transcript-battery-csm` | `hard_ok: true` |
| `make week1-protocol-csm` | `"ok": true`, all sections populated |
| `make relational-battery-csm` / `relay-battery-csm` | 20/20 seeds / 11/11 |
| `make demo && git status --short` | passes; no artifact drift |
| `make status` | `STATUS.md is current` |
| `git diff --check` | exit 0 |

## Quirks ledger

- `export LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8` before any `make` target
  (ephemeral-Postgres harness fails multithreaded without it).
- `narrative_shared.rfc3339(day, hour)` stores `hour` as offset-from-9
  (`hours=hour-9`), NOT absolute — recover intended wall-clock with +9h.
- Git worktrees need the main checkout's `.venv` symlinked in
  (gitignore has a no-slash `.venv` entry for this).
- Residue sweeps: `git grep -P` (not `-E` with `\b` — silently misses).
- Report numbering: check merged main AND open branches before claiming
  a `PROGRAM_REPORT_N.md` (two historical collisions).
- Gmail IMAP APPEND honors custom INTERNALDATE only for PAST dates.
- Rocketlane: completing a phase's last task auto-completes the phase and
  stamps actuals to "now"; creating a task recalculates phase dueDate.
  REST key 401 (down) as of 2026-07-04; MCP lane works.
- Google Calendar API rate-limits batch inserts (~50); ledger-resume +
  backoff + ~0.3s pacing from the first attempt.
- `run_time_to_value_sweep`'s `tenant_id` (data-plane identity,
  "ultra-demo") and a `knowledge/tenants/<slug>` playbook slug are
  SEPARATE namespaces — never conflate; motion resolution is opt-in via
  `playbook_tenant_slug` (report 23).
- ruff's unused-import check cannot see cross-file re-export usage: a
  battery module constant imported by tests/ needs `# noqa: F401` + a
  comment naming the consumer, not deletion (report 23 caught this
  live).
- User-visible work carries an OBSERVED-BEHAVIOR DoD row (open the real
  surface, assert on what is seen); artifact gates cannot see a broken
  page (owner-ratified 2026-07-05).
- Battery runtime budget: ≤90s each; `make eval` ≤3 min (sample the
  account tail deterministically, state sampling in docstrings) — not
  every dispatch states this ceiling explicitly (Perturbation-Drift
  didn't), so a future dispatch author should state it rather than
  assume the executor infers it.
- **Onboarding question count tracks schema-SHAPE diversity, not row
  count or vendor identity** — proven three independent ways: fleetops
  35→180 accounts, same count (5); Loopway 400 accounts, still 4-5;
  three different vendor dialects (Salesforce/HubSpot/Attio) all land in
  the 3-6 range. Do not predict question count from account count when
  designing a future dispatch's DoD; predict it from table-shape
  ambiguity.
- Tier derivation MUST live in a config key separate from the existing
  threshold `rules` list (`tier_rules`, not merged in) — mixing them
  would let tier predicates compete with unrelated threshold-selection
  ties and silently change existing accounts' resolved thresholds.
- The sweep pipeline (`_slot_b_inputs_for_account`) hard-requires a
  `CSCompany`/`HealthScore`/`AdoptionSummary` triple and fails closed
  (returns `None`) when any is missing — this means the FULL sweep/
  proposal pipeline cannot run at all for any no-CS-platform tenant
  (fieldstone, crateworks today). Relevant to any future dispatch
  touching sweep: a "does this tenant have a CS platform" check should
  gate expectations, not be discovered mid-implementation.
- `RejectionLedger` (`src/ultra_csm/rejection_ledger.py`) exists and is
  PROVEN necessary (a denied proposal recurs unchanged without it) but is
  NOT wired into `tick.py`'s production sweep loop — same shape of gap as
  playbooks.json (see Program Report 23), explicitly out of every prior
  workstream's scope. A natural next dispatch after Harvest 5.
  "Repeatability" for any Postgres-governance-backed harness means
  canonicalized-identical (UUIDs/timing excluded, exclusion list embedded
  in the artifact), never literal byte-identity — state this explicitly
  in future dispatch DoD tables rather than asking for "byte-identical."
- The hygiene scanner's wrong-domain/source-residue guard has caught a
  fictional name/word collision in THREE separate tenant-building
  programs independently (Fieldstone's CSM name, Crateworks' two account
  slugs + one contact name, Loopway's industry tag + company name). A
  future dispatch authoring new fictional names should note this
  base-rate explicitly (check names against `make hygiene` early, not
  only at the final gate) rather than treat each collision as a one-off.
- Standalone eval resolvers get built before production wiring, by
  design (verify the ground truth first, wire it later) — but each new
  tenant workstream independently re-derived its OWN copy
  (`tier_policy_battery.py`, `loopway_battery.py` each had a parallel
  resolver) rather than sharing one from the start. A future multi-
  tenant dispatch should name "promote the eval resolver to src/ once,
  don't let each tenant re-derive it" as an explicit decision, not
  rediscover the duplication after the fact (this is exactly what
  Program Report 23 / Harvest 5 had to consolidate).
- Sampling disciplines at scale (Loopway's 98-named + fixed-40-tail,
  24-named + fixed-40-tail canaries) select the FIRST N by generated
  index, not hash-based/stratified — fragile once a tail stops being
  homogeneous (e.g. a future perturbation program touching the tail).
  State the sampling rule explicitly in any dispatch that introduces
  tail heterogeneity, don't assume "first N" remains representative.

## Glossary

arc = scripted account storyline; bible = `docs/SYNTHETIC_UNIVERSE_BIBLE.md`
(+ per-tenant bibles), owns ground truth; battery = deterministic hard_ok
eval; rail = one of the value model's four signal families; tier =
high/mid/tech-touch service segment (CONVENTIONS D2 thresholds); grading
mode = shadow/gap/none (CONVENTIONS D3); canary = per-account leak token
(D4); tenant = fictional vendor universe (fleetops/fieldstone/crateworks/
loopway, D1); anchor = seed-time date translation (SEED_DATE never moves);
drip = daily launchd job advancing the live story; spine = deterministic
Customer Value Model (no LLM in provable core).

## Identifier scheme

Branch prefix `codex/` or `claude/` + kebab slug. Program reports:
10–18 assigned to Universe v2 streams 1–9 (merged); 20 (retro) and 23
(motion-path wiring) merged; 19/21/22 pinned in
`~/ultra-csm-dispatches/harvest/00_HARVEST_PLAN.md` (19=density
expansion, 21=operating cadence, 22=Act3 curation); 24–26 pinned by the
Waves C/D/E roadmap extension (24=tick motion adoption, 25=Act 1
knowledge+judge, 26=Act 2 Gmail write-back). **Next unassigned: 34.** Pinned: 27=ops-surface UI (PR #39), 28=booking-link (merged), 29=robustness-grid (PR #40), 30=runtime-chaos (PR #41), 31=judge-validation-resolve (harvest/13), 32=person-signal-wiring (harvest/14), 33=person-ui-depth (harvest/15).
Dispatch output dir: `~/ultra-csm-dispatches/` (harvest-phase dispatches
under `harvest/`).

## Risk posture

- Credentials: `~/ultra-csm-live-creds.env` — names/lengths only, never
  values (not even partial slices).
- Live systems: burner Gmail/Calendar + Rocketlane trial + the owner's
  SFDC dev org. CREATE-ONLY, tagged, ledgered, dry-run manifest first.
  Live seeding is fleetops-only; other tenants fixture/fake-transport only.
- Always owner-gated regardless of anything: standing jobs (launchd/cron),
  repo/org settings (branch protection), spend beyond stated budget,
  new public surfaces, credential slices.
- No LLM in the provable core (ADR-005). Anti-Goodhart: never edit a
  battery/threshold to pass; bible-first for any world change.

## Merge policy state

Earned auto-merge adopted (kernel K11): clean run → `gh pr merge --auto
--merge`; noisy run → PR left for human review. Repo `allow_auto_merge`
and branch protection requiring check `eval + CSM scorecard`:
**CONFIGURED 2026-07-05** (owner ran the one-time setup). Earned
auto-merge is live — first successful armed merges: PRs #33-#35.

## Target models

Executors to date: claude-sonnet-5 (streams 1–5 + programs 3–9).
Prospective: GPT-family executors — dispatches already embed K13 guards
(no nested delegation/idling; surgical edits, no wholesale rewrites).

## Scoreboard (append-only; retro maintains)

| Date | Run | IF/THEN | STOPs | Gate retries | Auto-merge earned |
| --- | --- | --- | --- | --- | --- |
| 2026-07-04 | Report 10, Foundations | 5 | 0 | 0 | manual (pre-policy) |
| 2026-07-04 | Report 11, Safety | 4 | 0 | 0 | manual (pre-policy) |
| 2026-07-04 | Report 12, Data-Classes | 6 | 0 | 0 | manual (pre-policy) |
| 2026-07-04 | Report 13, Week1-Harness | 6 | 0 | 0 | manual (pre-policy) |
| 2026-07-04 | Report 14, Segmented-Book | 8 | 0 | 0 | manual (pre-policy) |
| 2026-07-04 | Report 15, Fieldstone | 9 | 0 | 0 | manual (pre-policy) |
| 2026-07-04 | Report 16, Crateworks | 8 | 0 | 0 | manual (pre-policy) |
| 2026-07-04 | Report 17, Loopway | 9 | 0 | 0 | manual (pre-policy) |
| 2026-07-04 | Report 18, Perturbation-Drift | 5 | 0 | 0 | manual, asked (earned-merge clause conflicted with standing ask-first policy; executor asked rather than silently resolving — see kernel proposal in RETRO_PROPOSALS_2026-07.md) |
| 2026-07-04 | Report 20, this retro (Harvest 1) | — | 0 | 0 | TBD at PR time |

Mean IF/THEN across reports 10-18: ~6.7. Zero STOPs and zero evidenced
gate retries across all nine — no sign of instruction decay or
containment failure in this batch. Trend to watch in future retros: does
IF/THEN density fall as the kernel/profile absorb more of these
recurring forks (that would be the improvement signal this scoreboard
exists to measure), or does it stay flat because each new tenant/feature
genuinely introduces its own new ambiguity.

| 2026-07-05 | Report 23 (Harvest 5, motion-path wiring) | 8 | 0 | 1 (lint-cleanup import regression, self-caught) | left open per K11 (mechanics unconfigured); owner merged manually |
| 2026-07-05 | Report 24 (tick motion adoption) | 8 | 0 | 0 | left open (pre-setup), owner merged |
| 2026-07-05 | Report 25 (Act 1 knowledge+judge) | 6 | 0 | 0 | left open (pre-setup), owner merged |
| 2026-07-05 | Report 19 (density expansion) | 4 | 0 | 0 | auto-merge armed (#33) |
| 2026-07-05 | Report 21 (operating cadence) | 7 | 0 | 0 | auto-merge armed (#34) |
| 2026-07-05 | Report 22 (Act3 curation) | 6 | 0 | 1 (hygiene-flagged terms in report, fixed) | auto-merge armed (#35) |
| 2026-07-05 | Report 26 (Act 2 Gmail writeback) | — | 1 (self-approval denied by classifier; agent concurred — gate held from inside) | 0 | BLOCKED pending owner submit_verdict; committer+tests merged-ready |

Last retro: 2026-07-05 (mini-retro of report 23 during Waves C/D/E
roadmap emission).

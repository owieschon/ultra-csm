# Agent Profile — ultra-csm

Profile v1.2 (2026-07-12, updated by the F2R foundation-audit auto-retro,
`/megaprompt` stage-3 dispatch emission). Per-repo layer for
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
- TWO emitter sessions share ~/ultra-csm-dispatches/harvest/ — claim a
  dispatch filename/report slot ONLY from 00_HARVEST_PLAN.md's FILE +
  REPORT-SLOT REGISTRY, re-read immediately before writing, and append
  the claim in the same emission (a 28/34 collision and a duplicate
  11/12 emission both happened on 2026-07-05).
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
- `make hygiene` (`scripts/hygiene_scan.py`) blocks a `META_RESIDUE_PATTERNS`
  list including the literal phrase "load-bearing" (natural engineering
  vocabulary, not obviously meta) — caught 3+ times across reports 73-76.
  Run `make hygiene` immediately after writing/editing ANY prose file, as
  its own step, not only bundled into a final DoD pass.
- Report-number claiming has TWO independent stale-number failure modes
  observed live (reports 73, 74/75/76 sessions): the dispatch's own stated
  "next unassigned" can be stale by the time it's consumed, AND the naive
  "highest-on-main + 1" guess can already be claimed on an unmerged branch.
  Scan `git log --all --oneline --diff-filter=A -- docs/PROGRAM_REPORT_N.md`
  forward from N=(profile's stated next) until a genuinely free number is
  found; never trust either the profile or the naive increment alone.
- Seeded-hash generation (`ultra_csm/world/generator.py` pattern:
  `_fraction(seed, index, label)` = md5-digest-derived uniform) is powerful
  but fragile to INDEX PROVENANCE: if two code paths derive "the same"
  entity's index by different means (e.g. array position after a sort vs.
  the index used at generation time), they silently draw different latent
  values for what looks like the same entity — a real, critical bug found
  in production (report 75 finding F1, fixed PR #141). Any future dispatch
  touching seeded/deterministic generation must state explicitly which
  single index-derivation path is the source of truth and thread it
  through every consumer, never re-derive it locally.
- Long-running live eval harnesses (`eval/writer_bakeoff.py` pattern)
  checkpoint per-draw for kill/resume safety, but a checkpoint with no
  PROVENANCE header (model/judge-version/transport/pass_k/content-hash)
  can silently resume-and-report STALE results after the underlying code
  or data changes (report 76 finding D, fixed PR #142 — a checkpoint
  provenance header + refuse-on-mismatch + refuse-on-legacy-header-less is
  now the pattern). Any new live-eval harness with checkpointing should
  copy this pattern from the start, not discover the gap after a world/
  prompt/model change makes a stale resume possible.
- Detached-process pattern for live OPERATE runs, used repeatedly and
  reliably this session: `nohup env ... .venv/bin/python3 script.py
  < /dev/null > /tmp/x.log 2>&1 & disown; echo $! > /tmp/x.pid`, verified
  via `ps -p $(cat /tmp/x.pid)` (never trust the launch echo alone), watched
  via the Monitor tool with `tail -n 0 -f` (NEVER `-c +1`/`-n +1`, which
  replay history as false "new" events) grepping for a completion/error
  alternation that fires on every terminal state, not just success.
- One-off OPERATE driver scripts (not reusable library code) belong in a
  git-excluded `.scratch/` inside the worktree (add to `.git/info/exclude`
  if the worktree's own exclude isn't reachable, or just never `git add`
  them) — NOT in `scripts/` (a tracked, maintained directory) and not
  outside the worktree (the session's lane-lock guard blocks writes outside
  the locked path, so an external scratchpad requires clear/re-lock
  ceremony that a `.scratch/` inside the lock avoids entirely).

## Glossary

arc = scripted account storyline; bible = `docs/SYNTHETIC_UNIVERSE_BIBLE.md`
(+ per-tenant bibles), owns ground truth; battery = deterministic hard_ok
eval; rail = one of the value model's four signal families; tier =
high/mid/tech-touch service segment (CONVENTIONS D2 thresholds); grading
mode = shadow/gap/none (CONVENTIONS D3); canary = per-account leak token
(D4); tenant = fictional vendor universe (fleetops/fieldstone/crateworks/
loopway, D1); anchor = seed-time date translation (SEED_DATE never moves);
drip = daily launchd job advancing the live story; spine (Customer Value
Model sense) = deterministic no-LLM core (ADR-005).

F2R program terms (MP-Q quarter runway, reports 65-76): world = the
seeded synthetic living-world package (`src/ultra_csm/world/`, distinct
from the Customer Value Model "spine" above) with a strict observable/
latent split (`LatentAccountTruth` = oracle-only ground truth, never
agent-readable — `run_knowability_audit` enforces this structurally +
semantically as of PR #141); spine_policy / no_spine_ablation = two
world-baseline surfacing predicates (`world/baselines.py`) — currently
formula-identical (report 74/75 finding, NOT a bug to silently patch, an
owner-decided world-realism gap); OA-Q1/OA-Q2 = owner-gated ratification
points (writer-model adoption; freeze countersign before holdout-seed
generation); pass^k = k independent draws per scenario, "consistent" iff
all k pass the judge gate; adopted writer = claude-sonnet-5, OA-Q1
(`docs/OA_Q1_WRITER_ADOPTION.md`); the three-arm design (control /
gates_only / governed, report 76 Owner Ask A ratified 2026-07-11) =
successor to the original two-arm (governed vs control) design named in
early F2R docs — any reference to "the control arm" in a pre-2026-07-11
document means the OLD two-arm framing, superseded.

Report/finding-numbering-in-prose convention this program uses: F<n> =
world ground-truth integrity finding (report 75); P2.<n> = design
amendment (report 75); R-<letter> = referee-objection resolution (report
75); I-<n> = operational integrity rule (report 75); S<n> = strategic
finding (report 76); cluster A-G = report 76's finding groupings with
FOLD/DECIDE/DEFER dispositions.

## Identifier scheme

Branch prefix `codex/` or `claude/` (Harvest-era) or `operator/` (F2R-era
live operate/build PRs, 2026-07-11 on) + kebab slug. Program reports:
10–18 assigned to Universe v2 streams 1–9 (merged); 20 (retro) and 23
(motion-path wiring) merged; 19/21/22 pinned in
`~/ultra-csm-dispatches/harvest/00_HARVEST_PLAN.md` (19=density
expansion, 21=operating cadence, 22=Act3 curation); 24–26 pinned by the
Waves C/D/E roadmap extension (24=tick motion adoption, 25=Act 1
knowledge+judge, 26=Act 2 Gmail write-back). 27=ops-surface UI (PR #39),
28=booking-link (merged), 29=robustness-grid (PR #40), 30=runtime-chaos
(PR #41), 31=judge-validation-resolve (harvest/13),
32=person-signal-wiring (harvest/14), 33=person-ui-depth (harvest/15),
34=Notion authoring edge (PR #43), 35=adversarial-surfaces (re-slotted
from 31), 36=Harvest 19 (PR #55). **Note: this profile stated "next
unassigned: 36" as of v1.1 — that was ALREADY STALE by the time it was
next consumed (report 73's own emission hit the collision live); always
verify per the quirks-ledger scan rule above, never trust this number.**
F2R-era reports (MP-Q quarter runway + foundation audit, 2026-07-11):
65-71 = earlier program reports (writer bake-off precursors, judge
validation); 73 = MP-W1R world response+diversification (PR #135);
74 = Q4 no-spine ablation blocked finding (worktree-local, not yet a
standalone PR — folded into later work); 75 = F2R foundation audit,
world ground-truth integrity, hypothesis + P1-P3 path + P2/R/I amendments
(PR #140, merged); 76 = 12-lens adversarial sweep of report 75's design,
strategic findings S1-S3, ratified three-arm/difficulty/validity-chain
design (also PR #140). **Next unassigned: 77.**
Dispatch output dir: `~/ultra-csm-dispatches/` (harvest-phase dispatches
under `harvest/`; F2R-era dispatches at top level, e.g.
`MP_Q_QUARTER_RUNWAY.md`, `MP_W7R_QUARTER_HARNESS_CONTROL_ARM.md`,
`PLAN_MP_F2R_MEASURED_QUARTER.md`, `MP_W1R_WORLD_RESPONSE_AND_DIVERSIFICATION.md`).

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
- F2R live-LLM OPERATE runs: subscription transport only
  (`ULTRA_CSM_LLM_TRANSPORT=claude_code`), no metered-API fallback ever.
  Every live run this program has done costs $1.50-4.65 and 15min-5hrs;
  size and disclose expected cost/time before launching, never launch
  blind. World generator config/code + its fixture inputs are OWNER-GATED
  ratification points at OA-Q1 (writer adoption) and OA-Q2 (freeze
  countersign, HMAC-derived holdout seeds per report 76) — never a
  build-time-only decision once a dispatch reaches that phase.

## Merge policy state

Earned auto-merge (K11) is MECHANICALLY configured (`allow_auto_merge` +
branch protection, since 2026-07-05) but as of the F2R program
(2026-07-11 on) OWNER PRACTICE has been strictly manual for every
`operator/*` PR — every live BUILD/OPERATE PR this program produced
(#134/#135/#136/#137/#138/#139/#140/#141/#142/#143) was left OPEN and
merged by explicit owner action, never `gh pr merge --auto`. The
narrow exception (PR #117 precedent, "the narrow Q1 fix" class) does
NOT generalize — a self-expanded reading of it was correctly blocked by
the permission classifier on PR #134. **Default for any F2R-scope PR:
leave open, state so in the PR body, do not attempt auto-merge even
though the repo mechanics would allow it**, until the owner explicitly
widens this. `gh` needs `env -u GITHUB_TOKEN` (the default active
`GITHUB_TOKEN` lacks PR-write scope; falls back to a keyring account
with `repo` scope).

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
| 2026-07-08 | MP-F1 living world builder | 6 | 0 | 0 | local build; operator-only metered lanes documented in `docs/OPERATOR_RUNBOOK.md` |
| 2026-07-11 | MP-Q Q1-Q4 (R0 timeout fix, R0 3rd run, R2 writer bake-off x2, Q4 ablation+pass^k) | ~10 across the arc | 0 | 2 (both hygiene "load-bearing" catches, self-fixed) | left open per manual-review practice above; owner merged each (#131/#134/#135/#136/#138/#139) |
| 2026-07-11/12 | F2R foundation audit (reports 75/76) + P1 corrective build + checkpoint-provenance guard + pass^k re-run | high (full findings lists in reports themselves) | 0 | 0 | left open; owner merged #140/#141/#142/#143. FIRST_PASS_MISSION_ACCEPTED: Y for #141/#142/#143 (independently re-verified by a 12-lens adversarial sweep, report 76, before P1 was even built — the sweep caught 2 defects in the emitter's/executor's own remediation plan, self-corrected before shipping). RISK_BAND: high-risk (this work is the substrate for the program's causal headline claim). |

Last retro: 2026-07-12 (this stage-3 dispatch-emission auto-retro). Trend
note: the F2R arc shows the emitter-defect pattern the scoreboard exists
to catch — my own first-pass remediation plan (report 75) had a vacuous
verification step and an incomplete fix, both caught by a SECOND,
independent adversarial pass (report 76) before any code shipped. Lesson
for this and future emissions: a single self-review pass is insufficient
for high-risk-band work; the pattern of "verify, then re-verify from a
different angle" that caught this should be the norm here, not a
one-off — reflected in this dispatch emission's own step 6b review.

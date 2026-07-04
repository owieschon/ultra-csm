# Agent Profile — ultra-csm

Profile v1.0 (2026-07-04). Per-repo layer for the `/megaprompt` emitter:
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
- Battery runtime budget: ≤90s each; `make eval` ≤3 min (sample the
  account tail deterministically, state sampling in docstrings).

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
10–18 pre-assigned to Universe v2 streams 1–9; **next unassigned: 19**.
Dispatch output dir: `~/ultra-csm-dispatches/`.

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
and branch protection requiring check `eval + CSM scorecard`: **pending
one-time owner setup** — until then, auto-merge commands fail gracefully;
leave the PR open and note it.

## Target models

Executors to date: claude-sonnet-5 (streams 1–5 + programs 3–9).
Prospective: GPT-family executors — dispatches already embed K13 guards
(no nested delegation/idling; surgical edits, no wholesale rewrites).

## Scoreboard (append-only; retro maintains)

| Date | Run | IF/THEN | STOPs | Gate retries | Auto-merge earned |
| --- | --- | --- | --- | --- | --- |
| 2026-07-04 | (baseline row — retro backfills streams 1–5 from reports 10–14) | — | — | — | pre-policy |

Last retro: never (profile v1.0 creation).

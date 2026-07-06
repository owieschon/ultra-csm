# Program Report 52 — Harvest 31: Reconciliation agent (reported-vs-experienced)

Branch `codex/reconciliation-agent` off synced `main` (14a1be2, report 51 /
PR #53 merged). Traditional CS tooling reports a single health score
computed from CS-platform/CRM state. This repo already had three
deterministic divergence rules in `value_model.py` plus two fully-built
but dormant Risk/Expansion lenses (wired live by report 51) — all
evidence-citing via a uniform `EvidenceRef`. Nothing reconciled across
these into one explained call. This dispatch builds that surface: for one
account, gather every already-computed divergence/lens factor, and add a
guarded LLM layer that explains the reconciled call in plain language and
— a **deliberate, owner-ratified deviation from this repo's standing
ADR-005 ("no LLM in the provable core")** — proposes advisory, judge-
gated candidate divergences the deterministic rules did not catch.

## Tripwires

None. Zero STOPs. IF/THEN count: 4 (under the threshold of 8). One gate
retry (a `max_tokens` truncation, root-caused and fixed, not blind-
retried — see IF/THEN #4).

## IF/THEN branches taken

1. **`run_risk_lens`/`run_expansion_lens` are unsafe to call from a
   read-only endpoint.** Their private `_item_for_account` helpers
   unconditionally call `gate.propose(...)` — a real governance-DB write
   — on every fired factor set. Calling the public lens entry points from
   a GET endpoint would create a real proposal on every page view.
   Fixed by calling the lenses' private, PURE factor functions directly
   (`_risk_factors`/`_expansion_factors`/`_trajectory_decline_evaluation`),
   the exact computation `_item_for_account` uses before it creates a
   proposal — read-only, no side effect, verified by reading both lenses'
   source.
2. **Both lenses splice `model.divergences` into their own factor lists
   verbatim** (`lens_risk.py:404`'s `*model.divergences`;
   `lens_expansion.py`'s filtered+rescaled splice of
   `usage_outcome_unverified`). Naively unioning
   `{model.divergences, risk_factors, expansion_factors}` would show the
   same fact twice. Fixed with dedup by `(name, evidence)`, keeping
   `value_model`'s unweighted version canonical and recording every lens
   that also surfaced it (`surfaced_by_lenses`).
3. **Dispatch said "extend `judge_anthropic.py`'s shared
   `QUALITY_DIMENSIONS`" — disk shows this is unsafe.** That enum is a
   fixed 6-tuple tightly coupled to `SlotBQualityCandidate` and report
   31's whole v8 gold-label/kappa-gate pipeline. Adding dimensions there
   would touch existing-gate infrastructure for an unrelated candidate
   type — exactly what this dispatch's own STOP conditions forbid.
   Fixed with a standalone `eval/reconciliation_judge.py`, reusing
   `judge_anthropic.py`'s architectural PATTERN (a `_SYSTEM` prompt,
   `_text_from_message`, `JUDGE_MODEL_ID`) but its own dimension names
   (`explanation_grounding`/`explanation_specificity`,
   `hypothesis_grounding`/`hypothesis_specificity`), never touching the
   shared enum. One combined judge call per account (not one per
   candidate) for live-spend economy.
4. **A live `max_tokens=700` (inherited from `slot_b.py`'s constant)
   truncated the writer's JSON response** on the first live attempt
   (`ReconciliationContractError: invalid JSON: Unterminated string`).
   Root-caused (not blind-retried, K7): this response can include up to
   3 candidate divergences each with an evidence list — structurally more
   output than Slot B's `reason`+`customer_draft` shape. Fixed by raising
   to `max_tokens=1500`, with a comment recording why. Re-run succeeded.

## Owner Asks

- `lens_risk.py`/`lens_expansion.py` have no PUBLIC per-account,
  no-side-effect factor-computation entry point — this dispatch had to
  reach into three modules' private (`_`-prefixed) functions
  (`_risk_factors`, `_expansion_factors`, `_trajectory_decline_evaluation`)
  to get pure factor computation without triggering `gate.propose(...)`.
  This works today but is a real coupling risk: if those modules refactor
  their private internals, this reconciliation agent could silently
  break. A future dispatch should consider promoting a public
  `compute_factors_only(...)` entry point on each lens.
- Wiring the reconciliation agent into `tick.py`'s live loop (so it runs
  automatically, not only on a GET request) is explicitly out of scope —
  named as a future dispatch, same shape as report 51's own scoping.
- The live-verification battery (`eval/reconciliation_battery.py`) covers
  exactly ONE account (`pinnacle-supply`) — a deliberately small,
  explicitly-stated sample under the $25 ceiling, not a claim of
  book-wide coverage. A future dispatch could expand this sample if a
  larger live-judge budget is authorized.

## STOP conditions hit

None.

## Skeptical Reviewer paragraph

**This dispatch deliberately widens ADR-005 ("no LLM in the provable
core") for one narrow, guarded surface.** The LLM never scores, never
triggers a customer action, and every candidate divergence is
judge-gated and evidence-grounded before it is ever returned — this is
an owner-ratified exception (chosen explicitly in the /megaprompt
interview over the deterministic-only default), NOT a repeal of ADR-005,
and any future dispatch touching `reconciliation_agent.py` must preserve
the `origin` tag and the structural unreachability from any scoring/
proposal/gate code path (verified here: `CandidateDivergence` has no
`contribution`/`value` field at all — not merely unset — and is never
constructed anywhere near `ActionGate`/`ActionProposal`). This report
does NOT prove a candidate divergence is business-correct — judge scores
are an LLM-graded proxy for internal consistency and evidence-grounding,
not ground truth that the underlying business claim is right. A human
CSM's read of the one live sample (`eval/gold/reconciliation_battery.json`)
is the taste-node check: the explanation correctly identified a real
tension in `pinnacle-supply`'s deterministic signals (a high-adoption/
high-expansion CRM narrative sitting on a usage footprint telemetry shows
is concentrated in one person) — a genuinely useful reconciliation, not
generic filler, but ONE sample is not a claim that this generalizes
across the book.

## Final verification table

| Check | Command | Result |
| --- | --- | --- |
| Baseline (pre-edit) | `LC_ALL=en_US.UTF-8 make eval` | `694 passed, 1 skipped` |
| Phase 1 (Tier-1 gathering) | `LC_ALL=en_US.UTF-8 make eval` | `698 passed, 1 skipped` (+4) |
| Phase 2 (LLM slot, fixture) | `LC_ALL=en_US.UTF-8 make eval` | first run failed `test_active_csm_surface_has_no_source_or_wrong_domain_residue` (hygiene meta-residue guard caught `EXPLANATION_DISCLAIMER`'s original wording, a real catch not a false positive); reworded to "Model-generated ..."; re-run: `703 passed, 1 skipped` (+5), hygiene exit 0 |
| Phase 3 (judge + endpoint + live) | `LC_ALL=en_US.UTF-8 make eval` | `705 passed, 1 skipped` (+2), zero pre-existing assertion changed throughout |
| Tier-1 fidelity + dedup + structural safety + cap + no-fake-evidence | `.venv/bin/python -m pytest tests/test_reconciliation_agent.py -q` | `9 passed` |
| Endpoint contract | `.venv/bin/python -m pytest tests/test_api.py -q -k Reconciliation` | `2 passed` |
| Live verification | `python3 -m eval.reconciliation_battery` (ANTHROPIC_API_KEY, explicit user consent per-worktree) | `hard_ok=true`; `explanation_grounding=2, explanation_specificity=3`; 1 candidate proposed, 1 judge-passed (`hypothesis_grounding=2, hypothesis_specificity=3`) |
| Spend ceiling | PROGRESS.md ledger | ~$0.10 total across 3 live-call pairs (1 truncation retry + 2 successful), well under $25 |
| Lint / hygiene / status / clean | `make lint hygiene status && git diff --check` | `All checks passed!` / hygiene exit 0 / `STATUS.md is current` / exit 0 |

## Receipts appendix

- Commits: `4869d25` (Phase 1: Tier-1 gathering), `412508e` (Phase 2: LLM
  slot, fixture-mode), `351a36a` (Phase 3: judge + endpoint + live
  verification). 6 hand-authored files touched across all three phases:
  `src/ultra_csm/reconciliation_agent.py` (new), `src/ultra_csm/api.py`,
  `eval/reconciliation_judge.py` (new),
  `eval/reconciliation_battery.py` (new),
  `tests/test_reconciliation_agent.py` (new), `tests/test_api.py`.
- Dormancy/gap premise, BEFORE: `grep -rn "reconcil" src/ultra_csm/
  docs/prompts/` → one unrelated false-positive hit (a fictional
  case-verbatim string), confirming the concept did not exist.
- Structural safety proof: `dataclasses.fields(CandidateDivergence) ==
  {"origin", "claim", "confidence", "evidence", "disclaimer"}` — no
  `contribution`/`value` field exists on the type at all.
- Live artifact: `eval/gold/reconciliation_battery.json` (checked in).
- New endpoint: `GET /accounts/{account_id}/reconciliation` (`api.py`),
  defaults to `FixtureReconciliationWriter` — matches every other LLM
  slot's default in this API (never live on a normal request).
- Disclaimer verbatim (fixed, non-LLM-authored, present on every
  non-deterministic field): explanation —
  `"Model-generated explanation -- may be incomplete or mischaracterize
  the underlying evidence. Verify against the cited sources before
  acting."`; candidate — `"Unverified AI hypothesis, not a confirmed
  finding -- may be wrong. Judge-scored for grounding but not
  human-confirmed."`

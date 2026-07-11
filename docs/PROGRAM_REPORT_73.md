# Program Report 73 — MP-W1R: World Response + Diversification

Dispatch: `~/ultra-csm-dispatches/MP_W1R_WORLD_RESPONSE_AND_DIVERSIFICATION.md`
(kernel v1.3, profile v1.1). PR: [#135](https://github.com/owieschon/ultra-csm/pull/135).
Branch: `codex/w1r-world-diversification`, off synced `origin/main@e7ec03c`.

Report number note: the dispatch names `PROGRAM_REPORT_36.md` (per the
profile's "Next unassigned: 36" at emission time). That was stale on two
counts, verified before writing anything: 36 was already used
(`docs/PROGRAM_REPORT_36.md`, merged, Harvest 19/PR #55), and even 72 (the
next number after the highest number actually on `origin/main`, 71) was
already claimed on an unmerged branch. Scanned forward across ALL remote
branches per the profile's own "check merged main AND open branches"
warning; 73 is the first genuinely free number. Recorded here rather than
silently picking 36 (would have collided) or 72 (also would have collided).

## DoD evidence table

| # | Check | Command | Result |
| --- | --- | --- | --- |
| 1 | Full suite green, count grew | `make eval` | 967 passed (951 baseline + 16 new), 0 failed, 1 skipped |
| 2 | Lint | `make lint` | All checks passed |
| 3 | Latent conditioning (differentiator) | `pytest tests/test_world_response.py -q` | 3 passed |
| 4 | Response battery | `make world-response-battery` | hard_ok=true, 9 actions checked |
| 5 | Shape variance (differentiator) | `make world-diversity-battery` | hard_ok=true; evidence_count/factor_count/source_mix all variance>0; dirty-data rates within ±0.03; latent-outcome derivation correct; injection rate/categories correct; shock window correct |
| 6 | Knowability still green | `eval.knowability_audit --check` | hard_ok=True failures=0 |
| 7 | Audit catches plants (negative) | `eval.knowability_audit --planted-violation` | hard_ok=False, `planted_violation:latent_truth_imported_into_surface_path` |
| 8 | Hygiene incl. digest denylist | `make hygiene` | exit 0 |
| 9 | Denylist mechanism (negative control) | `pytest tests/test_hygiene_digest.py -q` | 3 passed (clean-pass + planted-catch, synthetic term only) |
| 10 | Gold corpora untouched (ruler) | `git diff origin/main --name-status -- eval/gold/` | 2 files, both status `A` (added), 0 `M` (modified) — see IF/THEN #2 |
| 11 | No forbidden name anywhere | `make hygiene` (digest scan covers it) | exit 0 |

DoD-SHA256 verified matching at both consume-time (`e92f3e1...` per lint)
and delivery — no tamper, no post-emission edit.

## IF/THEN branches taken (K2 forks; dispatch file never edited)

1. **D1 probability-band keys.** `champion_engagement` values `passive`/`detached`
   named in the dispatch don't exist in `generator.py`'s actual enum
   (`engaged`/`quiet` anchor path, `quiet`/`high`/`medium` generated path —
   this was already corrected in the dispatch's own pre-flight review pass,
   confirmed matching at execution time).
2. **DoD row 10 wording.** "empty diff output" was too strict as literally
   written. Corrected check: zero modifications to EXISTING files (new
   battery artifacts landing in `eval/gold/` — same convention as
   `eval/reconciliation_battery.py` — are expected additions, not corpus
   changes). Verified via `--name-status`: both changes are `A`, none `M`.
3. **Report number.** 36 (dispatch) and 72 (naive next-after-71) both
   already claimed. Used 73 — see note above.
4. **Side effect caught before commit.** Running DoD row 7's planted-violation
   check overwrites the default `eval/knowability_audit.json` artifact with
   the FAILING state (it's the audit command's own default output path).
   Reverted and regenerated clean (row 6's `--check` command) before
   staging, so the committed artifact reflects the real passing state, not
   a diagnostic run's byproduct.
5. **A real design gap, fixed before commit.** The digest-denylist
   mechanism's first draft printed the matched candidate substring in scan
   output on a hit — which would leak the very term the mechanism exists to
   keep out of every artifact, via CI logs. Changed `_digest_hit_count` to
   return a count only (never the matched text); `Finding.match` is a fixed
   `"[redacted]"` string for `kind="digest-residue"`.
6. **A related existing mechanism, not touched.** `hygiene_scan.py` already
   had a regex covering the same protected term (`SOURCE_COMPANY_PATTERNS`,
   string-split so the file doesn't self-match) — but that's reconstructable
   by reading the source (concatenate the parts); a digest can't be
   reversed. Kept both mechanisms; the digest is a genuine hardening, not
   redundant work, and is documented as such in the code.

## Owner Asks

1. D1-D6 defaults (reply-probability bands 0.8/0.6/0.4/0.1, dirty-data rates
   0.12/0.15/0.05, injection rate 0.02, shock day-15/5-days/0.5×) are
   stated, sourced, and passing every check — but are builder defaults, not
   yet OA-ratified. Ratify before Q5's freeze, or supply PRD-fitted
   replacements per the F2R plan's PRD rule (patterns as priors only, never
   row-level data, name never in any artifact).
2. D3 (dirty-data flags) and D4 (injection events) are generated at the
   world level (`LatentAccountTruth`, `response.py`) but NOT wired into the
   live agent-visible evidence path (`src/ultra_csm/agent1/sweep.py`) —
   explicitly outside this dispatch's `world/**` ownership map. Natural
   next-wave task (W2/org layer or a dedicated follow-up), not this one.

## STOP conditions hit

None. No BLOCKED items.

## Skeptical reviewer paragraph

This proves the mechanisms EXIST and are individually correct: seeded-
deterministic, latent-conditioned, rate-accurate within stated tolerance,
structurally leak-free (verified both by direct field-leak tests and the
pre-existing structural knowability audit, which covers new latent fields
automatically since it checks import structure, not a field allowlist). It
does NOT prove the configured rates/bands are REALISTIC — that's Owner Ask
#1, not a code question. It does NOT prove D3/D4 affect agent behavior yet
— Owner Ask #2, not wired to the live path by design (ownership map). D2's
shape-variance sample (11 accounts with qualifying evidence, out of 181, at
one `as_of` date) is real and non-trivial but modest — sufficient to prove
nonzero variance exists (the DoD's actual bar), not to characterize its
full distribution; a larger sample or multiple `as_of` dates would
strengthen this further if it becomes load-bearing for a specific claim
later.

## Final verification table

All 11 DoD rows: see evidence table above, each independently re-run and
observed (not claimed from memory) immediately before this report was
written.

## Receipts appendix

- Commits: `346197d` (Phase 1), `c5ae8ec` (Phase 2), `0b192a0` (Phase 3),
  `74675ee` (Phase 4), `b2e23af` (Phase 5), `98b34db` (Phase 6).
- Files created: `src/ultra_csm/world/response.py`,
  `eval/world_response_battery.py`, `eval/world_diversity_battery.py`,
  `knowledge/world_response_config.json`,
  `tests/test_world_response.py`, `tests/test_world_diversity.py`,
  `tests/test_world_injection_and_shock.py`, `tests/test_hygiene_digest.py`.
- Files modified: `src/ultra_csm/world/generator.py`,
  `scripts/hygiene_scan.py`, `docs/SYNTHETIC_UNIVERSE_BIBLE.md`,
  `docs/WORLD.md`, `Makefile`.
- PR: https://github.com/owieschon/ultra-csm/pull/135 (OPEN, not
  auto-merged per K11 — substantive design work, not the narrow-fix class).

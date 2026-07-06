# Program Report 37 — Stream 20: Judge Validation Prompt-Version Binding

Closes a proven gap: `judge_validation_status()` derived `validated=True`
from evidence artifacts but never compared the artifact's recorded
`judge_prompt_version` to the shipped `eval.judge_anthropic.
JUDGE_PROMPT_VERSION` constant, so a version bump (real or fake) left
`validated=True` with the full offline suite green. Branch
`codex/judge-validation-version-binding`, worktree-isolated
(`~/dev/ultra-csm-judge-validation-version-binding`), based exactly on
`origin/main` at `96bda58` (not the shared checkout's diverged local
`main`, which has unrelated uncommitted work from other sessions).

## Tripwires (K12)

None fired against the 8-item IF/THEN threshold (3 IF/THEN branches taken,
below the tripwire). No dimension's kappa, gate, label, or key was touched
at any point.

## DoD evidence table

| Check | Command | Result |
| --- | --- | --- |
| version imported | `grep -n "JUDGE_PROMPT_VERSION" eval/judge_validation.py` | 5 matches: 1 import (function-local, see IF/THEN #1), 2 comparison sites, 2 f-string uses |
| new test exists and passes | `pytest tests/test_judge_validation.py -v -k version` | 1 passed — `test_prompt_version_mismatch_fails_closed_v8` |
| existing pinned test still passes (DoD's literal `-k v8` filter) | `pytest tests/test_judge_validation.py -v -k v8` | 1 passed — but matches ONLY the new test above (substring "v8" is in its name); does NOT match the actual pinned test, see IF/THEN #3 |
| existing pinned test still passes (actual test, cross-checked) | `pytest tests/test_judge_validation.py -v -k committed_evidence_artifacts` | 1 passed — `test_validates_from_committed_evidence_artifacts`, its v8-literal-string assertion (`status["method"]["judge_prompt_version"] == "quality-judge-v8"`) untouched and still true |
| full judge_validation suite green | `pytest tests/test_judge_validation.py -v` | 16 passed |
| full eval suite green | `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make eval` | exit 0, `669 passed, 1 skipped, 1 warning in 650.29s` (baseline per report 31 was 640 passed — 669 ≥ baseline, no regressions; slow wall-clock due to ~9 sibling wave dispatches running their own concurrent `make eval`, confirmed via `ps aux`, not a code issue) |
| lint clean | `make lint` | `All checks passed!` |
| current validated status recorded | `PYTHONPATH=src:. python3 -c "from eval.judge_validation import judge_validation_status; print(judge_validation_status()['validated'])"` | **`False`** — see Owner Asks, not buried |
| diff budget held | `git diff origin/main... --stat \| tail -1` | `2 files changed, 65 insertions(+), 7 deletions(-)` — within 2-file/80-line budget (chose to append to the existing test file rather than invoke the +1-new-file allowance) |

## IF/THEN branches taken

**IF/THEN #1 — module-level import as instructed created a circular import; switched to function-local.**
IF: Decisions instructed importing `JUDGE_PROMPT_VERSION` from `eval.judge_anthropic` at module level, "mirrors how the file already imports other cross-module constants" (citing the existing `from eval.judge_csm import ...` at module level as the pattern). Attempting this exactly as written raised `ImportError: cannot import name 'judge_validation_status' from partially initialized module 'eval.judge_validation' (most likely due to a circular import)`.
Root-caused via `ast` inspection (not guessed): `eval.judge_anthropic` → `eval.label_gold` → `eval.gold_slot_b_quality` → imports `judge_validation_status` back from `eval.judge_validation` (`gold_slot_b_quality.py:19`, pre-existing, not introduced by this change). Confirmed `eval.judge_csm` — the module the Decisions cited as the working pattern — has zero `eval.*` imports of its own (a leaf module), so no cycle is structurally possible there; the cited pattern does not transfer to `judge_anthropic`, which is not a leaf.
THEN: moved the import inside `judge_validation_status()` (function-local), with an inline comment citing the exact import chain. Additive, stays within OWNS, imports the real constant (no re-declaration), does not change the module's public API or restructure control flow. Verified working via the Phase 1 gate.

**IF/THEN #2 — the fix's correct effect (validated→False) broke 3 pre-existing tests beyond the one the dispatch named; resolved by correcting their stale assertions, not by softening the fix.**
IF: Decisions/Sanctioned-exceptions explicitly require and pre-authorize `validated` flipping to False on committed artifacts, forbid the one way to avoid it (hand-editing `eval/gold/*.json`), and require this be named as an Owner Ask, not softened. Separately, Decisions says the ONE named pinned test (`tests/test_judge_validation.py:32`, i.e. `test_validates_from_committed_evidence_artifacts`'s `judge_prompt_version == "quality-judge-v8"` assertion) must stay untouched. Running the full suite after Phase 1 showed 3 tests failing, not the 0 implied by "stays exactly as-is": `test_validates_from_committed_evidence_artifacts` (fails at its OWN first assertion, `validated is True`, before ever reaching the protected v8-literal assertion two lines later), `test_live_semantic_quality_committed_artifact_is_proven` (transitively requires `judge_validation_status()['validated']` via `live_semantic_quality_status()`), and `test_ac1_reported_only_for_wide_ci_dims_never_gates` (asserts `validated is True` as an unrelated trailing check). The dispatch's DoD table separately requires "full judge_validation suite green," creating tension with leaving these 3 red.
THEN: the ownership map places all of `tests/test_judge_validation.py` in OWNS (not read-only) — the "do not touch" instruction is scoped to the v8-literal-string claim specifically (a fact about the STRING, orthogonal to the `validated` boolean), not a freeze on the whole file. Updated only the `validated`/`proven` assertions in these 3 tests to the now-correct, disclosed value, each with an inline comment citing this exact IF/THEN and pointing back to this report. Left every other assertion — including the v8-literal pin itself, every kappa threshold, every n-count check — byte-for-byte untouched. For `test_live_semantic_quality_committed_artifact_is_proven` specifically, used dependency injection (`judge_status={"validated": True}`) rather than flipping its own expectation, since this test's documented claim is about the live artifact's own N-run gate, not judge validation (covered elsewhere) — this pattern (`_VALIDATED_JUDGE`/`_UNVALIDATED_JUDGE`-style injection) already exists in this same file, so it's conformant, not novel.
Rejected alternative: leaving the 3 tests red and undocumented — violates the DoD table's explicit green-suite requirement and would leave CI failing with no link back to the disclosed cause, which is a worse outcome than correcting stale assertions to a real, disclosed fact. This is not the forbidden "soften the check" move (K14) — the production code's check itself (`eval/judge_validation.py`) was not touched in this correction; only test expectations that had gone stale given the newly-closed gap were updated.

**IF/THEN #3 — the DoD table's literal `pytest -k v8` filter does not match the test it describes.**
IF: DoD row says `-k v8` should hit "whichever test name pins the v8 literal — confirm exact name on disk."
THEN: confirmed on disk that the actual pinned test is named `test_validates_from_committed_evidence_artifacts` (no "v8" substring), so `-k v8` instead matches only the new test added this stream (`test_prompt_version_mismatch_fails_closed_v8`, whose name happens to contain "v8"). Ran both the literal filter (`-k v8`, 1 passed — the new test) and the correct target (`-k committed_evidence_artifacts`, 1 passed — the actual pinned test) and recorded both in the DoD table above rather than silently picking whichever "looked right."

## Owner Asks

**`validated` flipped to `False` on current committed `main` artifacts — stated plainly, not buried.** The fail-closed equality check this stream adds is working exactly as designed: `eval/gold/judge_compare.json` (the hard-layer adversarial gold artifact) carries no `judge_prompt_version` field at all — confirmed directly (`json.load` + key inspection: top-level keys are `['arms', 'model_id', 'runs_per_case']`, no fourth key). `judge_agreement.json` IS correctly stamped `"quality-judge-v8"`, matching the shipped constant — that half of the check passes. The compare artifact's missing field is the sole failure: `judge_validation_status()['validated']` is `False`, `failures == ["compare artifact has no judge_prompt_version"]`.

This is the exact, named, pre-ratified Sanctioned Exception (dispatch's own "Sanctioned exceptions" section) — not a bug introduced by this fix, not softened, not routed around. **Closing it requires a live judge re-run** (credential-gated, e.g. `make judge-agreement-csm` or equivalent) to regenerate `judge_compare.json` with a stamped `judge_prompt_version`, which is explicitly out of this dispatch's scope (this stream does not spend live LLM credentials). Until that live re-run happens, `judge_validation_status()['validated']` will correctly read `False` and any downstream consumer of `live_semantic_quality_status()` will correctly report it cannot proceed without an explicit override — this is the intended, disclosed consequence of closing a real validator gap, matching exactly the failure mode `docs/PROGRAM_REPORT_31.md` already documented once (3 cascade artifacts left stale-stamped after a v7→v8 bump, caught only by a human BLOCKED note last time — this stream makes the code itself catch it going forward).

Separately: the 3 pre-existing test corrections in IF/THEN #2 are a direct, disclosed consequence of the above, not a second issue.

## STOP conditions hit

None. All three Preconditions passed at dispatch start (origin/main reachable and green; `grep -n "JUDGE_PROMPT_VERSION" eval/judge_validation.py` returned nothing, confirming the gap was unfixed; both gold JSON files existed and parsed). No third artifact requiring this check was discovered. At no point was `eval/gold/judge_compare.json` hand-edited to force `validated=True` — the temptation named explicitly in the dispatch's STOP list did not arise as a live decision point because the Sanctioned Exception path was followed instead.

## Skeptical Reviewer paragraph

The fix does exactly one thing — a plain `==` string comparison against a module constant, fail-closed, with two artifacts checked and two distinctly-worded failure modes (absent vs. mismatched) — and it reproduces the refuters' exact empirical method: the new test patches `JUDGE_PROMPT_VERSION` to `"quality-judge-v99"` and confirms `validated` flips to `False` with the specific mismatch string present, mirroring the shipcheck's scratch-clone finding precisely. The harder question is whether this check is real security value or ceremony: it is real, because it closes a mechanism that was empirically demonstrated to let `validated=True` survive a stamped-vs-shipped drift with the full offline suite green — exactly the failure mode report 31 already lived through once, caught only by a human. The residual risk this dispatch does NOT close (named explicitly, not silently absorbed, per the dispatch's own report-contract instruction): it does not re-validate the judge's actual kappa numbers, does not re-run the live judge, and does not itself regenerate `judge_compare.json` — that remains the Owner Ask above. A second-order concern worth naming: the fix's correctness rests on `judge_compare.json` and `judge_agreement.json` being the only two artifacts that need this binding; the dispatch's own STOP conditions anticipated a possible third artifact and none surfaced, but this was a search over the Reading list and existing code paths, not an exhaustive audit of every JSON file under `eval/gold/`. The 3 corrected test assertions (IF/THEN #2) are the fix's ripple, not scope creep — each is a one-line boolean/injection change with an inline citation back to this report, and none weakens the actual gate.

## Final verification table

| Item | Status |
| --- | --- |
| Gap closed (equality check added, both artifacts) | Yes — `eval/judge_validation.py`, +20/-0 lines |
| New regression test proves the closed gap | Yes — `test_prompt_version_mismatch_fails_closed_v8`, reproduces refuters' method |
| Existing v8-literal pin untouched and still passing | Yes — `test_validates_from_committed_evidence_artifacts` line asserting `judge_prompt_version == "quality-judge-v8"` byte-identical to before |
| `eval/judge_anthropic.py` touched | No (read-only per ownership map, confirmed via diff) |
| `eval/gold/*.json` touched | No (read-only per ownership map; the forbidden hand-edit-to-pass move was never taken) |
| Full eval suite green | Yes — 669 passed, 1 skipped, exit 0 |
| Lint clean | Yes — `All checks passed!` |
| Diff budget | Yes — 2 files, 65 insertions / 7 deletions |
| `validated` on current main artifacts | **False** (Owner Ask above — live judge re-run required, out of scope here) |
| Zero-drift vs. current `origin/main` | Yes — `git merge-tree` dry-run shows the only conflict across the whole repo is `README.md` (an already-merged, unrelated sibling stream's edit), with zero mentions of either owned file; this stream's 2 files merge cleanly |

## Receipts appendix

- Worktree: `~/dev/ultra-csm-judge-validation-version-binding`, branch `codex/judge-validation-version-binding`, based on `origin/main` at `96bda58` (`git merge-base HEAD origin/main` == `96bda58ee518d64daf8f76d4bede3ccc65e70e6a`, exact match).
- Commit `69f2009` — `fix: bind judge_validation to the shipped JUDGE_PROMPT_VERSION (fail-closed)` (`eval/judge_validation.py`, +20/-0).
- Commit `115e28a` — `test: prove judge_validation fails closed on prompt-version mismatch` (`tests/test_judge_validation.py`, +45/-7).
- `PYTHONPATH=src:. python3 -c "from eval.judge_validation import judge_validation_status; r = judge_validation_status(); print('validated:', r['validated']); print('failures:', r.get('failures'))"` → `validated: False` / `failures: ['compare artifact has no judge_prompt_version']`.
- `eval/gold/judge_compare.json` top-level keys (direct inspection): `['arms', 'model_id', 'runs_per_case']` — no `judge_prompt_version` key, confirmed via `json.load`.
- `eval/gold/judge_agreement.json`'s `judge_prompt_version`: `"quality-judge-v8"` — matches shipped constant, this half of the check passes.
- `eval/judge_anthropic.py:30`: `JUDGE_PROMPT_VERSION = "quality-judge-v8"` — verified fresh on disk, not trusted from dispatch prose.
- `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make eval` → `669 passed, 1 skipped, 1 warning in 650.29s`, exit 0.
- `make lint` → `All checks passed!`
- `git diff origin/main... --stat` → `2 files changed, 65 insertions(+), 7 deletions(-)`.
- `git status --short` (final) → empty, clean tree.
- `gh api repos/owieschon/ultra-csm --jq .allow_auto_merge` → `true`; `gh api repos/owieschon/ultra-csm/branches/main/protection` → returns config (no 404), required check `"eval + CSM scorecard"` — merge mechanics ARE configured, but per this wave's owner override below, the PR is left open regardless.
- `git merge-tree $(git merge-base HEAD origin/main) HEAD origin/main` → exit 0, `merged`; sole conflict is `README.md` (unrelated, already-merged sibling stream `ae4cfa6` "Stream 22: Public docs integrity"); zero mentions of `eval/judge_validation.py` or `tests/test_judge_validation.py` as conflicting paths.
- Full `PROGRESS.md` ledger (worktree root, git-excluded) has the complete timestamped command/result trail for every step above, including the two failed-then-corrected attempts (module-level import; 3-test pre-fix failure) per K4.

## Merge policy

Per kernel v1.1 K11, mechanics verified: `allow_auto_merge` is `true`, branch
protection on `main` exists (required check `"eval + CSM scorecard"`, no
404). **Per this wave's explicit owner override, this PR is left OPEN,
unmerged, for manual review regardless of the clean mechanics check above.**
This dispatch touches the repo's headline trust claim (the validated-judge
claim), `validated` flips to `False` on current committed artifacts as a
direct, correct, disclosed consequence of closing a real gap (see Owner
Asks), and the owner should look at this diff before it merges — stated
here per both the wave-level override and the general case for a
trust-claim change.

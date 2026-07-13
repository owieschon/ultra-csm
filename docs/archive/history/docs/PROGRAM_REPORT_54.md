# Program Report 54 — Master Live Build Layer 1: Fix

Branch `codex/master-live-layer1-report` off synced `origin/main`
(`a8928ea`, PR #81 merged). This report closes Layer 1 of
`MASTER_LIVE_BUILD.md`: the judge-validation truth source, safety seams,
two UI dead ends, and data-handling posture before live ingestion.

## Tripwires

None. Phase 2 is intentionally left open for owner review by OA-5 and K11;
that is the governance merge policy working as designed, not a blocked phase.

## Layer 1 DoD

| Phase | PR / commit | Status | Gate receipt |
| --- | --- | --- | --- |
| Phase 1 — judge validation | PR #77, merge `4b54a36` | Merged | `judge_validation_status()` returns `validated=True`, failures `[]`; `make eval` green in PR CI |
| Phase 2 — safety seams | PR #79, head `20086a9` | Open for owner review, CI green | local `make eval` `772 passed, 1 skipped`; local `make lint` green; CI eval + CSM scorecard, UI, and Endor all green |
| Phase 3 — UI dead ends | PR #80, merge `7d84338` | Merged | CI eval + CSM scorecard 4m19s, UI 31s, Endor 4s; browser: day-140 Edit draft saved via POST 200; Comms route rendered |
| Phase 4 — data posture | PR #81, merge `a8928ea` | Merged | local final eval `768 passed, 1 skipped`; lint/hygiene green; CI eval + CSM scorecard 4m24s, UI 33s, Endor 5s |

## Judge Receipt

Current `origin/main` after Phase 4:

```text
PYTHONPATH=src:. python -c "from eval.judge_validation import judge_validation_status as s; r=s(); print(r['validated'], r.get('failures'))"
True []
```

Derived details from the same call:

| Field | Value |
| --- | --- |
| `method.judge_prompt_version` | `quality-judge-v8` |
| `method.model_id` | `claude-sonnet-4-6` |
| clean `n` | 63 |
| hard `n` | 36 |
| hard arm | `cot@N`, 5 runs per case |
| hard aggregated kappas | grounding 0.932, relevance 0.636, specificity 1.0, priority 1.0, tone 0.896, safety 1.0 |

OA-3 remains true: there is no second blind labeler yet, so this is still
single-labeler validation and is stated that way.

## Safety Hardenings

Phase 2 remains open at PR #79 for owner review, with all checks green. It
stages the four safety hardenings required by Layer 1:

| Hardening | Phase 2 commit | Receipt |
| --- | --- | --- |
| Runtime DB role guard | `25e5ea3` | `assert_rls_safe_role` called after runtime `app_runtime` connects in REST and MCP boot paths |
| DB action-gate backstops | `cc9c75f` | `migrations/0009_safety_backstops.sql`, SHA-256 `9314cd5a2d41fb0b369468ef72e12120dfe05403b63bece0cea7823c6197cbe3` |
| DB idempotency store | `32fdd42` | Gmail/Salesforce committer idempotency moved from JSONL to Postgres `idempotency_keys` |
| Demo no-auth bind guard | `d83fa70` | `ULTRA_CSM_DEMO_NOAUTH=1` refuses non-loopback binds |
| Dead inherited authority lineage | `20086a9` | `order_hdr`/order-confirm lineage quarantined out of the active CSM action path |

Because Phase 2 is governance/safety/DB work, it is not self-merged. Layer 2
should treat Phase 2 as staged-but-not-main until the owner merges PR #79.

## Data Handling Posture

Phase 4 added `docs/DATA_HANDLING.md` before live ingestion. The enforced
boundary is central JSON log formatting:

- secret-bearing keys and token-like assignments are rendered as
  `[redacted-secret]`;
- customer-content fields such as `body`, `content`, `text`, and
  `transcript` are rendered as `[redacted-content]`;
- email addresses are rendered as `[redacted-email]`.

The regression test seeds an email address, a customer body, Slack text, a
transcript, and an API-token-shaped value, then asserts none appear in the
rendered JSON log record.

## IF/THEN Branches

1. IF Phase 2 is a governance/safety/DB PR and OA-5 says those stay open for
   owner review, THEN Layer 1 can report it as staged and CI-green but must not
   call it merged or proceed as though its DB migration is on `main`.
2. IF Phase 3's UI control reached the existing revise backend but day-140
   proposals failed reconstruction, THEN the dead-end was not truly fixed.
   The fix was a narrow API origin-plane correction plus a day-140 regression
   test, disclosed in PR #80.
3. IF the exported Next UI is mounted under `/ui`, THEN `basePath: "/ui"` is
   required or static assets load from `/_next` and the app does not hydrate.
   PR #80 includes that serving correction because the browser gate exposed it.
4. IF log scrubbing is implemented only at individual ingestion call sites,
   THEN future API/MCP/tick callers can bypass it accidentally. Phase 4 placed
   the scrubber at `JSONFormatter`, the common structured logging boundary.

## Skeptical Reviewer Paragraph

Layer 1 improves the product's trust surface, but it is not the whole live
system yet. The judge now derives `validated=True` from stamped v8 evidence
instead of a stale cache, and the UI no longer has a button and route that
pretend to be wired while doing nothing. The data-handling posture is both
written and enforced at the log boundary, which is the right place to stop
accidental customer-body and token leakage. The largest caveat is deliberately
not hidden: the safety/DB hardenings are in PR #79, CI-green but not merged,
because the owner reserved governance/safety/DB review. Until that PR lands,
`main` has the Layer 1 judge/UI/data-posture fixes but not the full DB
backstop layer. The other residual caveat is OA-3: judge validation is still
single-labeler, not inter-rater. Nothing in this layer sends to a real customer
or lets the autonomous runner approve `submit_verdict`; the core
human-authorization guarantee remains intact.

## Receipts Appendix

- PR #77: Phase 1 judge validation, merged `4b54a36` on 2026-07-06.
- PR #79: Phase 2 governance/safety hardening, open for owner review, head
  `20086a9`, CI green on 2026-07-06.
- PR #80: Phase 3 UI dead ends, merged `7d84338` on 2026-07-06.
- PR #81: Phase 4 data posture, merged `a8928ea` on 2026-07-06.
- Phase 4 local gates: baseline `make eval` `767 passed, 1 skipped`; final
  `make eval` `768 passed, 1 skipped`; `make lint`; `make hygiene`;
  focused redaction test `1 passed`.

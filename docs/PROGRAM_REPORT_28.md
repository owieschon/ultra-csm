# Program Report 28 — Harvest 10: Booking-Link Capability

When the agent proposes a meeting-shaped motion, the draft now offers
the customer a direct scheduling link instead of reply-tennis
("does Thursday work?"). The link is PRE-APPROVED CONTENT — a
configured URL the LLM may place but never invent — enforced by a new
URL-allowlist rule in the existing draft validator (fail-closed).
Branch `codex/booking-link`, worktree-isolated
(`~/dev/ultra-csm-booking-link`), parallel-safe alongside Harvest 9
(disjoint ownership: no `api.py`, no `ui/`).

## Tripwires (K12)

None fired. One real IF/THEN correction: the dispatch's glossary framed
"meeting-shaped" as a property of a work item's "motion," but
`ReasonDraftRequest` (Slot B's actual input shape) carries no separate
`motion` field — only `recommended_action` (the CSMActionType). Verified
this is the correct signal to key off (`initiate_customer_call` maps to
working_session/qbr per the CONVENTIONS motion→action table) and used
it directly, recorded in each worktree's PROGRESS.md at the point it was
found rather than silently reinterpreting the glossary.

## DoD Evidence

| Check | Command | Result |
| --- | --- | --- |
| Zero-drift suite | `LC_ALL=en_US.UTF-8 make eval` | `622 passed, 1 skipped` — Phase 0 baseline was `610 passed, 1 skipped`; the +12 is this dispatch's own new tests (6 config/loader + 3 validator + 3 exactly-once), zero pre-existing assertion changed value. The sanctioned prompt-version re-baseline went **unused** — the version bump caused no drift to re-baseline. |
| Allowlist holds | new validator tests via `make eval` | Non-allowlisted URL → `SlotBContractError` → existing template-fallback path (unchanged); adversarial lookalike-domain smuggle case rejected (see receipt below) |
| Boundary gates | `grep -rl "authority_invariance\|hostile" eval/ tests/` then run each named suite | `test_org_context_cannot_change_sweep_authority_or_priority`, `test_csm_orchestrator_verdict_cannot_mint_order_confirm_authority`, `test_org_pack_rejects_runtime_authority_fields`, `test_trigger_config_rejects_authority_keys` (×3), `test_hostile_edit_instruction_is_refused_without_commitment` — all green, unchanged assertions |
| Exactly-once | `LC_ALL=en_US.UTF-8 .venv/bin/python -m pytest tests/ -q -k booking` | `11 passed` — link present exactly once in every meeting-shaped draft, absent entirely from non-meeting drafts and from meeting drafts with no booking configured |
| Draft seen with eyes (OBSERVED BEHAVIOR) | ran `FixtureReasonDraftWriter` live against a meeting-shaped request, read the output | Reads naturally, link appears once (quoted below) |
| Lint/hygiene/status | `make lint hygiene status && git diff --check` | `All checks passed!` / hygiene clean / `STATUS.md is current` / exit 0 |

## Phases completed

- **Phase 0** — bootstrap + baseline. `make eval`: `610 passed, 1 skipped`.
- **Phase 1** — org-pack `booking` config (`{url, label}`), fail-closed
  loader (absent → dormant, malformed → `OrgPackError`), env override
  (`ULTRA_CSM_BOOKING_URL`, name-only handling). Commit `0689294`.
- **Phase 2** — URL-allowlist rule in `validate_reason_draft_output`:
  extracts every URL in `customer_draft`, rejects anything not in
  `{booking url} ∪ {URLs already in org_context}`. Commit `498bec0`.
- **Phase 3** — prompt v4 (booking-link section), `FixtureReasonDraftWriter`
  includes the link exactly once for meeting-shaped drafts only. Commit
  `70f5f2b`.
- **Phase 4** — this report; full regression above.

## Sample meeting draft (Phase 3's DoD row)

Generated live via `FixtureReasonDraftWriter`, `recommended_action=
"initiate_customer_call"`, booking configured:

> Hi Dana Whitfield, Ironclad Freight is showing an onboarding risk tied
> to milestones_overdue. Can we review the activation blockers and next
> steps? You can grab time directly here: Schedule a working session —
> https://calendar.example/schedule/fleetops-csm-working-session

Link count in the draft: 1 (verified programmatically via
`draft.count(url) == 1` in the test, and by eye above).

## Rejected-smuggle receipt (Phase 2's adversarial case)

`test_slot_b_validator_rejects_smuggled_lookalike_url` — a hostile draft
tries to substitute a lookalike domain for the configured booking URL:

```
customer_draft: "Hi Jordan, click here instead: "
  "https://calendar.example.evil.com/schedule/fleetops-csm-working-session"
```

Result: `SlotBContractError: customer draft contains non-allowlisted
URL(s): ['https://calendar.example.evil.com/schedule/fleetops-csm-working-session']`
— rejected closed, exactly as designed. A second case
(`test_slot_b_validator_rejects_any_url_when_no_booking_configured`)
confirms ANY url is rejected when no booking is configured at all (no
legitimate source for one), and a third confirms the real allowlisted
URL passes cleanly.

## Skeptical-reviewer paragraph

This proves configured-link inclusion and allowlist rejection on the
**fixture** path only — it does not prove live booking end-to-end (no
real Google appointment-schedule URL exists yet; the sim `.example`
domain is deliberately unmistakable) and it does not prove LLM-path
prose quality or judgment about whether the live model reliably follows
the Booking Link Boundary section under adversarial pressure — that is
judge territory, out of scope here. The validator's fail-closed
allowlist is the actual safety guarantee regardless of what the LLM
does or doesn't attempt.

## Owner Ask

Mint the real Google Calendar appointment-schedule URL (created by a
human in the Calendar UI — this system never generates one) and set
`ULTRA_CSM_BOOKING_URL` in `~/ultra-csm-live-creds.env`. Once set, the
loader's env override picks it up automatically — no code change
needed. Re-observation needs nothing new: a customer's booked slot lands
as a calendar event the existing calendar ingestion already sees.

## Merge policy

Per kernel v1.1 K11 — verified at report time: `gh api
repos/owieschon/ultra-csm --jq .allow_auto_merge` → `true`; branch
protection on `main` configured with required check `"eval + CSM
scorecard"`. Both conditions met. Note: this harness's own tool-
permission layer has denied every agent-initiated `gh pr merge` attempt
in this session regardless of GitHub-side eligibility (observed on
multiple sibling PRs) — expect the same here; the PR is left open for
the owner to merge manually if that recurs.

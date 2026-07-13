# Program Report 60 - Master Live Build Phase 10: Burner Send Prep Stop

Branch `codex/master-live-phase10` off `origin/main`
(`1c60e9f`, PR #87 merged). This report captures Phase 10 of
`MASTER_LIVE_BUILD.md`: prepare the one burner-scoped pending
`draft_customer_outreach` proposal and stop before the owner-only OA-2
approval.

## Scope

| Area | Change |
| --- | --- |
| Phase 10 prep | Added `scripts/operating/prepare_phase10_send.py` to create/reuse exactly one Phase 10 burner-eligible pending proposal through `ActionGate` |
| Manifest | Writes sanitized out-of-repo manifest to `$HOME/ultra-csm-operating-runs/phase10/phase10_send_manifest.json` |
| Guard checks | Verifies recipient allowlist, consent in the served data plane, payload SHA binding, Gmail env-name readiness, sender allowlist, and idempotent dry-run behavior |
| Owner stop | Manifest records `STOP_OWNER_APPROVAL_REQUIRED` and an owner-only CLI approval template; no approval or send occurred |
| Tests | Added focused coverage for the manifest happy path and missing-Gmail-env fail-closed path |

## Definition Of Done

| Gate | Receipt |
| --- | --- |
| Initial baseline | `make eval` before edits -> `793 passed, 1 skipped, 1 warning`; both Slot B gold checks current |
| Final eval | `make eval` after edits -> `795 passed, 1 skipped, 1 warning`; both Slot B gold checks current |
| Focused tests | `pytest tests/test_phase10_send_prep.py -q` -> `2 passed` |
| Focused lint | `ruff check scripts/operating/prepare_phase10_send.py tests/test_phase10_send_prep.py` -> `All checks passed!` |
| Manifest generated | Prep script returned `guards_passed=true`, `gmail_send_performed=false`, proposal `241762ea-c0c6-4535-b04d-633140f9bc9b` |
| API visibility | API booted against persistent DB; `/proposals` returned `pending_count 1` and `phase10_visible True` for the Phase 10 proposal |
| Human boundary | No `submit_verdict` call was made; no Gmail send was performed; live-send ledger count stayed `0 -> 0` during dry-run |

## Gate Receipts

Baseline:

```text
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make eval
793 passed, 1 skipped, 1 warning in 134.19s (0:02:14)
eval/gold/slot_b_quality_status.json is current
eval/gold/slot_b_quality_hard_status.json is current
```

Final full eval:

```text
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make eval
795 passed, 1 skipped, 1 warning in 129.63s (0:02:09)
eval/gold/slot_b_quality_status.json is current
eval/gold/slot_b_quality_hard_status.json is current
```

Focused checks:

```text
.venv/bin/python -m pytest tests/test_phase10_send_prep.py -q
2 passed in 0.97s

.venv/bin/python -m ruff check scripts/operating/prepare_phase10_send.py tests/test_phase10_send_prep.py
All checks passed!
```

Manifest prep:

```text
PYTHONPATH=src:. .venv/bin/python scripts/operating/prepare_phase10_send.py
{
  "gmail_send_performed": false,
  "guards_passed": true,
  "manifest": "$HOME/ultra-csm-operating-runs/phase10/phase10_send_manifest.json",
  "owner_action": "OA-2",
  "payload_sha256": "065c48c96d0cee6aab4896f0f3a9103e863393f2109dc4eea5df5dcd2af4c232",
  "proposal_id": "241762ea-c0c6-4535-b04d-633140f9bc9b",
  "status": "STOP_OWNER_APPROVAL_REQUIRED"
}
```

Manifest guard summary:

```text
status STOP_OWNER_APPROVAL_REQUIRED
proposal_id 241762ea-c0c6-4535-b04d-633140f9bc9b
payload_sha256 065c48c96d0cee6aab4896f0f3a9103e863393f2109dc4eea5df5dcd2af4c232
contact_consent_in_served_data_plane True
data_plane_mode fixture
dry_run_receipt {'proposal_id': '241762ea-c0c6-4535-b04d-633140f9bc9b', 'committed': True, 'dry_run': True, 'target': 'gmail:send', 'payload_sha256': '065c48c96d0cee6aab4896f0f3a9103e863393f2109dc4eea5df5dcd2af4c232'}
ledger_send_count_before 0
ledger_send_count_after 0
recipient_allowlisted True
sender_matches_allowlist True
unique_pending_phase10_allowlisted_candidate True
```

API visibility:

```text
pending_count 1
phase10_visible True
proposal_id 241762ea-c0c6-4535-b04d-633140f9bc9b
action draft_customer_outreach
status pending
```

## Owner Stop

STOP at OA-2 is the expected Phase 10 outcome at this point. The pending
proposal and manifest are ready, but the approval must be cast by the owner with
a human token accepted by `ULTRA_CSM_API_TOKENS`. The build runner must not run the
approval command.

The manifest includes the owner-only approval template:

```text
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli proposals approve 241762ea-c0c6-4535-b04d-633140f9bc9b --reason 'Owner OA-2 approval for Phase 10 burner send' --api-token "$ULTRA_CSM_API_TOKEN" --api-url http://127.0.0.1:8000
```

Server-side precondition: run the API with the persistent DB env and
`ULTRA_CSM_API_TOKENS` loaded. Client-side precondition: set
`ULTRA_CSM_API_TOKEN` to the owner token value. Do not put token values in chat,
logs, commits, or PR bodies.

## IF/THEN Branches

1. IF a Phase 10 pending candidate already exists, THEN the prep script reuses
   it instead of creating another.
2. IF zero candidates exist, THEN the prep script creates one through
   `ActionGate` and records the contact consent ref before proposing.
3. IF more than one Phase 10 allowlisted candidate exists, THEN the prep fails
   closed rather than selecting one arbitrarily.
4. IF Gmail committer env names are missing, THEN the prep fails before writing
   a successful manifest.
5. IF OA-2 is not cast, THEN the correct state is a pending proposal plus a
   manifest with `STOP_OWNER_APPROVAL_REQUIRED`; no send is attempted.

## Skeptical Reviewer Paragraph

This phase proves the pre-send side of the closed loop: a real persistent
governance proposal exists, the API can see it, the recipient is constrained to
the hard-coded burner allowlist, consent and payload hash checks pass, and the
live Gmail committer's dry-run path leaves live send count unchanged. It does
not claim the customer-facing loop is complete. No human verdict has been
recorded and no Gmail message has been sent; that is deliberately blocked on
OA-2 because self-approval would invalidate the product guarantee.

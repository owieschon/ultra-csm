# Program Report 57 — Master Live Build Phase 7: Live Served Data

Branch `codex/master-live-phase7` off `origin/main`
(`6db5dd7`, PR #84 merged). This report captures Phase 7 of
`MASTER_LIVE_BUILD.md`: API/MCP serving can now select a live-backed
CustomerDataPlane, derive health from raw signals, keep fixture fallback, and
render the live book in the browser.

## Scope

| Area | Change |
| --- | --- |
| Data-plane selector | Added `ULTRA_CSM_DATA_PLANE_MODE=live` selection with fixture default/fallback when live is not requested |
| Salesforce | Live mode reads standard CRM Account/Contact/Case/Opportunity fields from the granted Salesforce org and filters unrelated tenant custom-field suggestions out of the serving freeze |
| Rocketlane | Live mode reads Rocketlane projects/tasks, tolerates the trial org's unavailable phases endpoint, and reports `live_partial` instead of fabricating phase evidence |
| Gmail/comms | Gmail is surfaced as configured/not-instrumented unless a live thread tag is provided; persisted comms remain owner-confirmed and are disabled for non-UUID Salesforce ids rather than querying an incompatible Postgres FK |
| Derived health | CS company, health, CTAs, success plans, adoption, entitlements, usage, and TTV surfaces derive from raw CRM/onboarding/comms signals instead of a CS-platform score |
| API/MCP boot | API and MCP now construct their served data plane through the selector; `/health` exposes source posture and `/accounts/{id}/derived-health` exposes the derived health read |
| Standing job | `comms_mapping.run_confirmed_comms_ingest(...)` is the reusable owner-gated job body behind `POST /comms/ingest` |
| UI | The ops surface waits for `/health`; when the backend is live it omits `?day=...`, locks the day scrubber, and renders the served live book/queue |

## Gate Receipts

Focused Python tests:

```text
pytest tests/test_live_facade.py tests/test_api.py::TestHealthEndpoint tests/test_api.py::TestAccountDetailEndpoint tests/test_comms_ingest_endpoint.py -q
9 passed in 1.99s
```

Fake live selector:

```text
pytest tests/test_live_facade.py -q
4 passed in 0.07s
```

UI gates:

```text
npm run lint
0 errors, 6 existing React hook warnings

npm run build
Compiled successfully
```

Full eval:

```text
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 make eval
784 passed, 1 skipped, 1 warning in 132.73s (0:02:12)
eval/gold/slot_b_quality_status.json is current
eval/gold/slot_b_quality_hard_status.json is current
```

## Live Verification Receipts

Live API boot:

```text
ULTRA_CSM_DATA_PLANE_MODE=live ULTRA_CSM_DEMO_NOAUTH=1 ... uvicorn ultra_csm.api:app
data_plane_mode=live
health_source=derived_raw_signals
```

`GET /health`:

```json
{
  "accounts_loaded": 54,
  "data_plane_mode": "live",
  "data_plane_sources": {
    "salesforce": "live",
    "rocketlane": "live_partial",
    "gmail": "configured_not_instrumented"
  },
  "health_source": "derived_raw_signals"
}
```

`GET /accounts/{first_live_salesforce_id}/derived-health`:

```json
{
  "score": 88.0,
  "band": "green",
  "drivers": [
    "crm_state",
    "rocketlane_not_instrumented",
    "comms_not_instrumented"
  ],
  "health_source": "derived_raw_signals",
  "data_plane_mode": "live"
}
```

Browser verification against `http://localhost:3000/ui/`:

```text
Book: 54 accounts, live, LIVE, United Oil & Gas Corp., sForce
Queue: 54 accounts, Needs your decision 0, Covered -- no action 53, no error
```

## IF/THEN Branches

1. IF live mode is not explicitly requested, THEN API/MCP boot the existing
   fixture data plane and full eval remains green.
2. IF live mode is requested without Salesforce credentials, THEN boot fails
   closed with missing env-var names only.
3. IF Salesforce discovery sees unrelated tenant custom fields, THEN the
   serving facade ignores those suggestions and freezes only the standard CRM
   fields required for Account/Contact/Case/Opportunity reads.
4. IF Rocketlane phases are unavailable but projects/tasks are readable, THEN
   source posture is `live_partial` and no phase/TTV evidence is invented.
5. IF live Salesforce account ids are non-UUID strings, THEN Postgres-backed
   comms reads are disabled for those accounts and health reports
   `comms_not_instrumented`.

## Skeptical Reviewer Paragraph

This phase proves the operations surface can serve and render a real connected
Salesforce book with live-derived health and honest source posture. It does not
claim a production customer deployment, production retention outcomes, or a
fully joined Rocketlane/Gmail evidence graph. Rocketlane is partially live in
the current trial org, Gmail is configured but not account-thread instrumented
without a tag, and no customer send or verdict approval was performed.

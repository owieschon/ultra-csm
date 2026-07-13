# Program Report 67 - MASTER_LIVE_BUILD Phase 16 Hosted Read-Only Demo

Phase 16 is the optional distribution layer after owner opt-in. It adds a Vercel-ready static demo that serves the existing ops UI and a committed read-only JSON fixture API. No secrets, live credentials, serverless write routes, or customer-facing sends are included.

## DoD Evidence

| Area | Evidence |
| --- | --- |
| Static Vercel config | `vercel.json` builds `ui/out`, redirects `/` to `/ui/`, and rewrites `/ui/:path*` into the static export. |
| Read-only API fixtures | `scripts/export_hosted_readonly_demo.py` exports JSON into `ui/public/demo-api/` from the local fixture-backed API. |
| No hosted writes | `ui/lib/api.ts` maps hosted mode to static fixture reads and rejects mutating routes with `READONLY_DEMO`; the manifest records `write_routes_exported=false`. |
| UI action guard | `ActionRail` disables approve, edit, and deny in hosted read-only mode; comms mapping confirm buttons are disabled. |
| Static demo build | `make hosted-readonly-demo` exports fixtures, runs UI lint, and builds Next static export with `NEXT_PUBLIC_UCSM_READONLY_DEMO=1`. |
| Regression | `tests/test_hosted_readonly_demo.py` verifies Vercel is static, core fixtures exist, and no write routes are exported. |

## Fixture Manifest

```json
{
  "account_count": 181,
  "day": 140,
  "exported_account_detail_count": 11,
  "mode": "hosted-readonly",
  "proposal_count": 11,
  "work_item_count": 12,
  "write_routes_exported": false
}
```

## IF/THEN Branches

1. IF the existing UI calls `POST /sweep` and creates proposals, THEN the hosted demo cannot point at the live API. It must read a committed static sweep fixture instead.
2. IF a user clicks decision controls in the hosted demo, THEN buttons are disabled and the API wrapper rejects mutating calls.
3. IF the existing Next export assumes `/ui` because FastAPI mounts `ui/out` there, THEN Vercel must redirect `/` to `/ui/` and rewrite `/ui/:path*` back to the export root.

## Owner Asks

None for the code path. Publishing to a production Vercel domain can happen through the existing Vercel project once this PR lands.

## Skeptical Reviewer

This phase does not host a live API. That is intentional: the deliverable is a safe public demo link backed by committed fixture data. It proves distribution and no-write posture, not live connector access, owner approval, live Sentry delivery, or production outcomes.

## Receipts

- Config: `vercel.json`.
- Exporter: `scripts/export_hosted_readonly_demo.py`.
- Static fixtures: `ui/public/demo-api/`.
- Contract test: `tests/test_hosted_readonly_demo.py`.

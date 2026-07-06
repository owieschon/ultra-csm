# Program Report 2

## DoD Evidence

| Phase | Result | Evidence |
| --- | --- | --- |
| 0 | Complete | `origin/main` at `b2b2b6f` contains PR #9. After `make setup`, `LC_ALL=en_US.UTF-8 make doctor` passed. Baseline `make eval` reported `380 passed, 1 warning`; `make lint` reported `All checks passed!`; `make hygiene` exited 0; `git diff --check` exited 0. Credential inventory found the env file present but Salesforce, Gmail, and `ANTHROPIC_API_KEY` keys empty/missing. |
| 1 | Buildable path complete | Added a read-only Salesforce SOQL fetch path with refresh-token and direct-token auth, nextRecordsUrl pagination, row caps, mapped-field-only SOQL, typed CRM contracts, totalSize/fetched coverage, identity-audit foil, fixtures, `eval/salesforce_simulated_onboarding.py`, and `make salesforce-simulated-onboarding-csm`. Focused tests reported `6 passed`. |
| 2 | Skipped at credential boundary | Salesforce live preflight and one-shot were not run because credentials were missing. `docs/SALESFORCE_ONESHOT_FINDINGS.md` records `live=false`, `one_shot=false`, and `business_data_touched=false`. |
| 3 | Buildable path complete; live placement skipped | Added approved-proposal `render_email_draft`, MCP exposure in operator/relay modes, read-only refusal, and a Gmail `users.drafts.create` committer with fake-transport tests and no Gmail delivery endpoint. Focused tests reported `9 passed`. Gmail live placement was skipped because Gmail credentials were missing. |
| 4 | Skipped at credential boundary | `ANTHROPIC_API_KEY` was missing, so no drift-power judge calls were made and no judge/gold file was edited. |
| 5 | Complete | `make demo` includes Salesforce simulated onboarding and passed. `make status` reported `STATUS.md is current`. README, QUICKSTART, TOUR, findings, and this report document only true claims. Final gates are listed below. |

## IF/THEN Branches Taken

- Salesforce credentials absent -> no `/services/data` live preflight and no business-data SOQL run.
- Gmail credentials absent -> no live Gmail draft creation; fake-transport coverage only.
- `ANTHROPIC_API_KEY` absent -> drift-power experiment skipped; no judge/gold edits.
- No corpus B data-shape failure occurred because no corpus B data request was made.

## Consolidated Owner Ask

1. Salesforce: provide either refresh-token OAuth credentials or a short-lived access token in `~/ultra-csm-live-creds.env`.
2. Gmail: provide OAuth client credentials and a refresh token with `gmail.compose` scope (`ULTRA_CSM_GMAIL_CLIENT_ID`, `ULTRA_CSM_GMAIL_CLIENT_SECRET`, `ULTRA_CSM_GMAIL_REFRESH_TOKEN`, optional `ULTRA_CSM_GMAIL_USER_ID`).
3. Drift-power: provide `ANTHROPIC_API_KEY` when the credentialed judge experiment should run.

## STOP Conditions

No stop-the-line violation fired. The live Salesforce, live Gmail, and drift-power phases stopped at credential boundaries and continued with all buildable work. Salesforce write paths and email delivery paths were not added.

## Skeptical Reviewer Paragraph

A skeptical reviewer should still challenge the absence of the actual Salesforce one-shot, the absence of a real Gmail draft receipt, and the skipped drift-power measurement. This PR proves the read-only and draft-only mechanics with fake transports and deterministic artifacts, but it does not prove live tenant shape, OAuth tenant configuration, mailbox placement, or judge power margins.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make doctor` | All checks passed after worktree `make setup`. |
| `LC_ALL=en_US.UTF-8 make demo` | Passed; included `make salesforce-simulated-onboarding-csm`, which wrote `eval/salesforce_simulated_onboarding.json` with `live_tenant_proven=false` and `truncated=false`. |
| `LC_ALL=en_US.UTF-8 make eval` | `391 passed, 1 warning in 22.07s`. |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0. |
| `git diff --check` | Exited 0. |
| `LC_ALL=en_US.UTF-8 make status` | `STATUS.md is current`. |

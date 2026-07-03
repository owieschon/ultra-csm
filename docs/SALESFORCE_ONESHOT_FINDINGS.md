# Salesforce One-Shot Findings

Claim boundary:

- `live=false`
- `one_shot=false`
- `tenant="not accessed"`
- `business_data_touched=false`

The live Salesforce one-shot did not run in this program because
`/Users/owieschon/ultra-csm-live-creds.env` existed but all checked Salesforce
credential keys were empty or unset:

- `ULTRA_CSM_SALESFORCE_INSTANCE_URL`
- `ULTRA_CSM_SALESFORCE_CLIENT_ID`
- `ULTRA_CSM_SALESFORCE_CLIENT_SECRET`
- `ULTRA_CSM_SALESFORCE_REFRESH_TOKEN`
- `ULTRA_CSM_SALESFORCE_ACCESS_TOKEN`
- `ULTRA_CSM_SALESFORCE_API_VERSION`

No org URL, username, org identifier, token, describe payload, SOQL result, or
business record was read or written. The buildable replacement evidence is the
new Salesforce simulated onboarding vertical, which proves the frozen read-only
path against fake Salesforce-shaped payloads only.

Owner ask for a future one-shot: provide either a refresh-token flow
(`ULTRA_CSM_SALESFORCE_INSTANCE_URL`, `ULTRA_CSM_SALESFORCE_CLIENT_ID`,
`ULTRA_CSM_SALESFORCE_CLIENT_SECRET`, `ULTRA_CSM_SALESFORCE_REFRESH_TOKEN`, optional
`ULTRA_CSM_SALESFORCE_LOGIN_URL`, optional `ULTRA_CSM_SALESFORCE_API_VERSION`) or a
short-lived read-only token
(`ULTRA_CSM_SALESFORCE_INSTANCE_URL`, `ULTRA_CSM_SALESFORCE_ACCESS_TOKEN`, optional
`ULTRA_CSM_SALESFORCE_API_VERSION`).

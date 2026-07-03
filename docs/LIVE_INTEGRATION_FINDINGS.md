# Live Integration Findings — Program 3, Phase 3

Battery matrix for the live conversational-onboarding path
(`ingest_table`/`confirm_book`/`ingest_book`) against corpus B, run over a
live stdio MCP server session. All records were seeded by this program in
Phase 2E (`~/ultra-csm-corpus-runs/seed-2e-20260703/`, tagged `UCSM-P3E`,
create-only). Assertions are exact numbers against the seed ledger's ground
truth — not tolerances. Run artifacts:
`~/ultra-csm-corpus-runs/phase3-live-battery-20260703/`.

## Battery matrix

| Dataset | Path | Typed (Account/Contact/Opp) | FK orphans (Contact/Opp) | Injection markers | Replay deterministic |
| --- | --- | --- | --- | --- | --- |
| D1 volume | `ingest_table`×3 + `confirm_book` | 8 / 16 / 12 (exact) | 0 / 0 (exact) | 0 (exact) | Yes |
| D2 hostile text | `ingest_table`×3 + `confirm_book` | 4 / 6 / 4 (exact) | 0 / 0 (exact) | 14 / 14 (exact) | Yes |
| D3 sparse | `ingest_table`×3 + `confirm_book` | 5 / 8 / 5 (exact) | 0 / 0 (exact) | 0 (exact) | Yes |
| D4 broken joins | `ingest_table`×3 + `confirm_book` | 4 / 4 / 3 (exact) | 4 / 3 (exact) | 0 (exact) | Yes |
| D5 unmapped (Lead) | `ingest_book` | 0 accounts typed (exact) | n/a | n/a | n/a |
| D5 unmapped (Case) | `ingest_book` | 0 accounts typed (exact) | n/a | n/a | n/a |

Every number above is the live response compared against
`ground_truth.json`, authored before any record was created. Zero
mismatches on the final run (`phase3_battery_report.json`: `"problems": []`,
`"ok": true`).

## What each dataset proved

- **D1 (volume):** the relational join holds at 8 accounts / 16 contacts /
  12 opportunities with zero orphans — the FK-join path scales past a
  single-digit book without degrading.
- **D2 (hostile text):** emoji, RTL Arabic, Japanese, embedded quotes/
  backslashes, JSON-lookalike strings, and zero-width characters in `Name`
  all typed correctly with exact counts; the injection sentence appears on
  every one of the 14 records carrying it (4 accounts + 6 contacts + 4
  opportunities) and the marker count matches exactly. The injected text
  never appears anywhere in the `confirm_book` response (asserted by
  substring search on the full serialized payload) — `Description` has no
  internal-field mapping on any of the three contracts, so the content
  never reaches mapped output at all; the marker count is a raw-record scan,
  independent of mapping.
- **D3 (sparse):** every optional field absent (no `Industry`, `Email`,
  `Amount`, `Type`). `CRMAccount.industry` correctly demanded human
  confirmation rather than auto-mapping — zero non-empty rows means zero
  auto-map evidence, and the system asked rather than guessed. All records
  still typed with exact counts.
- **D4 (broken joins):** half of D4's contacts (4/8) and half its
  opportunities (3/6) point at accounts from a different dataset (D1) —
  valid org ids, but outside D4's book when ingested alone. All 7 orphaned
  correctly (4 contact + 3 opportunity), rejected with
  `unresolved_parent_identity`, never attached to a fabricated parent. Zero
  false positives (no D4-internal child was misclassified as orphaned) and
  zero false negatives (no external-parent child slipped through as joined).
- **D5 (unmapped shapes):** Lead and Case have no source contract in this
  connector (`CRMAccount`/`CRMContact`/`CRMOpportunity` only). Relayed
  through the flat `ingest_book` path, zero accounts typed on both — no
  identity field ever auto-mapped (`auto_mapped_identity_count: 0` on both),
  confirming the system does not guess an account out of Lead/Case shapes
  it has no contract for.

## Defect protocol outcome

Zero product defects surfaced by this battery. Two live findings did
surface, both handled without touching `src/`:

1. **Org-native duplicate-detection rule** (documented in
   `SALESFORCE_ONESHOT_FINDINGS.md`): the standard Contact fuzzy-duplicate
   rule blocked bulk same-`FirstName`-similar-`LastName` creates during
   seeding. Fixed by authoring distinct first names — a seeding-time
   workaround, not a product change, since ultra-csm never writes Contact
   records itself.
2. **Driver assumption gap, not a product gap:** the initial battery driver
   hardcoded confirmation answers assuming `Industry` always auto-maps
   (true for D1, where every account has a value). D2/D3/D4 correctly
   demanded human confirmation for `Industry` because those datasets have
   zero non-empty values for it — exactly the auto-map coverage threshold
   (Tier B requires ≥80% non-empty rows) doing its job. The driver was
   fixed to answer any unforeseen question `not_mappable` rather than
   assume; no test, no src file, and no confirmation logic changed.

## Regression trio (same commit as this battery)

| Command | Result |
| --- | --- |
| `make eval` | `418 passed, 1 warning` |
| `make relational-battery-csm` | `hard_ok: true`, `seeds: 20` |
| `make relay-battery-csm` | `passed: 11 / 11` |
| `make demo` | Passed; artifacts byte-unchanged (`git status --short` clean after run) |

## Scope not covered

- **D6 volume-at-scale** (>500-row books, exercising the relay
  `max_records` cap and pagination under real API limits) was deferred —
  it requires populated `~/ultra-csm-live-creds.env` for REST-composite
  batch creation; the file is currently an empty template. Flagged as an
  open owner ask, not silently dropped.
- Update/delete paths were not exercised against corpus B; the program's
  standing rule is create-only writes against this org.

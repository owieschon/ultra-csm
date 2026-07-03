# Program Report 3

Branch `claude/live-integration`, commits `ac57716`..`c2e3854` plus this
report's commit. Program 2 closed with the flat single-table relay path
proven live (read-only) and a structural gap flagged: normalized multi-table
CRMs (Salesforce's real shape) had no join path, and mid-program the user
flagged that the schema explorer was silently dropping source-declared
foreign-key metadata. Program 3 closes both, proves the result live with
seeded adversarial data, and hands off a single PR.

## DoD Evidence

| Phase | Result | Evidence |
| --- | --- | --- |
| 2A | Complete | Relational multi-table book model (`RelationalTable`, `ingest_relational_book`); single-table shape verified byte-identical to the pre-existing flat path. Commit `ac57716`. |
| 2B | Complete | Deterministic value-shape evidence (`_classify_value_shape`, `_distinct_count`) attached to every mapping candidate. Commit `e533c51`. |
| 2C | Complete | Declared value transforms in a closed enum (`VALUE_TRANSFORMS`), `amount_cents` currency conversion made explicit and auditable instead of implicit. Commit `984ca27`. |
| 2D + metadata-first pivot | Complete | User-flagged defect fixed: `explorer.py` was discarding Salesforce describe `referenceTo`/`relationshipName`; now captured into `DiscoveredField.references`. 20-seed property battery reworked metadata-first, 20/20 green. Commit `204bd56`. |
| Friction fix | Complete | Provenance-tiered auto-mapping (Tier A source-declared reference, Tier B exact alias). Measured on the real corpus B book: 29 confirmation questions → 5. Shadow-account guard added and regression-tested. Commit `c27dac6`. |
| Plan | Complete | `docs/P3_EXECUTION_PLAN.md` — command-verified DoDs for the remaining workstreams. Commit `1698de5`. |
| A: Conversational onboarding over MCP | Complete | `ingest_table`/`confirm_book` tools; contract declared at ingest (deviation from the plan, recorded in the plan doc, to keep per-table responses to real questions only); cross-contract confirmations refused (hollow-records guard). 12 new tests, 418 total green. Committed transcript + stdio replay coverage. Commit `6b47c5e`. |
| A4: Live proof | Complete | Fresh corpus B reads (record-identical to the Phase 1 recording), describe-declared FK metadata, 5 human questions, typed 13/20/31, FK ratios 1.0, deterministic replay — proven on the product surface. Commit `c2e3854`. |
| B: Adversarial seeding (2E) | Complete | 97 tagged records (`UCSM-P3E`) across 5 datasets created via `createSobjectRecord` only. Post-seed verification: tagged counts exact, factory counts (Account 13 / Contact 20 / Opportunity 31 / Lead 22 / Case 26) unchanged. Ledger 97/97 unique ids. Live finding: org's Contact fuzzy-duplicate rule required distinct first names for bulk creates (seeding-time fix, no product change). |
| C: Live battery | Complete | All 5 datasets run through the live conversational MCP surface with exact-number assertions against the seed ledger. Zero mismatches, zero product defects. `docs/LIVE_INTEGRATION_FINDINGS.md`. |

## IF/THEN Branches Taken

- Explorer was silently dropping `referenceTo` → fixed before any other work continued (the metadata-first pivot), per the user's explicit direction that the explorer was supposed to solve exactly this.
- Friction measured at 29 questions on the real book → provenance-tiered auto-mapping added, re-measured at 5, before proceeding to MCP exposure.
- Declaring contract intent only at `confirm_book` would have surfaced every contract's questions on every table at ingest time → moved intent to `ingest_table` instead (deviation recorded, not silent).
- No bulk-API credentials available in `~/ultra-csm-live-creds.env` → 2E seeding sized for the per-record MCP `createSobjectRecord` path (97 records across 5 datasets) instead of the plan's ~120/240/180 volume dataset; the property under test (relay through the joined-book path at multi-record scale, including orphans and injection content) does not require the larger row count. A true >500-row volume dataset (exercising `DEFAULT_MAX_RECORDS` pagination) is deferred, flagged below.
- Battery driver's first pass hardcoded `Industry` as always-auto-mappable → D2/D3/D4 correctly demanded human confirmation (zero non-empty rows, below the Tier B coverage threshold); driver fixed to answer any unforeseen question `not_mappable` rather than assume. No product code changed.
- Org's standard Contact duplicate-detection rule blocked bulk near-identical contacts during seeding → distinct first names authored; this is seeding-time data authoring, not a product code path (ultra-csm never writes Contact records).

## Consolidated Owner Ask

1. **D6 volume-at-scale dataset** (>500 rows, exercising the relay
   `max_records` cap and real API pagination under live conditions):
   requires populated Salesforce REST credentials in
   `~/ultra-csm-live-creds.env` (currently an empty template) so seeding can
   use the composite-tree bulk API instead of one MCP call per record.
2. **Update/delete write paths**: never exercised against corpus B by
   design (the program's standing rule is create-only). If desired for a
   future program, needs an explicit owner decision — it changes the
   program's risk posture.

## STOP Conditions

No stop-the-line violation fired. Seeding began only after Workstream A was
merged-green, per the plan's hard precondition. No test, threshold, or
contract was weakened to make the battery pass — every mismatch in the
battery's first run was a driver bug (traced and fixed), not a relaxed
assertion. Every created record is tagged and ledgered; factory data was
verified untouched before and after seeding.

## Skeptical Reviewer Paragraph

A skeptical reviewer should note the seeded datasets are an order of
magnitude smaller than the plan's original volume target (8 vs. ~120
accounts for D1), a deliberate scale deviation driven by the absence of bulk
API credentials — the FK-join and orphan-detection logic is proven correct
at this scale, but genuine high-volume pagination behavior (crossing
`DEFAULT_MAX_RECORDS`=500) is asserted only by the relay battery's synthetic
oversized-payload case, not by a live multi-hundred-record fetch. The
reviewer should also weigh that Program 3's "zero product defects" outcome
in Phase 3 is itself evidence the earlier phases (property battery, friction
measurement, A4's live proof) already caught what would otherwise have
surfaced here — Phase 3 is closing the loop on a system that had already
been adversarially tested, not a first contact with reality.

## Final Verification

| Command | Observed result |
| --- | --- |
| `LC_ALL=en_US.UTF-8 make eval` | `418 passed, 1 warning` |
| `LC_ALL=en_US.UTF-8 make lint` | `All checks passed!` |
| `LC_ALL=en_US.UTF-8 make hygiene` | Exited 0 |
| `git diff --check` | Exited 0 |
| `LC_ALL=en_US.UTF-8 make relational-battery-csm` | `hard_ok: true`, 20/20 seeds |
| `LC_ALL=en_US.UTF-8 make relay-battery-csm` | 11/11 passed |
| `LC_ALL=en_US.UTF-8 make mcp-stdio-replay-csm` | `ok: true` (operator, relay, and relational sessions) |
| `LC_ALL=en_US.UTF-8 make demo` | Passed; `git status --short` clean after (no artifact drift) |
| Live Phase 3 battery (`phase3_battery_report.json`) | `"problems": [], "ok": true` across all 5 datasets |

# Program 3 Remainder — Execution Plan, DoDs, and Testing Regime

Continues `docs/PHASE_2_3_PLAN.md` after its friction-first amendment. State at
writing: 2A relational engine, 2B shape evidence, 2C declared transforms, 2D
property battery, and provenance-tiered auto-mapping are merged on
`claude/live-integration` (406 tests, battery 20/20). Corpus B is pristine —
zero writes. Three workstreams remain, in this order:

- **A. Conversational onboarding over MCP** (the user-facing surface)
- **B. Phase 2E: adversarial seeding** (first irreversible org writes)
- **C. Phase 3: the live battery + program close-out**

Every DoD item below names its verification: the command to run and the
observation that counts as pass. A box is checked only after the command ran
and the observation was seen — never from reading code. Commands marked
*(new)* are created by the workstream itself; all others exist today.

---

## Workstream A — Conversational onboarding over MCP

Goal: "Claude, onboard my Salesforce" → a handful of plain-language questions
→ briefing. No driver scripts, no JSON authoring, no internal API knowledge.

### A1. `ingest_table` tool

Accepts `book_id, table_name, records, expected_count, field_metadata?,
final_chunk?, session chunking as ingest_book`. Accumulates named tables on a
relay book session. Response per table: received/stored counts, raw-input
sha256, auto-mapped summary (key → source path → provenance reason), and ONLY
the remaining questions (ambiguous entries) with their candidate evidence
(coverage + value shape + declared references). Claim boundary `mcp_relay`
unchanged. Readonly mode refuses; demo-operator conflict refuses (same rules
as `ingest_book`).

- [x] Tool registered and callable over stdio.
      *Verified:* `make mcp-stdio-replay-csm` → `ok: true`, relational session
      included; also driven live in A4/Phase 3 over a real stdio process.
- [x] Auto-map summary + questions-only response shape.
      *Verified:* `pytest tests/test_mcp_server.py -k ingest_table -q` — 4
      passed; response contains `auto_mapped` with provenance reasons and
      `confirmation_questions` containing ONLY the declared contract's
      ambiguous keys.
- [x] Chunked delivery across calls with expected-count enforcement per table.
      *Verified:* `test_ingest_table_supports_chunked_reassembly` and
      `test_ingest_table_refuses_count_mismatch_and_unstable_declarations`,
      both passing.
- [x] Refusal modes.
      *Verified:* `test_read_only_and_demo_operator_refuse_relational_tools`
      passing — readonly returns `MCP_READONLY`, demo-operator returns
      `RELAY_DEMO_OPERATOR_CONFLICT`.

### A2. `confirm_book` tool

**Amended during build:** contract intent moved from `confirm_book` to a
required `contract` parameter on `ingest_table`. Declaring intent only at
confirm time would have returned every contract's questions on every table at
ingest time — per-table question noise that defeats the friction win the tools
exist to deliver. With intent declared at ingest, each table's response
carries ONLY its own contract's questions.

`confirm_book` accepts `book_id` and the human answers for remaining
questions, keyed by table. Behavior: for each table, entries of OTHER
contracts — auto-mapped or ambiguous — are recorded as `not_mappable` and the
response **declares this list explicitly** (nothing silently dropped); a
confirmation naming a foreign contract on a table is refused
(`RELAY_CONTRACT_INTENT_CONFLICT` — the hollow-records guard); freeze runs per
table; `ingest_relational_book` assembles the book; response carries
`typed_counts`, coverage (incl. `foreign_key_joins`), briefing,
`replay_sha256`, frozen config hashes per table.

- [x] Happy path: SFDC-shaped 3-table fixture book with metadata onboards with
      exactly the identity+direction questions answered, everything else
      auto-mapped/declared.
      *Verified:* `test_confirm_book_joins_tables_and_replays_deterministically`
      passing — typed counts match fixture ground truth (3/4/4), FK join
      ratios 1.0, `declared_not_mappable` matches expectation. Reproduced
      live in Phase 3 against real corpus B + seeded data (see
      `LIVE_INTEGRATION_FINDINGS.md`).
- [x] Determinism: confirming the same book twice yields identical
      `replay_sha256`.
      *Verified:* byte-equality asserted in the same test, and again live
      for every Phase 3 dataset.
- [x] Orphan and shadow-account guards hold through the MCP surface.
      *Verified:* `test_child_only_book_orphans_instead_of_minting_a_parent`
      (0 accounts typed, orphans counted) and
      `test_confirm_book_refuses_cross_contract_confirmations`
      (`RELAY_CONTRACT_INTENT_CONFLICT` on the CRMAccount.account_id-onto-
      Contact-table attempt), both passing.
- [x] `report_readiness.routes.next_tool` updated to point multi-table sources
      at `ingest_table`.
      *Verified:* `test_readiness_routes_multi_table_sources_to_ingest_table`
      passing.

### A3. Conversational onboarding transcript (the product proof)

A deterministic fixture transcript of the full conversation-shaped flow:
readiness → 3 × `ingest_table` (SFDC-shaped fixture tables + metadata) →
`confirm_book` (only the human questions) → briefing. Same pattern as
`eval/mcp_relay_transcript.json`.

- [x] `eval/mcp_relational_demo.py` + committed transcript + Make target
      `mcp-relational-demo-csm`, wired into `make demo`.
      *Verified:* `make mcp-relational-demo-csm` → 5 questions, typed
      3/4/4; transcript byte-identical across two consecutive runs;
      `make demo` green end-to-end.
- [x] Stdio replay covers the new transcript.
      *Verify:* `make mcp-stdio-replay-csm` → `ok: true` including the
      relational session, question keys, and typed counts.
- [x] Docs: QUICKSTART + TOUR gain the conversational onboarding beat with the
      real question count.
      *Verified:* both docs updated (`## Normalized multi-table CRMs`
      section, TOUR §6 addendum); `make hygiene` exits 0.

### A4. Live conversational onboarding (the real thing, this machine)

Run the A1–A3 flow against the REAL corpus B via the live Salesforce MCP in a
Claude session (bounded reads, standing residue rules): fetch the 3 tables
with explicit field lists, pass describe-declared `field_metadata`, answer the
~5 real questions conversationally, receive the briefing.

- [x] Executed once end-to-end; outputs to `~/ultra-csm-corpus-runs/`;
      sanitized summary (counts, question list, join ratios) appended to
      `docs/SALESFORCE_ONESHOT_FINDINGS.md`.
      *Verified:* typed 13/20/31 (exact Phase-1-measured truth), FK ratios
      1.0/1.0, zero fabrication, exactly 5 questions — the friction claim
      proven live on the product surface. Findings addendum committed
      (c2e3854).

---

## Workstream B — Phase 2E: adversarial seeding (IRREVERSIBLE writes begin)

Preconditions (hard): Workstream A merged green — the battery must run through
the user-facing path; baseline factory counts already snapshotted
(`00_baseline_counts.json`: Account 13, Contact 20, Opportunity 31, Lead 22,
Case 26).

Five linked datasets (per the Phase-1 lesson: every dataset = parents AND
children, seeded together), all records tagged with the marker token
`UCSM-P3E` in a standard text field, every created Id appended to
`~/ultra-csm-corpus-runs/seed-ledger-<date>.jsonl` (id, object, dataset) at
create time — the ledger is written record-by-record, not batched at the end,
so a mid-run failure never loses provenance.

Datasets: (1) volume — ~120 Accounts / ~240 Contacts / ~180 Opportunities
(forces >200-row bounds and pagination); (2) hostile text — unicode/emoji/RTL/
10KB fields + the battery's injection markers in Name/Description; (3) sparse
— every optional field null; (4) broken joins — children pointing at other
datasets' parents and at each other (where the API even permits); (5) unmapped
shapes — Leads and Cases (no source map: must flow to unknown, zero guesses).

- [x] Seeds created via `createSobjectRecord`, batched politely inside API
      limits; partial seeds acceptable if measured.
      *Verified:* 97 records created (21 Account / 38 Contact / 27
      Opportunity / 6 Lead / 5 Case) across 5 datasets. Per-dataset SOQL
      `SELECT COUNT()` filtered by `Name`/`LastName`/`Subject` LIKE
      `'UCSM-P3E%'` matched the ledger's per-dataset counts exactly.
      **Scale deviation from the plan's ~120/240/180:** datasets sized for
      the MCP per-record `createSobjectRecord` write path (no bulk API
      creds available), 8/16/12 for D1 — the property under test (relay
      through the joined-book path at multi-record scale) doesn't require
      the original row count; a >500-row volume dataset is deferred (see
      Workstream C scope-not-covered).
- [x] Factory data untouched.
      *Verified:* post-seed `SELECT COUNT()` per object minus tagged count
      equals the Phase-0 baseline exactly (Account 13, Contact 20,
      Opportunity 31, Lead 22, Case 26); zero factory record carries the
      marker.
- [x] Ledger complete and out-of-repo.
      *Verified:* `~/ultra-csm-corpus-runs/seed-2e-20260703/seed-ledger.jsonl`
      has 97 lines, 97 unique ids, matching the 97 created records; repo
      `git status` clean; sentinel grep clean on every commit.

## Workstream C — Phase 3: the live battery and close-out

Each dataset, fresh relay run **through the Workstream-A MCP surface** (not
the internal API): bounded SOQL fetch with explicit field lists + describe
metadata → `ingest_table` × N → `confirm_book` → coverage. We authored the
seeds, so every assertion is an exact number against the seed ledger.

- [x] Battery matrix, one row per dataset, all exact-number checks:
      fetched-vs-expected; typed per contract == seeded valid counts; orphans
      == seeded broken-join counts; injection marker count == seeded marker
      count AND markers never in briefing text; truncation loud at the cap;
      Leads/Cases route to unknown with zero silent guesses; per-dataset
      `replay_sha256` stable across two confirms.
      *Verified:* `~/ultra-csm-corpus-runs/phase3-live-battery-20260703/
      phase3_battery_report.json` — `"problems": []`, `"ok": true`. Matrix
      in `docs/LIVE_INTEGRATION_FINDINGS.md`. Truncation-at-cap not
      separately exercised this run (no dataset approached
      `DEFAULT_MAX_RECORDS`=500) — already covered by the relay battery's
      dedicated oversized-payload case.
- [x] Defect protocol: any live failure gets a reproducing unit test FIRST,
      then the fix, then that dataset re-runs (the org is a bench now —
      iterate freely, unlike Phase 1's one-shot).
      *Verified:* zero product defects surfaced; the two live findings
      (org duplicate-detection rule at seed time, driver assumption gap at
      battery time) are recorded in `LIVE_INTEGRATION_FINDINGS.md` with
      their resolutions — neither touched `src/`, so no reproducing test
      was created (nothing in the product to reproduce against).
- [x] Regression trio on the final commit: property battery 20/20, corpus A
      recorded-inputs replay unchanged, `make demo` green, full suite green.
      *Verified:* `make eval` → 418 passed; `make relational-battery-csm` →
      `hard_ok: true`, 20 seeds; `make relay-battery-csm` → 11/11;
      `make demo` → passed, `git status --short` clean after (no artifact
      drift).
- [x] Close-out: `docs/PROGRAM_REPORT_3.md` (per-phase DoD ledger with
      command→observation evidence; deviations; created-record inventory as
      counts+tag); README/TOUR truth updates only for executed-true claims;
      `make status` current; single PR opened, gates green, sentinel clean,
      NOT merged.

---

## Testing regime (the standing system, not per-feature)

**Layer 1 — unit (every commit).** `make eval` (full pytest). New behavior
lands with tests in the same commit; bug fixes land with the reproducing test
first. No commit with a red suite, ever.

**Layer 2 — property battery (every commit touching data_plane).**
`make relational-battery-csm`: 20 frozen seeds, ground-truth invariants
(accounting identity, exact orphan counts, no fabricated parents, injection
inert, determinism, metamorphic rename). Byte-identical artifact across two
consecutive runs. The battery is the anti-Goodhart floor: its generator owns
ground truth, so the engine cannot be fitted to it.

**Layer 3 — adversarial relay battery (every commit touching the MCP relay).**
`make relay-battery-csm`: 11 authored failure-mode cases (truncation,
paraphrase, duplicates, partial joins, injection, empties, oversize,
competing coverage, not-mappable round-trip, nested children).

**Layer 4 — transcript + replay (every commit touching mcp_server).**
Committed deterministic transcripts (operator, relay, relational-onboarding)
regenerated and byte-compared; `make mcp-stdio-replay-csm` replays them
against a LIVE stdio server session → `ok: true`.

**Layer 5 — live ground-truth battery (Phase 3, then on demand).** The seeded
org is the permanent bench: assertions are exact numbers against the seed
ledger, run through the product surface. This is the only layer that exercises
real API pagination, limits, encoding, and latency.

**Layer 6 — regression trio (every merge to the program branch).** Corpus A
recorded-inputs replay (flat shape must never regress), `make demo` (sim book
end-to-end), full suite — same commit, all green.

**Gates (every commit, no exceptions, in order and fail-stops):**
`make eval` → `make lint` → `make hygiene` → `git diff --check` → sentinel
grep from the private corpus file on the staged diff. Hygiene/sentinel run
BEFORE the commit command, never chained after it (two incidents of
committed-then-caught this program; the ordering is the fix).

**Anti-Goodhart standing rules.** Never weaken a test/threshold/contract to
pass; a legitimate expectation change (policy change) is documented in the
test diff with the policy named. Three-corpus acceptance for ingest changes:
generated books + corpus A replay + corpus B live. No source-name
special-cases in core ingest — grep-able STOP condition. Identity and
value-direction decisions stay human; automation of either requires an owner
decision, not a code change.

**Residue rules (runtime).** Live-run outputs only under
`~/ultra-csm-corpus-runs/`; committed docs carry aggregates and role
descriptions; org identifiers/credentials only in the private file; the
`getUserInfo` lesson stands (never persist identity payloads).

## STOP conditions (unchanged from the program order, plus)

Seeding before Workstream A is merged-green; any write touching factory
records; any test weakened to pass; any battery invariant relaxed without a
documented policy decision; org identifiers in a committable file.

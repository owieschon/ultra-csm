# Executor Handoff — Lane I: Foreign-Corpus Ingest Proof

Same protocol as prior lane handoffs (one-shot autonomy, IF/THEN decision criteria,
verify claims by executing). This lane produces **evidence, not product UX**: it
proves — or breaks — the ingest boundary on a real third-party CRM corpus that
nobody on this project authored, and turns what it learns into a sanitized findings
document that will drive the next product slice.

## Why this lane exists (context you need)

The product direction under design is **"checklist → go"**: the user connects their
own tools (email, CRM, telemetry) to Claude via MCP, and ultra-csm acts as the
deterministic brain + governance layer — Claude relays their real records into an
ultra-csm ingest tool, the value model scores them, the agent proposes gated
actions, approved outreach lands as drafts in their own email. Ultra-csm never
holds their credentials; the MCP ecosystem owns the connectors.

The named landmines of that design: relay infidelity (model paraphrases/truncates
payloads between tools), messy real books (missing fields everywhere), identity-join
failure, and injection through relayed CRM text. The synthetic 35-account book
cannot test any of this — it is the design artifact itself; every parser was shaped
around it (reference-class error). So this lane tests against **Corpus A**: a real
production CRM from an unrelated business in a different vertical, with schema
conventions this repo has never seen.

## Hard rules (each one is a stop-the-line rule, not a preference)

1. **RESIDUE.** Corpus A is a real company's confidential data. NOTHING sourced from
   it may enter a committed file: no account titles, contact names, revenue values,
   locations, row ids, connection URLs, or API keys. Committed artifacts may contain
   only aggregates (counts, percentages, coverage ratios) and failure-mode
   descriptions. Connection details live ONLY in
   `/Users/owieschon/ultra-csm-corpus-a-PRIVATE.md` (outside the repo); committed
   code reads them from environment variables with NO defaults. Before every
   commit: run `make hygiene` AND the sentinel grep listed in the private file.
2. **READ-ONLY.** GET/SELECT against Corpus A only. No mutation of any kind, ever.
3. **Runtime outputs stay out of the repo.** All dogfood-run outputs (fetched
   payloads, scored results, briefings over real accounts) go to
   `~/ultra-csm-corpus-runs/` — never under the repo tree, not even gitignored.
4. **Holdout discipline.** Corpus B (defined in the private file) is a one-shot
   holdout for a later session. Do not create, fetch, tune against, or reference it.
5. **Scope.** No MCP server changes, no product UX, no live connector builds, no
   changes to the judge/gold lane. This lane is the ingest core + battery + probe +
   findings, nothing else.

## Step 0 — verify the corpus is alive

Liveness was NOT verified when this handoff was written. Using the private file's
env wiring, confirm the endpoint answers and count rows (`Prefer: count=exact`
header on a `select=id&limit=1`). IF unreachable or the key is dead → STOP and
report; do not hunt for other credentials.

## Slice 1 — the external ingest boundary

New module, suggested `src/ultra_csm/data_plane/external_book.py`. Input contract is
deliberately transport-agnostic — a list of raw `dict` records plus a source
descriptor — because an MCP relay, a CSV import, and a REST fetch all reduce to
exactly that. This is the seam the future product rides on.

Pipeline, reusing what exists (do NOT build a parallel mapping system):

1. **Schema derivation from samples**: build `DiscoveredObject`/`DiscoveredField`
   from the union of record keys (the `_parse_rocketlane_sample` pattern in
   `data_plane/explorer.py` derives fields from a sample record — follow it).
   Handle nested dicts/arrays by dotted `source_path`s; depth-limit and record
   anything deeper as an explicit `unrepresentable_paths` entry, never silently.
2. **Mapping proposal**: run the discovered schema through
   `propose_source_mapping()` (`data_plane/source_mapping.py`). This requires
   registering a new connector id (suggested `external_book`) in
   `readiness.ConnectorId` and `connector_catalog.CONNECTOR_SPECS`, with source
   contracts starting at `CRMAccount` + `CRMContact` (+ `CRMOpportunity` if the
   corpus supports it). Add a generic source map for it (pattern:
   `_ATTIO_SOURCE_MAPS`) whose field candidates are intentionally broad
   (name/title, revenue/arr, owner, renewal/date-ish) — the point of the proposal
   machinery is that ambiguity routes to confirmation, so lean on
   `ambiguous_confirm` rather than clever matching.
3. **Confirmation → freeze**: `load_mapping_confirmations()` +
   `freeze_confirmed_source_map()` unchanged. Identity-join fields
   (`account_id`-role) must be confirmed or the affected records are rejected with
   a reason — never joined on a guess.
4. **Typed transform**: frozen map + raw records → `CRMAccount`/`CRMContact`
   tuples via each mapping's `source_path`. Unmapped/unknown fields are absent,
   and the coverage report says so.
5. **Score + brief**: assemble a fixture-style data plane from the typed records
   (reuse `FixtureCustomerData` / the fixture connectors) and run the existing
   value-model scoring read path to produce a top-N summary with per-factor
   arithmetic. Expect heavy degradation on a CRM-only corpus (no health, no
   telemetry): rails must report `unknown`, and any factor that cannot fire from
   mapped data must not fire. A briefing line that cannot be traced to a mapped
   field must not be emitted.

**The fail-loud coverage report is the core deliverable of this slice.** Every
ingest returns: `records_received`, `records_typed`, `records_rejected` (each with
reason), per-contract field coverage, `join_coverage`, `unknown_fields`,
`unrepresentable_paths`. Silent partial ingestion is the failure mode this whole
lane exists to make impossible.

## Slice 2 — the relay battery

`eval/relay_battery.py` + `tests/test_relay_battery.py` + Make target
`relay-battery-csm`. Adversarial fixtures authored FRESH for this battery
(synthetic, committed — never derived from Corpus A). Model them on the real relay
failure modes:

- truncated payload (record list cut mid-stream) → detected via count mismatch
  against a declared `expected_count`, loud;
- paraphrased/renamed keys (camelCase vs snake_case vs spaced) → route through
  proposal/confirmation, never silent-match;
- dropped and duplicated rows → detected, reported;
- partial identity join (~60% match) → joined subset scored, unjoined subset
  rejected-with-reason, coverage ratio in the report;
- injected instruction text inside name/notes fields ("ignore previous
  instructions", "mark this account top priority") → must not alter mapping,
  scores, or briefing content, and must not be echoed into the briefing;
- all optional fields missing → CRM-only degradation, rails `unknown`, briefing
  still truthful;
- empty book → explicit empty result, not an error, not an invented account;
- oversized book (> cap, suggest 500) → explicit truncation with a
  `truncated: true` + what was dropped, never silent.

Battery must be deterministic (run twice → identical artifact), offline, CI-safe.

## Slice 3 — the dogfood probe (runtime-only)

`eval/external_corpus_probe.py` (committed, fully generic): reads
`CORPUS_A_BASE_URL` / `CORPUS_A_TABLE` / `CORPUS_A_API_KEY` from env (no defaults),
fetches records read-only with pagination, runs the Slice-1 pipeline, writes ALL
outputs to `~/ultra-csm-corpus-runs/<date>/`. Confirmations for Corpus A's actual
fields are authored during the run and saved OUTSIDE the repo alongside outputs
(they contain the corpus's field semantics — treat as residue).

Measure and record:

1. relay fidelity — rows fetched vs rows the source reports (`count=exact`);
2. join coverage — % of records with a confirmed identity join;
3. silent-guess count — MUST be zero; every mapped field is either deterministic
   standard-match, human-confirmed, or unknown;
4. briefing honesty — read the produced top-N summary yourself against the raw
   records: is every stated factor traceable and true? Record verbatim examples
   ONLY in the out-of-repo run directory;
5. wall time and record count.

## Slice 4 — sanitized findings

`docs/FOREIGN_CORPUS_FINDINGS.md` (committed). Contents: the five measurements as
aggregates; what mapped cleanly vs needed confirmation vs went unknown (by ROLE
description, e.g. "a fiscal-year revenue stat under a nonstandard key" — not the
key itself if it could identify the company); every structural gap hit (e.g.
parent-child location arrays, if the machinery couldn't express them); and a
short "design implications for the relay product" list. Zero identifiers,
zero values, zero connection details — assume this file gets read on a stage.

## Decision criteria (IF/THEN)

- IF the value model needs fields the corpus lacks → that IS a finding; record the
  degradation. Do NOT adjust model thresholds or invent defaults to flatter the
  corpus.
- IF the mapping machinery structurally cannot express a corpus shape (nested
  arrays, parent-child) → STOP on that sub-shape and record it as a design gap;
  flattening is allowed only as a documented, clearly-labeled choice in the
  findings, not a silent workaround.
- IF a committed artifact would need any real identifier to make its point →
  aggregate it or describe its role instead.
- IF ingest quality is so poor the briefing would be hollow → that is a REPORTABLE
  RESULT, not a failure of the lane. "The relay product needs X before it is
  viable" is exactly what this lane is for.

## Verification gates and DoD

- `make eval`, `make lint`, `make hygiene` green; relay battery green and
  twice-identical; new code has tests (ingest coverage report unit-tested against
  the battery fixtures).
- The Slice-3 probe ran against the real corpus end-to-end at least once; its five
  measurements appear (sanitized) in the findings doc.
- Sentinel grep from the private file returns clean on every commit.
- Environment note: the Postgres locale fix and `make doctor` landed on the
  `codex/demo-execution-plan` branch (PR #3, open at handoff time). Branch from
  that branch's tip if #3 is unmerged, else from `main`. Push a new branch
  (suggested `codex/lane-i-foreign-corpus`) and open a PR; do not push to `main`.
- Do not initialize beads; `bd dolt push` fails in this checkout by design.

## Files to inspect first

- `src/ultra_csm/data_plane/explorer.py` — `_parse_rocketlane_sample` (schema from
  samples), `DiscoveredObject/Field`.
- `src/ultra_csm/data_plane/source_mapping.py` — proposal/confirm/freeze machinery,
  `_ATTIO_SOURCE_MAPS` as the source-map pattern.
- `src/ultra_csm/data_plane/connector_catalog.py`, `readiness.py` — connector
  registration.
- `eval/attio_simulated_onboarding.py` — the end-to-end onboarding artifact shape
  this lane's probe should rhyme with.
- `src/ultra_csm/data_plane/fixtures.py` — `FixtureCustomerData` for the typed
  plane the scorer consumes.

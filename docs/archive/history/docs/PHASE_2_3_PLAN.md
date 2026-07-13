# Phases 2–3 Plan: Relational Ingest, Seeding, and the Live Battery

Program 3, continued. Phase 1 (the corpus B pristine one-shot) is complete and
committed: single-table Account ingest proved clean 13/13; Contact/Opportunity
sessions surfaced a structural gap (the pipeline requires a self-contained
denormalized book) and two secondary findings (coverage evidence cannot catch
semantically-wrong candidates; a latent amount/cents unit gap). This plan turns
those findings into engineering — under one governing constraint.

## The governing constraint: do not engineer to the shape of our tests

This project has now twice caught the same class of failure: machinery that
passed its own fixtures while being wrong about the world (the hollow-contacts
confirmation; the mechanically-generated template matching its own generator).
The Phase 1 findings are a third warning in milder form — the ingest boundary
was built against corpus A's shape and could not survive first contact with a
normal relational CRM. The fix must therefore NOT be "support Salesforce's
three tables." It must be the general model, of which every corpus we have is
an instance. Concretely, four rules bind everything below:

1. **General model first, instances second.** The core data model is "a book =
   N record-sets with identity relationships." Corpus A's flat single table is
   the N=1 degenerate case with nested children. Salesforce is N=3 with foreign
   keys. HubSpot/Attio relayed through MCP will be other instances. Zero
   source-specific branches in `external_book` — source specifics may only
   appear as *evidence passthrough* (e.g. field metadata a host chooses to
   supply), never as logic.
2. **Properties, not just examples.** The battery gains generated, seeded-random
   relational books with invariants that must hold for EVERY generated shape —
   properties the implementation cannot memorize. Fixed fixtures remain for
   regression, but acceptance is property-based.
3. **Three-corpus acceptance.** A change is done only when the SAME code path
   passes: (a) the generated property battery, (b) the corpus A recorded-input
   replay (regression — the flat shape must keep working), and (c) the corpus B
   live shape (the normalized shape that exposed the gap). Passing our authored
   fixtures alone proves nothing.
4. **Honesty invariants are non-negotiable and get foil tests**: no identity is
   ever fabricated; `typed + rejected = received` per table; every rejection
   carries a reason; unknown stays unknown; injection text never alters
   mapping/scores and is never echoed; replay of recorded inputs is
   byte-deterministic.

## Phase 2A — The relational book model (the real fix)

**Data model.** Extend the relay session to hold multiple named record-sets:

- `ingest_table(book_id, table_name, records, expected_count, final_chunk)` —
  repeatable per table; the existing single-book `ingest_book` becomes sugar
  for a one-table book (backward compatible; corpus A path unchanged).
- Proposal stage runs per table (same propose/sparsity machinery), but
  confirmation happens per book: `confirm_book(book_id, confirmations)` where
  each contract's confirmations name their source TABLE as the source_object
  (the field already exists — today it is always "records"; it becomes real).
- **Join declaration is a confirmation, not an inference.** A child contract's
  `account_id` mapping names table+field (e.g. Contacts.AccountId) and the
  freeze validates it as `identity_join` against the parent identity mapping
  (Accounts.Id): join keys must be DISTINCT coordinates (the identity-audit
  rule, now cross-table), and the transform resolves children to parents by
  key equality.
- **Orphan policy is explicit, decided now, default loud:** a child whose join
  key matches no parent in the book is rejected with reason
  `unresolved_parent_identity` and counted; a `join_coverage` block per child
  contract reports matched/orphaned/total. No policy knob in v1 — reject-loud
  is the only behavior; a permissive mode can be argued for later with
  evidence, not speculatively.
- The account-identity gate stays — but it gates the ACCOUNTS table, not every
  table. Child tables gate on their own identity + a resolvable join.

**Deliberately NOT doing:** cross-table schema inference (guessing which table
is the parent), fuzzy key matching, multi-hop joins (child→child→parent), and
any relationship not confirmed by a human. All are seductive generality in the
wrong direction — more inference where the design doctrine is less.

## Phase 2B — Semantic evidence (kill the StageName-as-name class)

Coverage-perfect-but-wrong candidates require evidence beyond row counts:

- Deterministic **value-shape classification** per candidate, computed from the
  sampled values themselves (no LLM): `id_like` (opaque uniform-length tokens,
  high uniqueness), `name_like` (mixed-case multi-word strings), `date_like`,
  `numeric`, `low_cardinality_enum` (≤ ~10 distinct values across sample —
  which is exactly what StageName is), `email_like`, `boolean_like`. Shape +
  uniqueness ratio + distinct-count join rows_present/rows_nonempty in every
  candidate's evidence.
- Optional host-supplied **field metadata passthrough**: `ingest_table` accepts
  an optional `field_meta` map (label/type per field, e.g. from Salesforce's
  describe); it is evidence only — displayed with candidates, never used to
  auto-map.
- Proposal ranking may use shape compatibility (an `id_like` candidate ranks
  above a `low_cardinality_enum` for an identity field) but NEVER auto-confirms
  across shape classes; ambiguity still routes to a human. The point is the
  human sees "StageName — enum, 10 distinct values" next to "Name — name-like,
  13 distinct" and cannot easily choose wrong.

## Phase 2C — Declared transforms (the amount_cents gap)

A confirmation may carry `transform`, from a CLOSED enum — no expressions, no
DSL: `currency_to_cents` (×100, decimal-safe, rejects non-numeric loudly) and
`none` (default). That single transform fixes the known gap; the enum exists so
the next one (if ever justified by a real corpus) has a place to live. The
frozen config hash covers transforms; replay determinism includes them.
Anything needing more than an enum entry is a design conversation, not a patch.

## Phase 2D — The property battery (anti-Goodhart enforcement)

New `eval/relational_battery.py` + tests, no new dependencies: a SEEDED
deterministic generator (explicit seed list committed; each seed → a full
relational book) that randomizes: table count (1–4), field names (random
casing/underscore/camel variants — never the fixture names), key formats,
parent/child ratios, orphan injection rate, null rates, enum-like columns,
name-like columns, duplicate keys, oversized text, injection strings, chunked
delivery splits. For every generated book, after a programmatic-but-audited
confirmation pass (choose candidates by shape-evidence rules, then assert the
identity-audit invariant before freezing), the invariants in rule 4 above are
asserted, plus: orphan counts equal the injected orphan count exactly;
renaming every field (same seed, renamed variant) changes NOTHING about typed
counts once equivalent confirmations are applied — a metamorphic test the
implementation cannot shortcut by memorizing names.

Battery is deterministic (seeded), CI-safe, byte-identical across two runs.
The generator lives in eval, is itself unit-tested, and its seeds are frozen in
the artifact so failures reproduce exactly.

## Phase 2E — Seeding corpus B (writes begin; holdout formally retired)

Only after 2A–2D are merged-green (fixtures + property battery + corpus A
replay). The org becomes a permanent test bench at the first write; the
pristine one-shot findings are already committed, so nothing is lost.

Datasets are seeded as LINKED sets (parents + children, per the Phase 1
lesson) via `createSobjectRecord`, every created Id logged to the run ledger,
every record tagged (marker token in a standard text field) so program data is
always distinguishable from factory data. Factory records are never updated or
deleted. Budget: stay well inside dev-org API limits; batch politely; partial
seeds are fine if measured.

1. **volume**: ~120 accounts + ~240 contacts + ~180 opportunities (forces
   multi-chunk relay and cap behavior; volumes chosen to exceed the 200-row
   bound on contacts).
2. **hostile text**: unicode/emoji/RTL/very long strings + the battery's
   injection markers, in Name/Description fields of linked records.
3. **sparse**: linked records with every optional field null.
4. **broken joins**: contacts/opportunities whose AccountId points at other
   datasets' parents, at each other, and (where the API even permits) nothing —
   the live orphan-policy test.
5. **unmapped shapes**: Leads and Cases (objects with no source map) — must
   flow through proposal → unknown/not_mappable honestly, zero silent guesses.

## Phase 3 — The live battery

For each dataset, a fresh relay run (bounded fetch via SOQL with explicit field
lists, one book = linked tables, confirmations authored from the evidence):
record fetched-vs-expected, typed-vs-rejected per contract, join coverage vs
the KNOWN seeded truth (we authored the data — assert exact numbers, never
impressions), injection marker count and non-echo, truncation behavior at caps,
replay determinism. Then the regression trio: corpus A replay, sim-book
`make demo`, full suite — all on the same commit.

Defects found live are fixed with a reproducing unit test first, then the
dataset re-runs (this org is a bench now — iterate freely, unlike Phase 1).
Findings → `docs/LIVE_INTEGRATION_FINDINGS.md` with the battery matrix;
PROGRAM_REPORT_3 per-phase evidence; README/TOUR truth updates only for
executed-true claims; single PR.

## DoD ledger (Phase 2–3 portion)

- [ ] 2A relational book: multi-table ingest + confirmed joins + orphan
      rejection; corpus A replay passes UNCHANGED through the same path;
      `ingest_book` back-compat proven by existing tests passing unmodified.
- [ ] 2B shape evidence on every candidate; StageName-class candidates visibly
      classified; field_meta passthrough optional and evidence-only.
- [ ] 2C `currency_to_cents` transform, hash-covered, replay-covered, loud on
      non-numeric.
- [ ] 2D property battery: seeded generator + invariants + metamorphic rename
      test; two-run byte-identical artifact; generator unit-tested.
- [ ] 2E seeds live in org, every Id ledgered, factory data untouched
      (post-seed count check: factory counts unchanged from the Phase 0
      baseline snapshot).
- [ ] 3 live battery matrix complete with exact-number assertions vs seeded
      truth; corpus A replay + sim demo + full suite green on the same commit;
      findings + program report committed; PR open, gates green, sentinel
      clean.

## STOP conditions (additions to the program's standing set)

Any temptation to special-case a source name in core ingest code; any
auto-confirmation across shape classes; any write touching factory records;
property battery invariant weakened to pass; transform enum growing past what
a real corpus demanded.

## Amendment (2026-07-03): friction-first reordering

Decision, applied after 2A-2D landed: the ideal path to user outcomes is
friction-first — a user should get from "connected" to "briefing on my book"
with only the questions that are genuinely theirs to answer, no scripts, no
config authoring. Ordering for the remainder of the program:

1. **Auto-map provenance tiers (DONE with this amendment).** Tier A: a
   source-declared reference auto-maps a CHILD contract's account_id foreign
   key (and never the account contract's own identity — a reference field is
   by definition a child's FK; promoting it would let a child table mint
   shadow accounts). Tier B: an exact standard-field alias with compatible
   value shape and ≥80% coverage auto-maps non-identity fields, the same bar
   the native connectors use for deterministic standard-field matches.
   Identity picks and value-direction calls always stay human. Measured on
   the real corpus B book: 29 confirmation questions → 5, all five genuinely
   human (4 identity picks, 1 value direction).
2. **MCP exposure of the relational flow** (ingest_table/confirm_book) so
   onboarding happens conversationally in a Claude session — no driver
   scripts. Then a committed end-to-end conversational onboarding transcript.
3. **2E/3 as planned**, run through the same auto-mapped path users will
   actually hit, so the robustness battery tests the product surface rather
   than an internal API nobody will call directly.

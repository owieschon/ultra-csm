# Foreign-Corpus Ingest Findings

Run date: 2026-07-03 UTC.

This is a sanitized evidence record for a read-only runtime probe against a
private external customer book. Raw records, field names, source-map proposals,
confirmations, and briefing text remain outside the repository under
`~/ultra-csm-corpus-runs/`. This document contains aggregates only.

## Claim Boundary

- The probe used a private runtime source and read-only requests.
- The probe did not use live customer-success, product-telemetry, or email
  credentials.
- The probe was bounded to 200 fetched rows; the source reported 11,160 rows.
- The confirmed pass used an out-of-repo confirmation template generated from the
  discovery pass. The result is evidence about ingest behavior, not proof of a
  production-ready connector.

## Measurements

| Measurement | Result |
| --- | --- |
| Rows fetched | 200 |
| Source-reported rows | 11,160 |
| Pages fetched | 2 |
| Full source fetched | No, intentionally bounded |
| Runtime wall time | 1.1 seconds on the confirmed pass |
| Silent guesses | 0 |
| Fields requiring confirmation | 9 |
| Fields degraded to unknown | 8 |
| Unrepresentable shape paths | 11 |
| Injection markers observed in sample | 0 |
| Scoreable CSM work items | 0 |

## Discovery-Only Pass

The first pass fetched the bounded sample and refused to type records because no
frozen source map had been supplied. That is the intended behavior: external
fields may be suggested for confirmation, but the runtime does not treat a
suggestion as a mapping.

## Confirmed Pass

After loading the out-of-repo confirmation template, the transform produced:

| Contract | Typed records |
| --- | ---: |
| CRMAccount | 6 |
| CRMContact | 0 |
| CRMOpportunity | 0 |

The transform rejected 194 records with `missing_account_name`. Contact join
coverage was not exercised in this sample because no contact candidates were
typed after account gating. The briefing stayed in the CRM-only lane and stated
that CS-platform health and product-telemetry rails remain unknown.

The work-item scorer was not run on the confirmed pass. With only sparse CRM
account context and no CS-platform, onboarding, outcome, or product-telemetry
rails, running the scorer would produce a hollow queue rather than grounded CSM
work.

## Review Verification (corrected pass)

A review re-run resolved the 6/194 split. The corpus is NOT sparse on the display
name: a universally-present title-like key exists on 200/200 sampled rows. The
mechanically generated confirmation had instead selected a rare variant key present
on only 6/200 rows. Re-running the same bounded probe with one corrected
confirmation typed **200/200 CRM accounts** (was 6/200), zero silent guesses,
wall time 2.6 s.

Two conclusions, both decisive for the product design:

- The refusal behavior worked exactly as intended: a wrong confirmation produced
  loud mass rejection, not silently wrong accounts. The freeze layer also refused
  a template that omitted one required confirmation.
- A mechanical confirmation is a simulated careless user, and it silently costs
  97% of the book. The field-sparsity review surface (show per-key row coverage
  before freezing) is therefore not an enhancement — it is the difference between
  3% and 100% ingest coverage. A conversational confirm ("variant key on 6 of 200
  rows vs a title key on all 200 — which is the name?") makes the right choice
  trivial for a human.
- Gap found during review: there is no way to demote an ambiguous proposed field
  to `unknown` at confirmation time — every ambiguous field demands a positive
  confirmation to freeze. Confirmations need an explicit "not mappable / unknown"
  verdict.

## Phase 1 Hardening Re-probe

After adding sparsity evidence, explicit `not_mappable` confirmations, cross-book
sampling, and child-record extraction, a fresh bounded re-probe produced the
following aggregate results. Runtime artifacts remain outside the repository in
the two run directories named by the probe summaries.

| Measurement | Result |
| --- | --- |
| Rows fetched | 200 |
| Source-reported rows | 11,160 |
| Pages fetched | 2 |
| Silent guesses | 0 |
| Fields requiring confirmation | 13 |
| Fields degraded to unknown before confirmation | 4 |
| Top display-label candidate coverage | 200/200 non-empty |
| Next lower display-label alternatives | 6/200 and 1/200 non-empty |
| Confirmed CRMAccount records | 200/200 |
| Confirmed CRMContact records | 200/200 (see correction below) |
| Confirmed CRMOpportunity records | 200/200 (see correction below) |
| Contact join coverage | 200/200 (see correction below) |
| Unrepresentable shape paths | 8 |
| Injection markers observed in sample | 0 |

The generated confirmation template selected the full-coverage display-label
candidate without hand editing. The competing sparse alternatives remain visible
in the proposal evidence, which is the intended operator-review behavior: a human
can see why the full-coverage candidate is the obvious mapping before freeze.

## Correction: the CRMContact/CRMOpportunity numbers above were hollow

A later live host-driven run (a person walking the confirmation questions instead
of a mechanically generated template) caught a real defect in the run above: the
template had confirmed `CRMContact.contact_id` and `CRMOpportunity.opportunity_id`
to the SAME source path already used for `CRMAccount.account_id`. Every "contact"
and "opportunity" record it produced was the account row itself, relabeled under
a different contract, with the account's own fields substituted for contact
name/email. `contacts_joined: 200, ratio: 1.0` was therefore a tautology, not a
join — every account trivially "joins" its own id to itself.

Real per-contact identity in this corpus lives in a nested collection at
`data.contacts` (listed above under unrepresentable shape paths). Child-record
extraction is real and unit-tested (a directly-nested `contacts[]` array on the
record extracts correctly), but it does not recurse through an intermediate
wrapper object first — this corpus's JSONB `data` envelope sits one level
between the record and the collection, which the current extraction does not
reach through. A live host that
actually reads the proposal's candidate evidence has no reason to pick
`CRMContact.contact_id <- (same path as CRMAccount.account_id)`: nothing in the
proposal suggests that mapping is correct, and a careful confirm should mark it
`not_mappable` instead. Re-running the same bounded fetch with `not_mappable`
confirmations for every CRMContact/CRMOpportunity field produced the honest
result: **CRMAccount 60/60 typed, CRMContact 0/60, CRMOpportunity 0/60,
`join_coverage: {contact_candidates: 0, contacts_joined: 0, ratio: null}`**, and
60/60 accounts returned a loud `MISSING_CS_DATA` score error rather than a
silent or fabricated score. That is the correct degraded outcome for a CRM-only
relay with no reachable contact/opportunity identity, and it is what the
"hollow briefing is a valid result" design principle exists to produce.

Two fixes landed from this: `join_coverage.ratio` is now `null` (not `1.0`) when
there are zero contact candidates — a vacuous 0/0 must never render as 100%
success — and this document's earlier 200/200 CRMContact/CRMOpportunity/join
numbers are superseded by this correction. The underlying gap (nested
`data.contacts`-style collections not reaching child-record extraction on this
corpus's shape) remains open for a future ingest-hardening pass.

Child records were extracted where the existing CRMContact contract could
represent them and the parent account identity could safely supply the join. The
remaining unrepresentable paths stayed declared as shape limits rather than being
guessed into new contracts.

## Structural Findings

- (Superseded by the review verification above.) The initial pass read as
  "heterogeneous or sparse" for the display-name field; the corrected pass showed
  the sparsity belonged to the generated confirmation's chosen key, not the corpus.
- Nested or collection-shaped source data exists in the sample and is not fully
  representable in the current flat CRMAccount/CRMContact/CRMOpportunity
  contracts.
- The mapper correctly avoided silent matching: no field entered runtime as
  mapped without confirmation.
- The bounded fetch creates an intentional count mismatch. The coverage report
  records that mismatch loudly instead of implying full-book coverage.

## Design Implications

- The explorer needs a review surface that shows field sparsity before the user
  freezes a mapping.
- The source-map confirmation flow should support sampling across the book, not
  only the first discovered shape.
- Parent-child and collection fields need an explicit representation strategy
  before they can drive CSM work items.
- CRM-only ingest should remain a degraded-but-usable state: it can establish
  account context, but health, adoption, and outcome rails must remain unknown
  until CS-platform and telemetry sources are connected.
- A hollow or sparse briefing is a valid result. It should block overconfident
  claims and drive onboarding guidance rather than being papered over.

# Salesforce One-Shot Findings

Run date: 2026-07-03.

Claim boundary:

- `live=true`
- `one_shot=true`
- `transport="official Salesforce Hosted MCP server (sobject-all), host-driven relay"`
- `tenant="Salesforce Developer Edition, factory sample data"`
- `business_data_touched=true` (read-only queries only; zero writes this phase)

The one-shot ran via the live Salesforce Hosted MCP connection (OAuth, PKCE,
refresh tokens), with a Claude Code session acting as the host relaying real
records into ultra-csm's `report_readiness`/`ingest_book`/`confirm_book_mappings`
tools — the same relay path already proven against corpus A, now proven against
a genuinely normalized, real multi-table CRM for the first time. This supersedes
the credential-boundary stop recorded in the prior program (PR #10); credentials
now exist via the live MCP connection rather than the env-var path, which
remains unused and still unconfigured.

No org URL, username, employer-linked identity field, or credential value is
recorded here — see the private corpus file's residue rules, now extended to
this org. Salesforce's own factory sample account/contact/opportunity names
(e.g. the well-known Trailhead demo dataset) are public Salesforce-authored
content, not private customer data, and are referenced here only in aggregate
form consistent with that distinction.

## Measurements

| Object | Rows fetched | Fields queried | Typed via relay | Rejection reason |
| --- | ---: | --- | ---: | --- |
| Account | 13 | Id, Name, OwnerId, Industry | 13/13 | — |
| Contact | 20 | Id, AccountId, Email, Name, Title | 0/20 | `missing_account_identity` (structural, see below) |
| Opportunity | 31 | Id, AccountId, StageName, Amount, CloseDate, Type | 0/31 | `missing_account_identity` (structural, see below) |

Silent guesses: 0. Injection markers observed: 0. Unrepresentable shape paths: 0
(this schema is flat; no nested-collection issue like corpus A's K4 gap).

## Structural finding: the relay ingest pipeline requires a self-contained book

`external_book`'s transform pipeline gates every record on a resolvable
`CRMAccount.account_id` **and** `CRMAccount.name` before it will type any child
CRMContact/CRMOpportunity record, because it was designed against corpus A's
shape: one denormalized row that is simultaneously the account and (via a
nested collection) its own children. Salesforce's real schema is properly
normalized — Contact and Opportunity are independently queryable tables joined
to a *separate* Account table by a real foreign key (`AccountId`). Relaying
Contacts or Opportunities as their own session, with no Account fields present
in those same rows, has no way to satisfy the account-identity gate — every
record is correctly, loudly rejected rather than silently dropped or
misassigned.

**What was explicitly NOT done to work around this**, per this program's
standing rules: the account-identity gate could be satisfied by mapping
`CRMAccount.account_id` to the Contact/Opportunity row's own `AccountId` field
(a value that is real and correct) and `CRMAccount.name` to some other
present field as a placeholder — but that field would not actually be an
account name (e.g. the Contact's own `Name`, or the Opportunity's `StageName`,
both of which the proposal mechanically offered as coverage-perfect candidates
purely because they are non-null on every row). Confirming either would mint a
"shadow account" carrying the real parent's id but a fabricated name — the
same class of defect as the hollow-contacts bug this project already fixed
once. It was correctly refused here rather than repeated.

**A related, narrower finding**: the proposal offered `StageName` (31/31
non-empty) as a same-coverage candidate for `CRMAccount.name` — a case where
per-candidate row-coverage evidence (the K1 sparsity surface) cannot
distinguish a semantically wrong candidate from a correct one, because both
have perfect coverage. Coverage-based evidence solves *coverage* ambiguity;
it does not solve *semantic* ambiguity. A future confirmation surface may want
to show candidate field labels/types (Salesforce's own field metadata already
carries a `type` and `label`) alongside coverage, since "StageName: picklist"
next to "Name: string" would make the wrong choice visibly wrong.

**Also found, not yet verified against real typed records** (verification
blocked by the structural gap above, since no Opportunity ever typed): the
existing `SALESFORCE_SOURCE_MAPS` for `CRMOpportunity.amount_cents` documents
that Salesforce's `Amount` field is a raw currency value, "stored internally
as cents" — implying a unit conversion is expected somewhere in the pipeline.
The generic `external_book` relay path does a raw passthrough with no unit
conversion step. If a future fix resolves the structural gap above and
Opportunity records begin typing, `amount_cents` values relayed this way will
be off by a factor of 100 (dollars stored where cents are expected) until this
is addressed. Recorded as a known, unverified-in-practice risk.

## Design implications

- The relay ingest boundary should support a "linked book" mode: multiple
  sessions (one per real table) that share an account-identity namespace,
  rather than requiring every session to independently satisfy the
  account-identity gate. This is the concrete next step for any real
  normalized-schema CRM relayed this way (Salesforce, and likely any other
  properly relational CRM).
- Confirmation candidate evidence should carry field type/label alongside row
  coverage, to catch semantically-wrong-but-coverage-perfect candidates like
  `StageName` being offered for an account name field.
- The `amount_cents` unit-conversion gap is real but currently unobservable
  through this path; flagged for whoever next gets Opportunity records typing.
- Account-only ingest is fully proven and works correctly today: 13/13 typed,
  zero silent guesses, real field-level sparsity evidence surfaced correctly
  (`Industry` 11/13 non-empty, both nulls on Salesforce's own no-industry demo
  accounts).

## What this does and does not prove

Proves: the relay path works end-to-end against a real, live, official
Salesforce connection for a single-table (Account) ingest, with zero
fabrication and correct honest degradation everywhere else. Does not prove:
multi-table relay with real cross-object joins (Contact→Account,
Opportunity→Account) — that specific capability does not exist yet, this run
is the evidence that surfaced the gap, not a workaround of it.

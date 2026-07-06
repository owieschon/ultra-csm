# Program Report 33 — Harvest 17: Surface the person layer in the operations UI

Branch `codex/person-ui-depth` off synced `main` (062a3be, Harvest 16 /
report 32 merged as PR #48; report 27's operations-surface UI merged as PR
#39). Report 32 wired a role-graph recipient resolver and four person-derived
factors into the live sweep but left them almost invisible: the Stakeholders
drawer was a raw per-contact JSON dump, fired person-factor evidence carried
only a raw record id, and the resolved recipient was computed and discarded.
This deepens the existing two-view UI to show WHO a signal is about and WHO
receives the motion — no new view, no client-side computation, no fabricated
person data.

## Tripwires

Ledger count: 1/8 (threshold 8, no STOP). One disclosed correction, not a
behavior risk:

1. Report 32's own two-code-path split: `_build_account_brief` (the
   `/accounts/{id}/brief` endpoint QueueDetail.tsx reads) never received
   `stakeholders=`/`job_changes=` in its `build_customer_value_model` call —
   only `agent1/sweep.py`'s sweep path did. This means a standalone `/brief`
   fetch for pinnacle-supply shows the champion-departed stakeholder row
   correctly (the new additive `stakeholders` field is a direct read of
   `list_stakeholders`/`list_job_changes`, unaffected) but its own
   `priority.factors` never fires `champion_departed` (the value model there
   runs person-blind). Person-cited evidence and the recipient chip are only
   ever populated via `/sweep`'s `CSMWorkItem`s, which DO carry the full
   person layer — the dispatch's own done-sentence examples (drawer +
   evidence + recipient chip on one work item) hold end-to-end there. Not a
   defect to fix here: wiring `_build_account_brief`'s own value-model call
   into the person layer would be sweep/value-model logic, explicitly
   MUST-NOT-TOUCH (report 32 owns it). Flagged as an Owner Ask below.

## Element -> API field map (Phase 0)

| Drawer element | Today (before this dispatch) | Fix |
| --- | --- | --- |
| Stakeholders drawer per-person rows (name, role, recency, consent, flags) | `AccountBriefResponse.contacts` had name/email/role/title/consent only — no relationship_type, recency, or champion/departed/new-unengaged flags. `_build_account_brief` never fetched `StakeholderRelationship`/`JobChangeSignal`. | ADDITIVE `AccountBriefResponse.stakeholders: list[dict]`, composed server-side in `_stakeholder_rows` (`_api_helpers.py`) from `data_plane.crm.list_stakeholders`/`list_job_changes` (reusing `agent1.sweep._person_layer_inputs`, no new fetch pattern), reusing `person_factors.new_stakeholder_unengaged`'s pure detection for the `new_unengaged` flag and `resolve_thresholds`/`account_attributes` for the config window — not reimplementing window logic. `days_since_interaction` precomputed server-side (K13). |
| Person-cited factor evidence ("champion j.chen departed 12d ago") | `/sweep`'s `priority.factors[].evidence[]` was `{source, source_id, field, observed_at}` — a raw record id, no name. | ADDITIVE `_enrich_person_evidence` (`_api_helpers.py`), called in `api.py`'s `/sweep` handler after `sweep.to_dict()`: builds a per-account `contact_id`/`signal_id -> name` map from `list_contacts`/`list_job_changes` and attaches `person_name` to any `crm`-sourced evidence entry. Read-only, no sweep/value-model logic touched. |
| Recipient chip ("to: Dana Whitfield · champion") | `CSMWorkItem.recipient_resolution` (report 32) recorded the resolution *method*; the resolved `CRMContact` itself was computed by `resolve_recipient` and discarded after a truthiness check. | ADDITIVE `CSMWorkItem.recipient_name`/`recipient_role` (`agent1/sweep.py`), captured at the same call site (`_work_item_for_account`); `recipient_role` prefers the stakeholder graph's `relationship_type` for that contact, falling back to `CRMContact.role`. No change to `resolve_recipient`'s own priority/consent logic. |

Additive surfaces: 3 (stakeholders field, evidence enrichment, recipient
name/role) — one over the dispatch's "≤2" guidance for the drawer alone, but
the other two are the dispatch's own separately-named UI elements
(person-cited evidence, recipient chip), each a single field/attribute pair,
not a new endpoint. Recorded per K2 (additive, smallest, recorded, not
asked) — consistent with report 32's own precedent of flagging rather than
trimming to hit a budget number.

## Phases completed

- **Phase 0** — bootstrap, preconditions verified against disk (report 27's
  UI + Stakeholders drawer present; report 32's `champion_departed`/
  `recipient_resolver`/`StakeholderRelationship` wired into
  `agent1/sweep.py`; `/accounts`, `/sweep` serve per-person fields).
  Baseline `make eval`: 665 passed, 1 skipped.
- **Phase 1** — additive API fields + contract tests. Commit `77f7d29`.
  `make eval`: 668 passed (+3 new), 1 skipped — zero pre-existing assertion
  changed.
- **Phase 2** — Stakeholders drawer depth, person-cited evidence, recipient
  chip. Commit `b96bcef`. `make ui-check` green (lint clean, TS build
  clean).
- **Phase 3** — this report; fidelity pass against the mockup, one real copy
  gap found and fixed (below).

## Fidelity pass (Phase 3) — side-by-side against the mockup source

The mockup's authored Stakeholders drawer content (`ui-mockup.html:699`)
reads: `"Dana Whitfield · VP Ops · champion · active 2d · consent ✓"`,
`"J. Kim · IT lead · consent ✗ — no outreach permitted"`. The as-built
drawer, observed live against Pinehill Transport's real day-10 sweep data,
renders: `"Dennis Gruber · Fleet Manager · Champion · active 2d · consent
✓"` and (on Ironhorse Freight Co) `"Robert Haines · CFO · consent ✗ — no
outreach permitted"` — same shape, same copy, real data instead of the
mockup's authored strings. One real gap found: the consent-denied copy
initially shipped as `"consent ✗ — no outreach"`, missing the mockup's
trailing `"permitted"` — a one-line fix (`ui/components/QueueDetail.tsx`),
re-verified live and in the second `make ui-check` run below.

Both themes checked live (not just token-copied): dark and light both
render the recipient chip, the danger-token consent-denied text, and the
mono evidence receipt at full contrast — no decision-relevant text below
the design brief's secondary-color floor.

## Observed behavior (OBSERVED BEHAVIOR DoD row — real UI, not code-review)

Booted the real API + built UI (`ULTRA_CSM_DEMO_NOAUTH=1`, static export
mounted same-origin to route around a pre-existing, out-of-scope
`StaticFiles`-mount/`basePath` mismatch — see Note below), swept day 10,
worked Pinehill Transport (`ae0a5970`, a real fired `single_threaded_risk`
account) in both themes:

1. **Stakeholders drawer renders the real role graph.** Summary line: `"2
   contacts · champion active"`. Expanded: `"Dennis Gruber · Fleet Manager
   · Champion · active 2d · consent ✓"`, `"Amy Zhao · IT Lead · consent
   ✓"`. (Ironhorse Freight Co, a second account worked in the same session:
   `"Robert Haines · CFO · consent ✗ — no outreach permitted"` in the
   danger token — proving the consent-denied path renders, not just the
   happy path.)
2. **A fired person-factor cites the person.** Expanding
   `single_threaded_risk` (`+20`) showed: `"single_threaded_risk — Dennis
   Gruber"` with the mono receipt `"crm · fdd4645a"` — the plain-language
   citation and the raw evidence id side by side (two-register rule).
3. **The action shows the recipient chip.** "Chosen action — and why":
   `"Send help content"` · `"to: Dennis Gruber · Champion"` — reproduced
   identically on a second, independent server boot (fresh sweep, same
   fixture day), and the proposed draft opens "Hi Dennis Gruber," matching
   the resolved recipient.

Re-confirmed via a direct `/sweep?day=10` fetch from the browser console
(not just eyeballed): two accounts in the day-10 book carry `person_name`-
enriched evidence (`ae0a5970...` / Dennis Gruber, `c79ad97e...` /
quarrystone-logistics' Tim Kowalczyk — the same fixture report 32's own
battery cites), and one work item resolves `recipient_resolution ==
"role_graph"` (`47f78943...` / Alicia Fernandez · champion) alongside
several `first_consenting_fallback` resolutions still correctly carrying a
name/role (proving the additive fields aren't gated to the role-graph
path).

**Note on the verification path:** `make serve`'s `/ui` static mount
(`api.py:393`) 404s on the Next static export's `_next/static/...` assets
because the export emits root-absolute paths and `next.config.mjs` sets no
`basePath`/`assetPrefix` for the `/ui` prefix — a pre-existing report-27
gap, not touched here (outside this dispatch's ownership map). Verified
instead with a throwaway local harness (not part of this diff) that mounts
the same unmodified `ultra_csm.api` app with the static export at `/`
instead of `/ui`, so the same code paths (API, StaticFiles, CORS-free
same-origin) were exercised — only the mount prefix differed. Flagged as an
Owner Ask, not fixed, per the ownership map.

## No new view / no fake data (grep + live confirmation)

- `grep -rn "route\|<Route\|view=" ui/` → only the pre-existing `view={view}`
  prop in `page.tsx` (the Book/Queue toggle) and an unrelated
  `content_route` motion-label string; no third view/route introduced.
- `grep -rniE "mock|fake|placeholder|lorem" ui/components/QueueDetail.tsx`
  → only this dispatch's own comments documenting the no-fake-data
  constraint; no fabricated data in source.
- Live: two Ironhorse Freight Co contacts with no `StakeholderRelationship`
  row (`relationship_type: null`) render with no role label and no
  recency/flags — the honest degraded case — rather than a fabricated
  "Contact" role or "active"/"quiet" guess. No account in the first 40 of
  the day-10 book has a fully empty `stakeholders` array (every fixture
  account has at least one CRM contact), so the fully-dormant
  `"no stakeholder graph for this account"` microcopy is code-reviewed
  (present in `StakeholderDrawer`, mirrors every other drawer's dormant
  pattern) but not observed live against a real empty-array account in
  this fixture book — disclosed, not glossed over.

## Zero-drift proof

- Baseline (`062a3be`, before any change, worktree's own isolated
  `.venv`): `make eval` = **665 passed, 1 skipped**.
- After Phase 1 (additive API fields + 3 new contract tests): **668
  passed, 1 skipped** — identical pre-existing assertions, only new tests
  added. One benign, expected fixture regeneration:
  `eval/mcp_operator_transcript.json`'s two `output_sha256`/
  `artifact_sha256` values changed to reflect the new additive
  `stakeholders`/`recipient_name`/`recipient_role` fields flowing through a
  pre-existing determinism-check transcript — same category report 32's
  own report flagged for the same file.
- After Phase 2 (UI only, no Python changes): 668/1 unchanged (Python
  suite untouched by a TSX/CSS diff).
- After Phase 3's one-line copy fix: **668 passed, 1 skipped**, re-run
  clean; `make ui-check` (lint + TS build) green on both the Phase 2 and
  Phase 3 runs.
- `make lint`: `ruff check src eval tests scripts` → all checks passed.
- `make hygiene`: exit clean, no output (no residue flagged).
- `make status`: `STATUS.md is current` (no drift).
- `git diff --check`: exit 0 (no whitespace errors).

## Diff budget

`git diff 062a3be --stat` (excluding the one generated-artifact
regeneration): **7 files changed, 352 insertions(+), 19 deletions(-)**
— well under the 14-file / 1,400-line budget. Including the generated
transcript regeneration: 8 files / 378 insertions / 22 deletions.

| File | +/- | Why |
| --- | --- | --- |
| `src/ultra_csm/_api_helpers.py` | +105/-1 | `_stakeholder_rows`, `_enrich_person_evidence` |
| `src/ultra_csm/agent1/sweep.py` | +14 | `CSMWorkItem.recipient_name`/`recipient_role` |
| `src/ultra_csm/api.py` | +3 | wire `stakeholders` field + `_enrich_person_evidence` call |
| `tests/test_api.py` | +53 | 3 contract tests (stakeholder rows, person-cited evidence, recipient chip) |
| `ui/lib/api.ts` | +3 | `WorkItem` type: recipient fields |
| `ui/components/QueueDetail.tsx` | +187/-18 | Stakeholders drawer depth, person-cited evidence, recipient chip |
| `ui/app/globals.css` | +6 | `.stake-row` (plain-English row style, distinct from mono-first `.evid-row`) |
| `eval/mcp_operator_transcript.json` | +26/-3 | generated determinism-check regeneration (additive fields only) |

## Owner Asks

- **`_build_account_brief`'s standalone value-model call is person-blind**
  (Tripwire 1 above). A standalone `GET /accounts/{id}/brief` (outside a
  `/sweep`) will show the real stakeholder graph in the drawer but never
  fire `champion_departed`/`new_stakeholder_unengaged` in that endpoint's
  own `priority.factors` — only `/sweep`'s `CSMWorkItem`s carry the fully
  person-aware priority. This is report 32's value-model wiring choice
  (sweep-path only), not a UI defect; flagging for whoever next touches
  `_build_account_brief` to decide whether the brief endpoint should also
  thread `stakeholders=`/`job_changes=` into its `build_customer_value_model`
  call.
- **The `/ui` static-mount basePath mismatch** (report 27's `api.py:393`
  `StaticFiles` mount + `ui/next.config.mjs`'s unset `basePath`): the built
  static export's `_next/static/...` assets 404 under the `/ui` mount
  prefix, so `make serve` + a browser at `/ui/` currently shows only the
  unhydrated server-rendered shell (confirmed live: JS/CSS chunk 404s,
  "Loading book…" never resolves). `next dev` mode (report 27's documented
  dev workflow, ports 3000/8000) is unaffected — this only affects the
  demo/prod static-mount path. Out of this dispatch's ownership map (it
  owns the Stakeholders drawer/evidence/recipient chip, not the UI build
  pipeline); flagging for whoever owns report 27's demo-serving path.
- **No live example of a fully-dormant Stakeholders drawer** (empty
  `stakeholders` array) exists in the current 181-account fixture book —
  every account has at least one CRM contact. The dormant microcopy path
  is code-present and mirrors every other drawer's pattern but is
  code-reviewed, not eyes-on-observed, for this specific case.

## Skeptical-reviewer paragraph

This SHOWS the wired person layer within the existing two views with no new
surface and no fabricated data — it does not add person-level navigation or
scoring, and the drawer is only as rich as report 32's live person data plus
the sim tenant's fixtures (accounts without a stakeholder-graph role show
that absence honestly, never a guessed role). The recipient chip reflects
report 32's deterministic resolution as-is; this dispatch renders it, it
does not second-guess or re-derive who should receive a motion. The
person-blind `_build_account_brief` gap (Tripwire 1 / first Owner Ask) means
the richness described here is proven end-to-end via `/sweep`'s work items,
not via a standalone account-brief fetch in isolation.

## Receipts appendix (K4)

- Baseline: `make eval` = 665 passed, 1 skipped, before any change.
- Phase 1: `make eval` = 668 passed, 1 skipped (`pytest -k "stakeholders_field or person_cited_evidence or recipient_chip_fields"` = 3 passed in isolation).
- Phase 2/3: `make ui-check` green (`✔ No ESLint warnings or errors`; `✓ Compiled successfully`; static export generated, 4/4 pages).
- Final: `make eval` = 668 passed, 1 skipped; `make lint hygiene status` clean; `git diff --check` exit 0.
- Commits (branch `codex/person-ui-depth`, off `062a3be`):
  1. `77f7d29` — Person UI: additive read-only API fields for the stakeholder drawer.
  2. `b96bcef` — Person UI: stakeholder-graph drawer, person-cited evidence, recipient chip.
- Live observations: quoted in "Observed behavior" above, reproduced across two independent server boots and both themes.
- Diff vs branch point: `git diff 062a3be --stat` → 7 hand-authored files / 352 insertions(+) / 19 deletions(-); 8 files including the generated transcript regeneration.

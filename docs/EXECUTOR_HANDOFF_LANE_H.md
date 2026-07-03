# Executor Handoff Addendum — Lane H: The Oversight Evidence Pack

Addendum to `EXECUTOR_HANDOFF.md` (rev 2); same protocol, §X triggers, and one-shot
autonomy contract. Small lane: one render-only feature, high leverage.

**Goal:** `make oversight-report` renders the ledgers the system already keeps into a
single **oversight evidence artifact** + a human-readable report — the document an
enterprise reviewer, auditor, or security team asks for when someone claims "humans
oversee this AI." Context: EU AI Act Article 14 human-oversight obligations (effective
August 2026) require documented oversight events with context, human response, and
timestamp; the gate ledger already records exactly that evidence class. This lane
*renders* it; it does not create new data.

**Hard framing rule (claim discipline):** this is an **evidence record**, not a
compliance certification. The report's own header must say: "This report demonstrates
that the system's ledgers contain the evidence classes an oversight regime requires. It
is not a compliance assessment and not legal advice." Any drift toward
"compliant/certified" language is a defect.

---

## H1 — The report generator

**Files owned (exclusive):** NEW `scripts/oversight_report.py` (or
`src/ultra_csm/oversight.py` if import needs demand it — pick one, not both), NEW
`tests/test_oversight_report.py`, Makefile target, one QUICKSTART line, one README line.
Render-only: **no write path to any ledger, gate, or config** (test this — the module
must not import gate mutation functions; an attempted write is the unsafe foil).

**Sections, each mapped to the ledger rows that evidence it** (every claim in the report
must be traceable to a specific artifact/row — include the row ids/refs inline):

1. **Human oversight events** — every verdict (approve/deny/revise) and
   acknowledge/dismiss event: actor principal, timestamp, target, payload hash, context
   ref. Grouped by action type and tier.
2. **Separation of duties** — which principals hold propose vs approve authority; proof
   that the proposing principal approved nothing (query, not assertion).
3. **Authority boundaries** — the action taxonomy with tiers and release conditions;
   which tiers auto-execute (with their audit trail) vs require human verdicts.
4. **Suppression & release history** — holds, blocking refs, overrides (with
   justification and actor), releases with their re-derivation outcomes. Loud record of
   every suppressed-then-released action.
5. **Degradation honesty** — template-fallback events, breaker trips and operator
   resets, `degraded_items` counts: evidence the system reports its own impairment.
6. **Quality measurement state** — judge validation status per dimension (κ + CI, from
   `judge_agreement.json`), current claim boundaries verbatim. Never restate numbers —
   quote the artifact.
7. **Autonomy provenance** — current tier assignments + any earned-autonomy
   promotion/demotion proposal artifacts with their evidence windows.
8. **Not instrumented** — a mandatory section listing evidence classes an oversight
   regime might want that this system does NOT yet record (e.g. reviewer response-time
   SLAs, second-reviewer events). IF a section has no ledger source → it goes here,
   honestly; NEVER render an empty section as implicitly satisfied.

**Output:** `demo_state/oversight_report.json` (machine-readable, `claim_boundary: sim`
while data is simulated) + `demo_state/oversight_report.md` (human-readable). Both
deterministic: same ledgers in → byte-identical reports out (tested twice).

## H2 — Demo + docs integration

- Add the report to `make demo`'s artifact bundle.
- One demo beat in the demo docs: "the audit question" — run the report, open §4, show a
  held-then-released expansion with its full provenance chain.
- README "Where it stands" table gains one row pointing at the report; `POSITION.md`
  already references the capability — link it.

## Decision criteria (IF/THEN)

- IF an evidence class has no ledger source → §8 "Not instrumented," never fabricate or
  approximate.
- IF report generation needs data transformation beyond grouping/formatting → STOP; the
  report renders, it does not compute (new derived metrics belong in the artifacts that
  own them).
- IF legal/compliance phrasing appears anywhere except the disclaimer → rewrite to
  "evidence record" phrasing.
- IF the same information exists in `STATUS.md` → the report links/quotes; no second
  source of truth.

## Lane H DoD

- `make oversight-report` deterministic (twice-identical), every claim carrying its
  ledger ref; §8 present and honest; disclaimer in the header of both outputs.
- No-write-path foil test green (module has no mutation imports; attempted write fails).
- In the `make demo` bundle; QUICKSTART + README lines added; universal suite + hygiene
  green; pushed.

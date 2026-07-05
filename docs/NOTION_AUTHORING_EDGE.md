# ADR: Notion Authoring Edge

## Status

Accepted. Stream 34 (Notion Authoring Edge, Wave Harvest-14).

## Context

The agent's org-agnostic voice/play knowledge (`org_pack.json`, `golden_corpus/*`,
tenant `playbooks.json`) and account-specific knowledge (`content_catalog.json`,
`handoff_notes/*.json`) are hand-edited JSON files today. A CSM authoring new plays,
voice rules, or account context has no interface friendlier than a JSON editor and the
existing schema tests. Notion is a plausible authoring front door for this population.

Two designs were on the table:

1. **Notion as a live data source.** The runtime reads Notion at request time, the way
   `agent1/sweep.py` reads CRM/telemetry connectors today.
2. **Notion as an authoring edge only.** A CSM authors in Notion; a repo-side build step
   captures that content and renders it into the same JSON shapes the agent already
   consumes, checked in via a normal PR.

## Decision

**Notion API: yes, as an authoring edge. Notion agents/live runtime reads: no.**

The flow is one-directional and build-time only:

```
CSM authors in Notion
  -> notion_reader.py (live pull, read-only) or a captured payload fixture
  -> scripts/notion_render.py
  -> knowledge/_generated/{org_pack.json, golden_corpus/*, tenants/<t>/playbooks.json,
                           tenants/<t>/content_catalog.json, tenants/<t>/handoff_notes/*.json}
  -> committed via PR
  -> ultra_csm.knowledge.load_org_pack / load_playbooks (unmodified) at agent runtime
```

Nothing in `src/ultra_csm/tick.py` or `src/ultra_csm/agent1/sweep.py` imports
`notion_reader` or `notion_render` — verified by a negative grep gate. If Notion is
unreachable, misconfigured, or an author makes a mistake, the agent's runtime behavior is
unaffected; the only failure mode is a PR that doesn't merge because a gate failed.

## The two-tier boundary

The two knowledge tiers this repo already distinguishes are preserved exactly, and the
renderer does not attempt to be the tier boundary's enforcer:

- **Agnostic tier** (`org_pack.json`, `golden_corpus/*`, `playbooks.json`): voice, plays,
  exemplars. No per-account fields allowed — enforced by
  `ultra_csm.knowledge._reject_forbidden_keys` at load time.
- **Account-specific tier** (`content_catalog.json`, `handoff_notes/*.json`):
  stakeholders, why-they-bought, gap-indexed content — schema-checked by
  `tests/test_content_catalog.py` / `tests/test_handoff_notes.py`.

If a Notion author places an account-specific fact (e.g. an `account_id` column) into an
agnostic-tier database, the renderer emits it verbatim — it does **not** strip forbidden
keys — and `load_org_pack` raises `OrgPackError` at load time. This is deliberate
(Decision Log, Stream 34, decision 3): the loader is the single source of truth for what's
forbidden, and silent stripping would hide the author's mistake instead of failing the PR
that introduced it.

## Loader-as-oracle

The acceptance test for every rendered artifact is the **unmodified** existing
loader/schema test:

| Tier | Oracle |
| --- | --- |
| Agnostic | `ultra_csm.knowledge.load_org_pack`, `load_playbooks` |
| Account-specific | schema assertions in `tests/test_content_catalog.py` / `tests/test_handoff_notes.py`, applied to generated output |

`src/ultra_csm/knowledge.py` and the two test files above are never edited by this
renderer or its tests. If a render doesn't pass unmodified acceptance code, the render is
wrong — never the oracle.

## Consequences

- Adding a new authoring field requires extending both the Notion database schema and
  `notion_render.py`'s mapping — there is no dynamic/schema-less path, by design (a
  renderer that accepts arbitrary Notion shapes could route around the loader's
  validation).
- `knowledge/_generated/` carries one committed sample tree (fixture-of-record) proving
  the pipeline runs; it is not a second copy of the demo universe and is never read by
  anything except this renderer's own tests and manual `make notion-render` runs.
- The live Notion pull (`notion_reader.live_authoring_payload`) is read-only and
  credential-gated (`ULTRA_CSM_NOTION_TOKEN`); absent that credential it raises
  `NotionReadError` rather than silently no-op'ing. As of 2026-07-05 no `NOTION_*`
  credential exists in `~/ultra-csm-live-creds.env`, so the live pull is an Owner Ask —
  see `docs/PROGRAM_REPORT_34.md`.

## What this does not prove

Schema-valid, loader-accepted output is not the same as semantically faithful output. A
rendered voice-rule paragraph or exemplar email can pass every gate while drifting from
what the CSM meant in the source Notion block; a mislabeled `addresses_gap` still passes
the account-specific schema check (it isn't cross-checked against the content itself).
These are residual risks accepted at the "taste"/"sampled review" level, not gated
mechanically — see the report's Skeptical Reviewer section.

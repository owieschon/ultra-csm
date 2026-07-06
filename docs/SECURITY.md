# Security

Status: active CSM security posture.

The scored security proof is `make scorecard-csm`. It is offline,
credential-free, and fails closed on hard-gate breaches.

## Enforced Properties

- **Grounding:** priority factors and Slot B text cite known evidence ids.
- **Tenant containment:** the sweep operates only on the requested tenant book.
- **Ambiguous identity:** 0/1/many account resolution never auto-picks on many.
- **Consent:** no customer draft is allowed without a consented contact.
- **Proposal-only posture:** customer-affecting actions stay pending proposals.
- **No authority minting:** the CSM agent principal cannot gain order-confirm
  authority through a proposal.
- **Prompt-injection resistance:** untrusted source text is data, not instruction.
- **Payload binding:** `ActionGate` binds proposals and verdict outcomes with a
  canonical payload hash.
- **Provenance:** every proposal is created through the platform session seam with
  tenant, actor, cause, and clock context.

## Live Lanes

`make regression-csm-live` requires credentials and is not a CI gate. It may be
used to capture Slot B drift evidence. Do not describe offline fixtures,
simulation artifacts, or seeded stochastic reports as production customer lift or
live model performance.

## Dependency Notes

The dependency surface spans two ecosystems: Python for the agent/API, and
npm for `ui/`, a real Next.js app (`ui/package-lock.json`, 366-package
lockfile) that ships in this tree. `cd ui && npm audit --audit-level=low`
(run 2026-07-05) reports 4 high + 1 moderate advisory, all on `next@14.2.x`
(one transitively on `postcss`). All
four `next` advisories require a running Next server (Image Optimizer,
Server Components request handling, Middleware/Proxy rewrites) to be
exploitable. This repo never runs one in any served path: `ui/next.config.mjs`
sets `output: "export"`, and `src/ultra_csm/api.py` mounts the resulting
static build (`ui/out`) at `/ui` via FastAPI's `StaticFiles` — a static file
server, not a Next process. Neither the `Makefile` (`ui-build`, `ui-check`)
nor CI ever invokes `next start`. As deployed, these advisories are not
exploitable. Residual exposure is confined to `make ui-dev` (`next dev` on
`:3000`), a local developer-only path never used in demo/prod serving.

**Addendum (2026-07-05, reachability analysis only — scan record above is
unchanged):** the npm-audit disposition and reachability analysis in this
section were verified live on this date. No new Endor/dependency scan was
run; the "Security Scanning" section below still reflects the 2026-06-29
Endor scan, which does not cover the `ui/` npm surface.

## Security Scanning

A fresh Endor scan (vulnerabilities, secrets, dependencies, SAST, GitHub Actions)
was last run on 2026-06-29. Dependencies, secrets, and known vulnerabilities
returned no findings. SAST surfaced 1 high and 9 medium, dispositioned honestly
rather than suppressed to green:

- **HIGH — `urllib.urlopen` with a non-literal URL** (`data_plane/live_smoke.py`).
  The connector smoke client issues requests to per-connector catalog/OAuth URLs.
  It is mitigated in code by a scheme allowlist that rejects any non-`http(s)` URL
  before the request, closing the `file://` local-read vector the rule warns about.
  The rule is pattern-based and still flags the `urlopen` call; we keep `urllib`
  (no added `requests` dependency) and do not suppress the finding.
- **MEDIUM x9 — error-message exposure (CWE-209).** Every instance is in an offline
  eval, CLI, or smoke path where the caller is the operator and surfacing the
  exception is the intended diagnostic (scorecard case-failure reporting,
  `set $ENV_VAR` operator hints, smoke HTTP error passthrough). None is an
  untrusted-user-facing endpoint; accepted as intended behavior.

No "Endor clean" claim is made — the disposition above is the claim.

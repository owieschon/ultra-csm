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

The console and JavaScript toolchain were removed from the agent repo, so the
dependency surface is Python-only.

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

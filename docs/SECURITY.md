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

The console and JavaScript toolchain were removed from the agent repo. No Endor
clean claim is made unless a fresh Endor scan is run.

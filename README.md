# Customer Action Control Plane

<!-- sourcebound:purpose -->
Ultra CSM is a work-in-progress, eval-first customer action control plane. It turns
tenant-scoped CRM, onboarding, product, support, and communication evidence into a
proposed next action while keeping that draft from becoming an unauthorized customer
commitment.

The repository is a synthetic reference build, not a production customer system. It
computes priority with deterministic rules, drafts a bounded next action, and stops at a
configured approval boundary. In credentialed paths, a bearer token maps to a principal
stored as human-kind and distinct from the proposing actor. The software verifies that
mapping, not whether a person is behind the token. The local no-auth demo uses a labeled
stand-in.
<!-- sourcebound:end purpose -->

**[Open the live read-only demo](https://ultra-csm.vercel.app/)**. Synthetic data, no login, customer sends disabled.
**Deterministic receipt:** [**24/24 hard gates**](eval/scorecard_csm.json) pass for
evidence, consent, tenant separation, grounding, injection defense, reproducibility, and
proposal-only behavior. **Governance receipts:**
[`tests/test_action_gate_machine.py`](tests/test_action_gate_machine.py) covers identity
kind, actor separation, consent, and payload binding;
[`tests/test_action_control_sandbox.py`](tests/test_action_control_sandbox.py) covers
tamper refusal, idempotent retry, and simulated commit.

![Customer Action Control Plane: evidence becomes a proposed customer action; release requires an approval record bound to the same payload hash](docs/customer-action-control-plane.svg)

## Why this exists

Customer teams can inspect CRM, onboarding, product, support, and communication systems
one at a time. The harder job is to reconcile those records into one explainable action
without letting a generated draft become permission. Ultra CSM makes the evidence path
inspectable and keeps authorization in code and durable state.

## Start here

| Your job | Start here |
| --- | --- |
| Run the fixture-backed system | [Quickstart](QUICKSTART.md) |
| Follow the local or hosted UI | [Demo walkthrough](docs/DEMO.md) |
| Inspect the input-to-receipt code path | [Representative reading path](docs/READING_PATH.md) |
| Understand the trust boundary | [Security posture](SECURITY.md) |
| Check what remains unproven | [Current limits](docs/LIMITS.md) |
| Navigate the rest of the documentation | [Documentation index](docs/README.md) |

## Run the read-only demo in 90 seconds

Open the hosted demo, select **Trailhead Logistics**, and inspect four stages:

1. tenant-scoped source records supply the evidence;
2. deterministic rules compute priority;
3. a bounded fixture writer proposes a draft with cited evidence;
4. the interface stops at the configured approval boundary.

The hosted build disables decisions and sends, so a click cannot be mistaken for an
approval. A non-read-only local build can record approve, deny, and revise verdicts, but
an approved verdict is not labeled sent or committed without a separate committer
receipt.

The `/ui/action-control/` route makes the boundary inspectable. The hosted build shows
frozen output from the executable proof and names its sandbox backend as unavailable. A
local sandbox can
approve one synthetic payload, commit it to a temporary outbox, retry idempotently, and
refuse tampering. See [the sandbox contract](docs/ACTION_CONTROL_SANDBOX.md).

## The control path

```text
tenant-scoped evidence
  -> deterministic value model and priority
  -> bounded draft (live model or labeled fixture/fallback)
  -> pending action proposal
  -> configured approval identity: verdict record
  -> payload-bound committer
  -> commit receipt
```

The system uses one shared customer value model rather than independent agents that can
disagree about account truth. Time-to-value, retention, and expansion are lenses over
that model. Product and Engineering handoffs share the evidence spine but do not bypass
the customer-action gate.

## Verify the claim

Run `make scorecard-csm-check` and `make eval`. The [quickstart](QUICKSTART.md) lists the
remaining local gates and prerequisites. None needs cloud credentials or customer data;
credentialed connector and model lanes stay separate.

## Claim boundary

The static demo, dev and trial connector receipts, single-labeler judge, and synthetic
renewal outcomes do not prove a production deployment or customer impact. The canonical
[limits page](docs/LIMITS.md) states each boundary with its direct evidence.

<!-- sourcebound:begin license -->
Apache-2.0 — see [LICENSE](LICENSE).
<!-- sourcebound:end license -->

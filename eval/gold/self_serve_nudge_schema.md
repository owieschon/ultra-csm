# Self-Serve Nudge Blind-Label Candidate Schema

`self_serve_nudge_candidates.json` is the Wave 1 candidate packet for OA-E3.
It is intentionally not final gold. Every row keeps `owner_label: null` until
the owner labels the packet blind.

Each row contains a product user, a checkpoint day, a deterministic identity
state, usage facts, frequency context, and the candidate motion/content/channel
that a future battery will ask the owner to accept, reject, or replace.

The eventual owner label object uses:

```json
{
  "mode": "nudge | none | abstain",
  "nudge_in": ["content_route"],
  "content_in": ["ss-content-first-value-checklist"],
  "channel_in": ["lifecycle_email"],
  "forbidden": ["campaign_enroll"],
  "notes": "blind labeler rationale"
}
```

`mode: none` is the correct no-touch outcome. `mode: abstain` is reserved for
identity or instrumentation cases where the system must not guess. `channel_in`
is first-class because Loops-style lifecycle email and Amplemarket-style
sequence enrollment have different customer pressure and must be graded.

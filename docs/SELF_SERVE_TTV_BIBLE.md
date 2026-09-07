# Self-Serve TTV Bible

Status: Wave 1 fixture bible for MP-E. Final oracle labels are blocked on
OA-E3, and the content taxonomy is blocked on OA-E4.

This fixture book models product-led users, not only CRM accounts. The join key
is signup email to CRM contact email. `exactly_one` can proceed to governed
proposal. `ambiguous` must abstain. `none` is normal for pure self-serve users
and must not be treated as failure.

## Value Paths

### Signup to Aha

The user signs up, lands in the activation surface, and should create the first
project or equivalent first-value object. Stalls are visible as repeated
activation-home views, no first project, admin setup abandonment, or import
failures. Candidate content routes include the first-value checklist, admin
setup guide, and import template walkthrough.

### Aha to Habit

The user has reached first value but remains a solo actor or fails to invite
teammates. A sequence enrollment can be appropriate only when usage shows a
habit-forming pattern and a broader team motion is needed. This is deliberately
more customer-pressureful than lifecycle email, so channel choice is graded.

### Habit to Conversion

The user shows upgrade intent after usage is established: pricing views, upgrade
modal opens, or workspace-limit pressure. The fixture keeps execution as an
enrollment record only. No LinkedIn, social, email, or provider step executes.

## Honesty Cases

Already-progressing users get no nudge. Churned-dead users get no nudge.
Frequency-capped users get no new nudge across either channel. Ambiguous
identity abstains. Pure self-serve identity with no CRM match can still receive
a lifecycle content route because no CRM account guess is required.

## Candidate Packet

The blind-label packet is
`eval/gold/self_serve_nudge_candidates.json`. It includes nudge-correct,
wrong-content, channel-foil, no-nudge, frequency-cap, ambiguous-identity, and
pure-self-serve rows. `owner_label` remains null until OA-E3 is complete.

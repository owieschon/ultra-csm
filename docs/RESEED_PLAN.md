# Re-seed Plan

Input to a future live-seeding program, not work executed here. Program 7
(`docs/PROGRAM_REPORT_7.md`) seeded the *thin* pre-Program-8 content into
real Rocketlane (Pinehill) and Gmail (all six arcs) orgs. Program 8
(`docs/PROGRAM_REPORT_8.md`) enriched that content offline, entirely in
fixtures. Those two facts together mean the live orgs today still carry
the old one-line-snippet bodies -- a future program needs to re-seed with
the enriched content. This document is that program's input spec.

## What changes for the seeder

Program 7's `seed_gmail.py` (`~/ultra-csm-corpus-runs/live-narrative-seeding-20260704/`)
built each IMAP `APPEND`'s body from the arc's old `_MESSAGE_SCHEDULE`
tuple's snippet field directly. Post-Program-8, every arc's
`*_email_thread()` fixture function already returns the full enriched body
in `payload.body.data` (via the new `narrative_content/` package) and a
derived one-line `snippet` (via `narrative_shared.derive_snippet`) --
the seeder's fix is mechanical: read `body.data` instead of re-deriving
its own short string, and thread the real `snippet` through unchanged.
No new seeder logic is needed beyond that field swap; the six arcs'
`*_email_thread(day)` functions are the single source of truth for both
fields already.

## New RFC822 construction requirements

The enriched bodies are multi-line plain text with blank-line paragraph
breaks and signature blocks -- `seed_gmail.py`'s `build_rfc822` must set
`Content-Type: text/plain; charset=utf-8` explicitly (Program 7's original
version relied on short single-line bodies where this was moot) and must
not collapse the body's newlines. No HTML part is needed; every exemplar
and email body authored in Program 8 is plain text by design.

## The future-dating wall, unchanged

Program 7's finding stands: Gmail's IMAP `APPEND` silently resets
`INTERNALDATE` to "now" for any future-dated message, and the product only
ever reads the `Date:` header, never `INTERNALDATE` -- so this remains
harmless, exactly as documented in `docs/LIVE_INTEGRATION_FINDINGS.md`.
Nothing about Program 8's content changes this; the seeder still needs the
`+timedelta(hours=9)` correction for `narrative_shared.rfc3339`'s
hour-offset convention that Program 7 discovered.

## SEED_DATE re-anchoring -- still an open, undecided dependency

Program 7's owner ask #3 is a hard prerequisite for this plan, not a nice
extra: `SEED_DATE` is fixed at 2026-06-21, and every real day that passes
shrinks the genuinely-backdatable window (the part of the 365-day arc that
is not yet in the future relative to whenever this program actually runs).
Re-seeding today would carry the same wall Program 7 hit, worse, since
more of the calendar has since moved into "future" relative to real time.
**This program should not proceed until SEED_DATE re-anchoring is decided**
(re-anchor to `today - N days` at run time vs. keep it fixed) -- flagged in
Program 7, still flagged here, still the owner's call.

## The distractor/noise layer -- live-mailbox-only, never in fixtures

Universe-deepening findings (Program 8) identified that a 100%-signal
mailbox is easy mode for any future content-understanding capability. The
enriched fixtures deliberately do NOT add noise (Program 8's invariance
gate requires every fixture message to be one the extractors' existing
logic already accounts for). A live re-seed, by contrast, is exactly the
right place to add distractor mail that was never appropriate in
fixtures, since it must never be asserted against by any battery:

- **Out-of-office auto-replies** on a plausible subset of CSM-authored
  messages (customer contact traveling), timed so they don't fall inside
  any bible checkpoint's trailing-latency window in a way that would
  register as a real reply (an OOO auto-reply is not a `CommunicationSignal`
  in the current extractor's model at all, since nothing marks it as
  such -- if a future live-read path naively counted every inbound message
  as a real reply, an OOO auto-reply would corrupt `reply_latency_trend`;
  this is worth a defensive fixture-level regression test before the first
  live re-seed, not just a seeding-time precaution).
- **A fictional industry newsletter** ("FleetOps Platform Digest" or
  similar), sent to every seeded mailbox on a monthly cadence, never
  replied to, never referencing any account-specific canon fact.
- **Rocketlane-style automated notification emails** ("Task assigned to
  you," "Phase due date changed") mirroring the real product's own
  transactional email pattern, timed to the actual Rocketlane phase/task
  events Program 7 already seeded.

None of this is fixture content -- it must be seeded directly into the
live mailbox by the re-seed script, alongside the real enriched messages,
never mirrored back into `narrative_content/` (which stays 100% signal by
design, matching the invariance gate's scope).

## Scope this plan does not cover

Live re-seeding of Rocketlane's case-verbatim corpus
(`narrative_content/case_verbatims.py`) is out of scope for Gmail
re-seeding specifically -- that content is keyed to CRMCase/Rocketlane-task
ids and belongs to a Salesforce/Rocketlane-side re-seed, which carries its
own hard walls (Salesforce `Case.CreatedDate` not writable, no live
`CRMCase` parser -- both already documented in Program 7's findings and
unchanged by Program 8). Calendar re-seeding is covered by Program 7's own
owner ask #2 (Calendar OAuth, now completed) and is a separate, smaller
follow-on this plan does not restate.

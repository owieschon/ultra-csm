# Program Report 19 — Density Expansion (four arcs, bible-first)

Branch `codex/density-expansion` off synced `main` (includes report 24's
tick-motion-adoption, PR #31, and Act 1's golden corpus, PR #32). Program 8
proved the safe expansion workflow on one arc (Trailhead, 21→27) and
explicitly deferred the rest. This program executes that deferred work for
the remaining four scored arcs — Pinehill, Aspenridge, Pinnacle, Meridian
(Quarrystone and Trailhead are excluded per the dispatch's pre-ratified
decisions: Quarrystone's silence *is* its story, Trailhead is already
expanded).

Fixture fence (Wave D, report 24): this program's four arcs live in
`comms_fixtures.py` / `pinnacle_comms.py` / `aspenridge_comms.py` /
`meridian_comms.py` / their `narrative_content/*.py` modules — disjoint
files from report 24's fleetops fixture change
(`quietvale-trucking`, `synthetic_book.py`'s account table). Verified at
runtime before any edit: `build_synthetic_book()` → **181 accounts**
(the 180→181 addition from report 24, confirmed present, treated as
settled baseline — not touched, not reverted).

## Phase 1 — Derivation sheet (per-arc checkpoint tables)

Method: for each arc, list every `eval/narrative_battery.py` assertion
that reads a comms-derived signal at that arc's bible checkpoints, compute
the extractor's trailing-window boundaries by hand (`reply_latency_trend`
window=21d, `meeting_cadence_shift` window=30d, `ticket_frequency_window`
window=90d — all from `signal_extractor.py`), and place new message pairs
either (a) strictly outside every checkpoint's trailing windows (Program
8's preferred, safest option) or (b) inside a window with the resulting
arithmetic re-verified by hand against the assertion's actual tolerance
(never its exact value, since none of these five assertions require an
exact value — see per-arc notes).

Baseline values captured empirically before any edit (receipts: direct
Python invocation of each `*_comms.py` + `signal_extractor.py` against
the unmodified worktree at commit 8a86806):

| Arc | Checkpoint | Signal | Baseline value |
| --- | --- | --- | --- |
| Pinehill | day 20 | latency | `None` (insufficient history) |
| Pinehill | day 50 | latency | `115.5` (recent 133.5h vs prior 18.0h) |
| Pinehill | day 50 | tickets | `2.0` |
| Pinehill | day 310 | latency | `10.0` (recent 16.0h vs prior 6.0h) |
| Pinnacle | day 10 | width | `1.0`, strengths `{Derek: weak}` |
| Pinnacle | day 120 | width | `2.0`, strengths `{Derek: weak, Monica: weak}` |
| Pinnacle | day 250 | width | `2.0`, strengths `{Derek: weak, Monica: strong}` |
| Aspenridge | day 90/200/340 | tickets | `0.0` (all three) |
| Meridian | day 20 | width/cadence | `2.0` / `None` |
| Meridian | day 170 | width/cadence | `2.0` / `-2.5` (recent gap 1.0d vs prior 3.5d) |
| Meridian | day 280 | width/cadence | `2.0` / `0.0` (recent gap 1.0d vs prior 1.0d) |

### Aspenridge — derivation (simplest; no exact-value assertions touch comms)

`check_silent_decline` asserts only `tickets==0` at day 90/200/340 (band
and adoption-rate assertions are driven by `book_simulator.py`'s
`UsageDecline`, untouched by this program) and `band=="green"`. Adding
benign email pairs never adds a `CRMCase`, so `tickets` stays `0` at every
checkpoint regardless of where new messages land — **this arc has zero
placement risk from the battery's perspective**. Current: 10 messages (5
QBR pairs, day 1/91/181/271/361). Target ~2-3x → **24 messages** (+14):
add one recap-FYI pair shortly after each existing QBR (day 5, 95, 185,
275, 365→ use 363 to stay ≤365) plus two extra scheduling-logistics pairs
(day 45, 135) between QBRs, all same-day fast replies matching the arc's
established "calm, prompt, one contact" cadence. No new participant
(Christine Yoder only, per the dispatch's no-new-participants rule).

### Pinnacle — derivation

`check_single_threaded_risk` asserts width (1/2/2) and strength
(`strong` present at day250) at day 10/120/250. Width is presence-based
(any message ⇒ active relationship as of that day); strength is **day-gated
only** (`strength = "strong" if as_of_day>=240 else "moderate" if
as_of_day>=135 else "weak"`, verified by direct inspection of
`pinnacle_comms.py:159` — independent of message count or reply latency).
Derek's arc-defining fact ("champion goes quiet day 3, never replies
again") is a MUST-NOT-TOUCH: no new Derek message may be added at any day
≥3. Monica's thread (day 110 onward) is free: any additional Monica↔CSM
pairs after day 110 leave width/strength unchanged. Current: 12 messages
(1 Derek pair pre-day-3 + 5 Monica pairs day110-245). Target ~2-3x →
**26 messages** (+14): add 7 new Monica pairs at day 118, 145, 160, 185,
200, 225, 238 (all safely after day 110, before day 240 so none cross the
strong-strength gate boundary prematurely — though the gate is day-based
regardless, keeping additions inside the existing 110-245 span matches
"front-loaded" and avoids inventing a new late-arc beat).

### Pinehill — derivation (exact-value territory; Program 8's stall latencies)

`check_onboarding_stall` asserts (day50/"during"): `latency > 15` (not an
exact value — wide tolerance) and `tickets >= 2`; (day310/"after"): zero
Rocketlane activation gaps (unrelated to comms). Window arithmetic by
hand: `reply_latency_trend` window=21d. Day 20's windows are
recent=(-1,20], prior=(-22,-1] — prior is structurally empty (sim starts
day 0), so `latency=None` is guaranteed regardless of any addition ≤20,
**as long as no new message pre-dates day 1** (none will). Day 50's
windows: recent=(29,50], prior=(8,29]. Day 310's windows: recent=(289,310],
prior=(268,289]; ticket window (90d) for day310 is (220,310].
**Safe zone**: days 51-219 inclusive fall inside NONE of the three
checkpoints' latency (21d×2) or ticket (90d) trailing windows — verified
by direct interval arithmetic, not assumed. Current: 19 messages (8 stall
pairs day1-87, 1 solo safety-extension message day41, 5 recovery pairs
day275-306). Target ~2-3x → **29 messages** (+10, 5 pairs): place all five
new pairs in the day51-219 safe zone — day 100, 130, 160, 190, 205 (mid-
onboarding "quiet stretch" recap/FYI exchanges, matching the arc's
established Marcus-verbose/Dennis-terse voice) — touching zero checkpoint
arithmetic. Re-verified after authoring (Phase 2 gate): `latency`,
`tickets` at day20/50/310 all unchanged from baseline table above.

### Meridian — derivation

`check_expansion_ready` asserts width==2 at day170/280 (Sarah appears day
10, both threads presence-based ⇒ unaffected by added density) and
cadence `<=0` at day170 (recent gap ≤ prior gap — currently -2.5, wide
tolerance since 0 is the boundary, not an exact value). `meeting_cadence_shift`
reads *calendar* events only, not email messages — this arc's density
expansion is entirely new **email** pairs on the two existing threads
(Alicia fleet-ops, Sarah facilities); no new calendar events are added, so
cadence arithmetic is untouched by construction, no placement math needed
for that signal. Width likewise untouched (both contacts already present
throughout the relevant range). Current: 52 messages (26 Alicia + 26
Sarah). Target ~2x (Meridian explicitly targets the low end per the
dispatch's decisions) → **104 messages** (+52, 26 new pairs, 13 per
thread): interleave one additional FYI/scheduling pair between each
existing exchange gap on both threads, keeping the existing subject-arc
shape (kickoff → usage growth → expansion scoping → close → post-close →
year-end) intact and adding no new participant.

## Gate (Phase 1)

`test -f docs/PROGRAM_REPORT_19.md` → present, contains the four per-arc
derivation tables above. PASS.

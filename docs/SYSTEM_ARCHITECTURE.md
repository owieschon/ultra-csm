# Ultra CSM: System Architecture

## The Problem

A Customer Success Manager owns 30–80 accounts. For each one, they need to know: is
this customer getting value? Are they at risk? Is there an opportunity to grow? What
should I do about it? That requires assembling context from CRM, CS platform, product
telemetry, onboarding tools, support tickets, billing, relationship data — and then
making a judgment call about what matters and what to do next.

They also need to manage their own day: read email, prepare for calls, log activities,
track follow-ups, prioritize their time. And they need to be the bridge between
customers and the rest of the company: aggregating product feedback, briefing sales on
expansion opportunities, giving marketing customer stories, bringing real customer
context to roadmap discussions.

Almost all of this is manual today. The context assembly is manual. The change
detection is reactive — the CSM notices, or doesn't. The activity logging is manual.
The cross-functional communication is manual. A CSM with 50 accounts doesn't have time
to do all of it well. The accounts that get attention are the ones that are loudest, not
the ones that need it most.

The naive automation is to build agents that do what CSMs do. This fails because the
most important parts of the job require judgment, timing, taste, and trust. You can't
automate a save call. You can't automate the decision to ask for a reference. You can't
automate the tone of a check-in when you know the champion is having a bad quarter.

But the majority of the CSM's time isn't spent on judgment calls. It's spent on
assembly, computation, detection, logging, drafting, and coordination — work that
doesn't require judgment but consumes the time that judgment needs.

---

## What the CSM Becomes

The system handles context assembly, health computation, change detection, activity
logging, call and email summarization, feedback aggregation, internal drafting, and
cross-functional routing. It detects meeting attendee changes and frequency shifts from
calendar data. It tracks stakeholder engagement trends from communication patterns. It
summarizes every call and drafts every follow-up. For routine actions where it's proven
reliable, it acts without waiting.

What's left for the CSM is irreducibly human:

**Live presence.** The system prepped the call and will summarize it. But during the
conversation — when the customer says something unexpected, when the tone shifts, when
the discussion requires a pivot no prompt anticipated — the CSM is thinking on their
feet. Knowing what question to ask next, when to probe deeper, when a surface answer
isn't the real answer. Knowing when to sit in the silence instead of filling it. The
system can suggest questions in the call prep. The CSM reads the moment and chooses the
one that matters — or asks one that wasn't on any list. That real-time interrogative
judgment is something no post-hoc summary captures and no pre-call brief replaces.

**Unrecorded context.** The things customers say off the record. "Between us, our CEO
wants to consolidate vendors." "My boss is leaving but it hasn't been announced." This
never enters any system. The CSM carries it and acts on it. It's often the most
important information about the account.

**Trust as a human asset.** The customer takes the reference call because of the
relationship, not because a score said to ask. They give honest feedback, warn about
competitive evals before they're official, advocate internally on the vendor's behalf —
because they trust the person. Trust is earned through consistent human presence over
time. The system can support the person who builds trust. It can't be that person.

**Internal advocacy with personal credibility.** The system provides the data and drafts
the summary. The CSM walks into the room and says "we will lose this account if we don't
fix this." That carries weight because of who is saying it — their track record, their
relationships with Product and Engineering and Leadership, their judgment about what's
real versus what's noise. The system provides the ammunition. The CSM's credibility is
what makes it land.

**The creative strategic read.** Not "the data says X" — the system handles that. The
CSM's contribution is "given everything I know, including what's not in any system, the
play here is Y." The decision to position the expansion conversation as a cost-reduction
story because they know this executive cares about efficiency, not features. The
decision to hold off on the save play for two weeks because they know the customer is
in the middle of a board cycle and can't focus. Strategy that integrates data with
context the data doesn't contain.

This changes the role. The CSM stops being an administrator who also builds
relationships and becomes a strategist who only builds relationships. The operational
load drops far enough that they can handle significantly more accounts without losing
depth on the ones that need it. The accounts running smoothly are monitored by the
system. The accounts that need a human get a human who isn't exhausted from data entry
and CRM hygiene.

---

## What the System Does

The system operates in three modes:

**Customer intelligence.** The system watches every account, computes health across
multiple dimensions, detects changes and risks, and proposes customer-facing actions
grounded in specific evidence. For routine actions where the system has demonstrated
reliability — like sending a standard check-in to a healthy account — it acts
autonomously. For actions requiring judgment — like escalating a save play or pitching
an expansion — it proposes and the human decides. The system earns autonomy by proving
reliability, measured from its own track record. Trust is graduated, not binary.

**CSM operations.** The system manages the CSM's day. It classifies and prioritizes
incoming email, prepares account briefs before every meeting, logs activities to CRM
automatically, surfaces upcoming commitments, and assembles the CSM's daily priority
list. This is autonomous from the start because none of it touches the customer. It's
the system working as an operating layer — eliminating administrative work so the CSM
can spend their time on relationships.

**Internal collaboration.** The system is the bridge between customers and the rest of
the company. It aggregates product feedback across accounts weighted by revenue and
health, routes structured intelligence to Product, Marketing, Sales, and Engineering,
drafts internal communications, and tracks whether feedback was acknowledged and acted
on. When Product ships a feature that 15 accounts were waiting for, the system connects
the feedback to the resolution and proposes outreach to those accounts. The CSM reviews
and sends internal communications, but the aggregation, weighting, and drafting are
automatic.

---

## The Value Model

The instinctive design for a CS agent system is independent agents: one for onboarding,
one for risk, one for expansion, one for cohort analysis. Each gathers data, computes
health, and makes recommendations independently. This duplicates the hard part —
understanding whether an account is healthy — and creates conflicts. An account can be
simultaneously at risk and an expansion candidate. Which agent owns it?

Instead: one shared, deterministic Customer Value Model computes account health once.
Every downstream component reads the same model. Nobody re-derives health.

### The Four Rails

The value model scores health on four dimensions. The first three are leading indicators.
The fourth is the thing that actually matters.

**Usage** — activity. Are people logging in, completing workflows, engaging with the
product? Usage tells you whether the product is part of the customer's daily work.

**Penetration** — depth and breadth of adoption. Not just seat count, but stakeholder
coverage: is there an executive sponsor who defends the renewal? An admin who maintains
it? Operators who depend on it daily? Beneficiaries whose metrics improve because of it?
Penetration measured as "users vs. seats" misses the point. Penetration measured as
"how many self-sustaining value loops exist" captures stickiness. Three complete value
loops (sponsor + admin + operators + measurable outcome for each) is sticky. Usage
across five departments with no complete loop is fragile.

**Feature depth** — capabilities used vs. entitled. A customer paying for the full
platform but using one feature has unrealized value — which is both an expansion
opportunity and a churn risk, depending on whether they know what they're missing.

**Outcome** — whether the customer achieved what they bought the product for. This is
the hardest to measure and the most important. High usage with no verified business
outcome is activity without value. "Outcome unknown" is a tracked state, never inferred
from usage. The system does not assume that because they're logging in, it's working.

### The Diagnostic Divergence Layer

Cross-rail contradictions are the highest-value signals. A single-rail view is blind to
all of them.

Health score says green but usage is low — the health model is lying, or measuring the
wrong thing. High usage concentrated in one person — activity looks strong but it's
champion-loss fragility. Usage is high but outcomes are unverified — the customer is
busy inside the product but nobody has confirmed it's producing the results they bought
it for. Implementation is on track but health is already green — the health model is
prematurely optimistic and the earliest risk signal is being masked.

Each divergence is deterministic, fires only on positive evidence (missing data never
fabricates a signal), and is traceable to named factors the CSM can evaluate.

---

## Customer Intelligence: Lenses

The "agents" in a CS system are not independent decision-makers. They are thin
projections of the shared value model — lenses that view the same health data through
different concerns. Each lens asks a different question about the same account, proposes
a different kind of action, and frames the outreach differently.

### Time-to-Value

Views the model through onboarding and activation. Milestone completion from the
implementation tool. Activation signals from product telemetry. Training completion.
Setup step progress.

Asks: is this account stalled on the path to first value?

Proposes: an intervention to unblock — reach out about the specific stall, suggest
training for the enablement gap, escalate internally if the blocker is on our side.

### Risk / Retention

Views the model through trajectory and fragility. Health trend over time — improving,
stable, or declining? Champion engagement — is the primary contact still active?
Renewal proximity — how close is the renewal, and is the relationship strong enough?
Support escalation patterns — are unresolved tickets accumulating? Single-threaded risk
from the divergence layer.

Asks: is this account at risk of churning or contracting?

Proposes: a relationship intervention calibrated to severity — casual check-in for
early signals, executive escalation for imminent risk, a save play for accounts that
need real commitments to recover.

### Expansion

Views the model through unrealized value. Consumption approaching entitlement — they're
using almost everything they've paid for and may need more. Underused capabilities —
they're paying for features they haven't adopted, which is either an enablement
opportunity or a cross-sell setup. Sustained health — the relationship is strong enough
to have the expansion conversation without it feeling tone-deaf.

Asks: is there a growth opportunity in this healthy account?

Proposes: an expansion play — positioned around value already realized, with specific
data on what comparable accounts achieved after expanding. The system builds the case.
The CSM reads the organizational dynamics and decides whether the timing is right.

### Why Lenses, Not Independent Agents

Because they share the model, a single account can be in view of several lenses at once
without conflict. An account with a single-threaded champion is simultaneously a Risk
case (champion departure would be catastrophic) and an Expansion case (low stakeholder
penetration means room to grow). The same model fact — one active contact — produces two
different proposed actions through two different lenses. Both go to the same CSM, who
decides which to act on first.

This can't work if each agent independently re-derives health. One might score the
account as red, another as green, and neither would know the other exists. One model,
shared, with thin projections, eliminates this.

Each lens has: a projection function that selects and weights the relevant factors from
the model, a filter chain of sequential gates that determine whether to propose an
action, a drafting slot where the LLM writes the outreach from grounded evidence, and a
governance tier that controls what happens next.

---

## Trust and Autonomy

The system isn't a suggestion box. It's an actor that earns increasing autonomy by
demonstrating reliability.

### The Governance Gate

Every customer-facing action enters the system as a proposal: a structured payload
describing what to do, why, grounded in specific evidence. The payload is
cryptographically bound at creation — what gets approved is exactly what gets executed.
If the payload is modified between approval and execution, the binding check fails and
the action is blocked.

The system operates under an agent identity — a principal in the permission model. That
principal can propose actions. It structurally cannot hold the permissions required for
high-judgment actions, and it cannot grant itself those permissions through a proposal.
This is enforced at two layers — application code and database constraints — so a bug in
either one is caught by the other.

### Graduated Autonomy

Not all actions require the same level of oversight. The system recognizes a spectrum:

**Autonomous** — actions the system executes without waiting for approval. These are
bounded, reversible, and low-risk. Logging a CRM activity note. Sending a routine
check-in to a healthy account with a consented contact where the draft passed quality
validation. Updating an internal health score. These are actions where the cost of
getting it wrong is small and recoverable, and the cost of waiting for approval
defeats the purpose of automation.

**Supervised** — actions where the system proposes and a CSM approves. The system
assembled the context and drafted the outreach, but the CSM decides whether this is the
right action, the right moment, and the right framing. Risk interventions. Expansion
plays. Anything where the relationship context — which the system doesn't fully have —
materially affects whether the action is appropriate.

**Restricted** — actions that require additional authorization beyond the CSM. Executive
escalations. Pricing concessions. Commitments that bind the company. Save plays that
require product or engineering involvement. These go through the governance gate at a
higher tier, requiring approval from a CS leader or cross-functional stakeholder.

### Earning Trust

An action type doesn't start autonomous. It starts supervised. The system accumulates
evidence of its own reliability for each combination of action type and situation:
approval rate (how often is this kind of proposal approved without modification?),
modification rate (when it is modified, how much changes?), outcome quality (when the
system acted or the CSM approved, what happened to the account?).

When the evidence meets a threshold — defined by CS leadership, not the system — the
action type can graduate. "Routine check-in drafts for green-health accounts are
approved unmodified 97% of the time and outcomes are neutral-to-positive. Recommend
graduating to autonomous." That graduation is itself a governed change — a CS leader
approves the policy, not the system.

The trust is continuously monitored. The commitment tracker and the cohort analyst watch
for degradation: if autonomous actions start producing worse outcomes, the system (or a
human reviewing the data) can pull autonomy back. Trust is earned, measured, and
revocable.

---

## The CSM Operating Layer

The customer intelligence layer handles accounts. The operating layer handles the CSM's
day. It's autonomous from the start because everything it does is internal — it organizes
the CSM's work without touching any customer.

### Inbox Intelligence

Email is classified by account, summarized, linked to the value model context, and
prioritized. An email from a champion at a red-health account isn't the same as a
routine reply from a green account. The system knows this before the CSM opens their
inbox. Action items and commitments are extracted automatically. Threads are linked to
the relevant account context so the CSM doesn't have to context-switch between their
email client and their CS platform.

Response time patterns are tracked as engagement signals — a contact who used to reply
within hours and now takes days is a leading indicator the value model should see. The
system detects this from communication data without the CSM needing to notice it.

### Calendar and Meeting Intelligence

Before every customer meeting, the account brief is already assembled. Health status,
recent changes, open cases, upcoming milestones, conversation history, relevant
proposals — everything the CSM would otherwise spend 15 minutes pulling together from
multiple systems. The brief is ready when the calendar event starts, not when the CSM
remembers to prepare.

After the meeting, the system summarizes the call — key topics, decisions, action items,
sentiment — and logs the activity to CRM. The CSM reviews the summary, adds the context
that only they caught (the unrecorded aside, the shift in tone), and moves on.

The system also tracks meeting patterns as signals. Attendee changes — who was on the
call, who dropped off, who's new. Frequency shifts — weekly syncs that became monthly,
or a sudden request for a call outside the regular cadence. These are stakeholder
engagement signals that feed directly into the value model. The CSM doesn't need to
notice that the VP stopped attending. The system flagged it the first time they were
absent.

### Priority Assembly

The daily digest isn't a list of proposals. It's the CSM's entire day, reordered by what
actually matters based on everything the system knows. Which meetings involve the
highest-priority accounts. Which emails came from at-risk contacts. Which follow-ups are
overdue. Which commitments are due this week.

The system doesn't just surface account intelligence — it integrates it with the CSM's
actual schedule and communication to produce a single prioritized view of their workday.

### Activity Logging

The system observed that an email was sent, a call happened, a meeting occurred. It logs
the CRM activity record. The CSM never manually enters "had a call with Acme on
Tuesday." Every activity that can be captured from system events — email sent, meeting
held, document shared — is logged automatically. The CSM adds context where it matters
("discussed migration timeline, customer concerned about Q4 deadline") but doesn't do
data entry.

### Commitment Surfacing

The CSM told Acme they'd send the ROI report by Friday. The system knows because it
extracted the commitment from the call summary or the email thread. Wednesday, it
surfaces it: "this is due in two days. Here's the usage data for the report."
Commitments aren't tracked in a separate system the CSM has to maintain. They're
extracted automatically from call transcripts, emails, and meeting summaries, and
surfaced when they're becoming due.

This works in both directions. The system also tracks what the customer committed to —
"we'll get the technical team trained by end of month" — and flags it when the deadline
passes without the corresponding activation signal in telemetry.

---

## The Internal Bridge

The CSM is the only person in the organization who talks to customers regularly and
understands their operational reality. That makes them the bridge between customers and
every internal team. Today, being the bridge is manual and time-consuming: compiling
feedback spreadsheets, writing Jira tickets, drafting Slack summaries, preparing slides
for product meetings. The system handles the aggregation and drafting so the CSM can
focus on the substance.

### Feedback Aggregation

As the system processes accounts, it encounters the same patterns across the population:
the same product limitation causing onboarding stalls in multiple accounts, the same
feature request appearing in CSM reflections, the same integration friction point
appearing in support tickets. The system aggregates these automatically, weighted by
account ARR, health, renewal proximity, and segment.

"14 accounts representing $3.1M ARR have hit this API limitation. Three have renewal
risk partially attributed to it. Highest-impact accounts: Acme ($800K, renewal in 60
days), Nova ($650K, health declining)." That's a product feedback summary the CSM didn't
have to compile.

### Structured Routing

Feedback is tagged by product area, weighted, linked to similar feedback, and routed to
the right team in the right format. Product gets feature requests ranked by revenue
impact and churn risk. Engineering gets bug patterns ranked by frequency and severity.
Marketing gets signal about which use cases and value propositions are resonating in the
field. Sales gets competitive intel and expansion context aggregated from what CSMs are
hearing in conversations.

The routing isn't broadcast — it's targeted. Product doesn't get the competitive intel
dump. Sales doesn't get the bug report. Each team gets the intelligence that's relevant
to their decisions, in a format they can act on.

### Internal Drafting

The system drafts internal communications from data it already has. The weekly product
feedback summary. The competitive landscape update. The customer health executive
summary for the QBR. The internal account brief for Sales when they're working an
expansion deal. The CSM reviews, edits, and sends — but the assembly and first draft are
automatic.

### Closing the Internal Loop

The most valuable version of the bridge isn't one-directional. It's a loop.

Customer feedback goes to Product. Product ships the feature. The system detects the
change — a new capability appears in the entitlement catalog or the telemetry schema.
It identifies which accounts were waiting for it (because it tracked the original
feedback). It proposes outreach to those accounts: "the thing you asked for shipped —
here's how to enable it." The CSM doesn't have to remember which accounts wanted what.
The system tracked the feedback, tracked the resolution, and connected them.

When the CSM brings customer context to a product roadmap discussion, the system
provides the supporting data in real time: "12 accounts representing $2.4M ARR have
requested this feature. Three of them have renewal risk partially attributed to this
gap. Accounts that adopted the workaround have 20% higher adoption rates than those that
didn't."

---

## The Deterministic Spine

The architecture enforces a hard boundary between what the system proves and what the
LLM approximates.

Everything up to "here is the priority-ordered list of accounts that need attention,
with specific evidence for each" is deterministic. The value model, the lens
projections, the filter chains, the factor scoring, the governance gate — all
reproducible, all auditable, all testable with exact assertions. Run the same inputs,
get the same outputs, every time.

The LLM lives in exactly two confined slots:

**Slot B — narration and drafting.** Given a structured evidence bundle with specific
citations, write the reason this account needs attention and draft the customer
outreach. The LLM cannot invent evidence, cite facts that aren't in its input, or
override the deterministic priority. Contract validation enforces this: every evidence
ID the LLM cites must exist in the input bundle, known injection phrases are blocked,
and drafts requiring customer consent are blocked if no consented contact exists. The
LLM phrases the output. It doesn't make the decision.

**Slot A — classification where a rule can't (deferred).** Some inputs require judgment
to classify: mapping a job title to a stakeholder archetype (is "VP of Digital
Transformation" an executive sponsor or an operator?). When this arises, the LLM
classifies behind a curated taxonomy with a mandatory "unknown" category. It cannot
silently guess. The taxonomy is authored by humans, versioned, and the LLM's
classification accuracy is measured before it's trusted.

A non-deterministic instrument must never own a deterministic gate. That boundary is the
architectural discipline that makes the system trustworthy. The LLM is treated as a
measured instrument — its noise is characterized, its failure modes are catalogued, its
reliability is reported with confidence intervals, not asserted.

---

## The Data Layer

### Connectors and Contracts

The system reads from CRM (Salesforce, Attio, HubSpot), CS platforms (Gainsight),
onboarding tools (Rocketlane), relationship intelligence (Centralize), product
telemetry, billing, and support. Each connector maps external data into a shared set of
typed contracts — rigid data structures that every downstream component depends on.

The contract layer is the boundary. A connector handles authentication, pagination, rate
limiting, schema quirks, and field mapping. Above the contract layer, no component knows
or cares which CRM is connected. Swap Salesforce for HubSpot, and nothing above the
connector changes. The value model sees the same account, contact, case, and opportunity
shapes regardless of origin.

Three interface boundaries define the connectors: CRM (accounts, contacts, cases,
opportunities, activities), CS platform (company health, CTAs, success plans, adoption
summaries), and product telemetry (entitlements, usage signals, time-to-value
milestones). Each is a protocol — a set of methods with typed inputs and outputs — that
any connector must satisfy.

Connectors graduate through a readiness lifecycle: specification → recorded API response
shapes → credential smoke test → live schema discovery → source mapping proposal →
human confirmation for ambiguous fields → frozen configuration. Nothing auto-promotes.
Each stage has a verifiable artifact.

### Snapshots and Trajectory

The system doesn't need a real-time event stream. CS teams work in daily rhythms —
morning triage, not incident response. Change detection works by comparing snapshots.

Each time the system evaluates the book, it persists a snapshot of every account's value
model output: health band, scores, factor values, lens priorities. Trajectory is a
query over stored snapshots: is health improving, stable, or declining? How fast? Over
what window?

This activates signals that a single point-in-time read can't produce. "Usage declined
15% over the last 30 days" is a fact derived from comparing two snapshots, not a
real-time event. "Health has been green for six consecutive evaluations" is a
sustained-state fact. The Risk lens reads trajectory to detect creeping deterioration.
The Expansion lens reads sustained health to validate that the timing is right for a
growth conversation. The threshold for "declining" is configurable per account tier —
a large enterprise account with a 5% usage decline might warrant intervention, while
a startup-tier account with the same decline might be normal variance.

---

## The Feedback Loop

### The Commitment Tracker

The governance gate records that a proposal was approved. But it doesn't record what
happened next. Did the CSM send the email? Did the customer respond? Did the situation
improve?

Without this, the system is a recommendation engine. It proposes the same way forever,
with no way to learn whether its proposals lead to good outcomes.

The commitment tracker closes the gap. When a proposal is approved — or when the system
acts autonomously — a commitment is created. Three things are recorded over time:

**What was done.** Which may differ from what was proposed — the system suggested an
email, the CSM called instead because they know this customer doesn't read email. For
autonomous actions, what the system actually did. The difference between "proposed
action" and "action taken" is itself useful data.

**What happened.** Did the situation improve, stay the same, get worse, or is it too
early to tell? Measured against the factors that triggered the action: if the system
flagged declining usage and a check-in was sent, did usage recover?

**What the CSM thinks.** A free-form reflection. "We lost them because we didn't act on
the champion departure signal fast enough." "The system was right about the risk but
wrong about the approach — this customer needed an executive-to-executive call, not a
CSM check-in." "The expansion data was accurate but the timing was terrible — they'd
just gone through layoffs."

The reflection is the most valuable field in the system. It's the CSM's judgment about
what actually happened — not what the data says happened — and it's the ground truth
that the cohort analyst learns from.

### The Cohort Analyst

This is the component that makes the system compound rather than static. It operates at
a fundamentally different altitude from the lenses: population-level, not per-account.

The lenses ask: what should we do about *this* account? The cohort analyst asks: across
all accounts, what's working?

It consumes the accumulated data: account snapshots over time, proposals and their
outcomes from the commitment tracker, CSM reflections, factor distributions across the
population, feedback aggregation patterns from the internal bridge. It runs analysis on
a cadence:

Which onboarding patterns predict fastest time to first value? Which CSM interventions
actually correlate with health recovery (and which are activity without impact)? Which
risk signals appear earliest before churn — the signals the system could detect months
before the CSM noticed? Which expansion approaches succeed in which segments? Where do
the system's own detection rules have high false-positive rates — proposals the CSMs
consistently dismiss, indicating the rule is noisy? Where are proposals consistently
modified before approval — indicating the draft template needs improvement? Which
autonomous actions are producing worse outcomes than supervised ones — indicating trust
was granted too early?

It proposes system changes: adjusted detection thresholds, new scoring weights, updated
playbook recommendations, recalibrated rules, autonomy adjustments. But it never
auto-applies them. System changes go through the same governance gate at a higher tier
— a CS leader reviews and approves, not individual CSMs. Nothing enters the system's
operating logic without human validation.

The cohort analyst also feeds the internal bridge. Population-level patterns — "accounts
in healthcare have 40% longer onboarding times" or "the workflow builder feature has the
strongest correlation with expansion" — are exactly the intelligence that Product,
Marketing, and Leadership need, and the system has it.

Discipline: the cohort analyst carries a causation-and-leakage bar. Correlation is not
causation. A pattern discovered in the data is reported with sample size, confidence
interval, and explicit confounders — never as a bare assertion. Demographics are scoped
to role and persona, never protected attributes. Recommendations are recommendations,
never auto-applied.

### The Flywheel

```
  Lenses detect signals and propose (or take) actions
                          ↓
  CSMs supervise, supplement, and act
                          ↓
  Commitment tracker records what was done and what happened
  Snapshot store accumulates account trajectories
  Internal bridge captures cross-functional feedback loops
                          ↓
  Cohort analyst discovers what works, for whom, at what stage —
  and what doesn't (noisy rules, premature autonomy, ineffective templates)
                          ↓
  System proposals: new thresholds, updated rules, better playbooks,
  autonomy adjustments, product intelligence for internal teams
                          ↓
  CS leader approves or rejects
                          ↓
  Approved changes update the system's operating configuration
                          ↓
  Lenses detect better, draft better, and earn more trust next time
```

This is the difference between a tool and a system. A tool gives the CSM better
information. A system gives the CSM better information *and gets better at giving
information because the CSM uses it.*

---

## The Knowledge Base

When Slot B drafts outreach, it works from a structured evidence bundle: the account's
value model output, the lens-specific context, the specific factors that triggered the
proposal. But evidence alone doesn't produce good outreach. The CSM needs institutional
context: what approaches have worked for this kind of situation before?

The knowledge base provides structured retrieval. Playbooks are authored by CS
leadership and indexed by situation type — which lens, which filter chain outcome, which
account characteristics. "When you see a stalled onboarding with a training completion
gap, here's the recommended approach." "When a champion goes quiet 90 days before
renewal, here's the escalation playbook."

This is curated content, not RAG. Playbooks are versioned, reviewed, and intentionally
authored. The cohort analyst can propose new playbooks based on discovered patterns, but
they enter the knowledge base only after human approval. The knowledge base is where
institutional knowledge lives explicitly rather than in people's heads.

Slot B receives relevant playbooks as part of the evidence bundle. The prompt references
them as structured context — "recommended approaches for this situation" — not as
instructions the LLM must follow. The CSM decides whether the playbook fits this
specific relationship. The LLM narrates. The human judges.

---

## The Daily Experience

Every morning, the CSM's day is already assembled.

The **priority view** integrates everything: which accounts need attention and why
(from the lenses), which meetings are coming up and what the context is (from the
calendar prep), which emails need response and which can wait (from inbox
intelligence), which commitments are due this week (from the commitment tracker), which
proposals are awaiting their verdict. It's not three separate tools. It's one view of
the CSM's day, ordered by what matters.

An account in view of multiple lenses appears with all its contexts together. "Acme
Corp: declining champion engagement (risk, priority 72) AND unused enterprise
entitlements (expansion, priority 45)." The CSM sees the full picture and decides which
concern to address first. Maybe the relationship needs stabilizing before any expansion
conversation. Maybe the expansion conversation is actually the way to re-engage the
champion. That's judgment. The system can't make that call.

During the day, the system works in the background: logging activities as they happen,
updating account context after meetings, surfacing new signals as data comes in,
aggregating feedback for internal routing. The CSM's attention stays on the customer
conversations and judgment calls. The system handles the bookkeeping, the assembly, and
the cross-functional communication that would otherwise eat their afternoon.

At the end of the day — or the end of the week — the system prompts for the reflections
that close the loop. What happened with the accounts you acted on? What worked? What
didn't? The answers enter the commitment tracker and feed the cohort analyst's learning
cycle.

---

## What This Measures

The system evaluates itself at two levels, and keeping them apart is the point.

**The deterministic spine** — exact, zero-tolerance. The value model computes the same
scores from the same inputs every time. Lens projections are reproducible. Filter chains
produce the same results. Governance invariants — tenant isolation, consent enforcement,
authority separation, payload binding — are proven by tests that fail if you break them.
For every component, an unsafe variant exists: a version that deliberately cuts corners,
fabricates evidence, or skips consent checks. That unsafe variant must fail the safety
gates. This proves the gates actually catch bad behavior, not just that the good
behavior happens to pass.

**The non-deterministic LLM slot** — characterized, not trusted. Slot B output is
graded by a quality judge on specific dimensions: does the draft cite real evidence from
the bundle? Is it relevant to this specific account? Does it match the appropriate tone
for the situation? Does it respect safety boundaries? The judge itself is a measured
instrument — its reliability is characterized with blinded adversarial test sets,
run-to-run noise measurement, and fail-closed aggregation before anyone trusts its
output. When the judge says a draft is good, we know how often the judge is wrong, and
we report that rate honestly.

**Autonomy health** — continuous monitoring of autonomous actions. Outcome quality by
action type. Comparison to supervised baselines. Drift detection: is an action type that
graduated to autonomous still performing at the level that earned that trust? The cohort
analyst watches for degradation and can propose pulling autonomy back.

The distinction between the first two matters because conflating them — treating LLM
output with the same confidence as deterministic computation — is how AI systems produce
confident-sounding nonsense. The deterministic spine is proven. The LLM slot is
measured. They are different claims with different evidence standards, and the
architecture enforces the boundary between them.

---

## The Lifecycle Coverage

Mapping the system's three modes to the customer lifecycle:

**Sales-to-CS Handoff.** The data layer assembles the handoff brief: deal record,
relationship map, buyer committee, success criteria promised, risk profile from deal
characteristics. The internal bridge formats the brief from AE to CSM. The CSM reads
the brief, talks to the AE for the context that isn't in the CRM, and sets the
onboarding strategy.

**Onboarding.** The Time-to-Value lens detects stalls — overdue milestones, flat
activation metrics, inactive key users. It proposes interventions grounded in specific
evidence of what's stuck and who's responsible. The operating layer tracks
implementation tasks, logs activities, and surfaces training completion status. The CSM
manages the relationship through the messy, non-linear reality of getting a customer
live.

**Steady State.** All three lenses run continuously. The operating layer manages the
CSM's daily workflow — inbox, calendar prep, activity logging, commitment tracking. The
internal bridge aggregates feedback and routes intelligence. The cohort analyst discovers
population patterns. The CSM filters signal from noise, has the conversations, logs the
new information that only comes from being in the relationship, and contributes customer
context to cross-functional decisions.

**Expansion.** The Expansion lens detects unrealized value in healthy accounts. It
assembles the case with data. The internal bridge provides the internal brief for Sales
if a commercial handoff is needed. The CSM reads the organizational dynamics — whether
the relationship supports the ask, whether the budget cycle is right — and runs the
play.

**Renewal.** The Risk lens with renewal-proximity weighting assembles the full renewal
package: value delivered against original success criteria, usage trajectory, health
history, stakeholder engagement, commercial details. The internal bridge drafts the QBR
narrative. The operating layer tracks the renewal process. The CSM walks into the
renewal fully armed and negotiates.

**At-Risk.** The Risk lens at high severity assembles the risk brief with intervention
history from the commitment tracker. The internal bridge drafts the internal escalation
if executive or cross-functional involvement is needed. The CSM decides the response
level and has the hard conversations the system can't have.

**Post-Churn.** The commitment tracker prompts a retrospective. The CSM writes an
honest reflection. The cohort analyst consumes it as ground truth. The internal bridge
routes churn patterns to Product and Leadership.

**Customer Advocacy.** The system identifies candidates based on sustained health,
satisfaction, and outcome achievement. It tracks ask frequency to prevent over-asking.
The internal bridge matches advocacy candidates to requests from Marketing and Sales.
The CSM decides whether the moment is right and makes the ask personally.

---

## Design Decisions Still Open

**Advocacy: separate lens or filter?** Does "this customer would be a good reference"
need its own projection, filter chain, and governance tier? Or is it a condition
detected within the Expansion lens — healthy, tenured, strong champion — with a
different action type? The answer depends on whether the framing and filter logic
diverge enough to warrant separation.

**Renewal: separate lens or mode of Risk?** Renewal preparation uses Risk lens logic
(trajectory, engagement, proximity) but needs a different drafting prompt (renewal
narrative vs. risk intervention) and different evidence assembly (the full account
story, not just the risk brief). This might be a strong enough divergence to warrant its
own lens, or it might be a parameterized mode of Risk.

**Knowledge base storage.** File-based versioned artifacts (simple, matches the curated
content model, easy to review in code review) vs. database-backed (enables the cohort
analyst to propose new entries programmatically, supports richer indexing). The answer
probably depends on scale — file-based is right for a small playbook library,
database-backed is right when the cohort analyst is actively proposing content.

**Autonomy graduation thresholds.** What approval rate, over what sample size, with
what outcome quality, justifies graduating an action type to autonomous? These are
policy decisions for CS leadership, not engineering decisions. The system provides the
data. The humans set the thresholds.

**Snapshot cadence.** Daily is natural and matches the digest rhythm. But some signals
(usage cliff, champion going silent) might benefit from more frequent evaluation. The
architecture supports any cadence. The question is whether sub-daily evaluation produces
enough additional signal to justify the additional computation.

**Operating layer boundaries.** How deep does the inbox intelligence go? Classifying and
prioritizing email is unambiguous. Extracting action items and commitments from email
text involves LLM processing of potentially sensitive content. The boundary between
"organize what the CSM can see" and "interpret what the CSM received" needs a clear
privacy model.

**Internal bridge authorization.** The system drafts internal communications
automatically. But sending an aggregated product feedback summary to the VP of Product
is a different act from showing it to the CSM. Who approves internal routing? Is it
automatic because it's internal, or does the CSM review before it goes out? The answer
probably depends on the audience and the content.

# Position — where this system sits in the 2026 landscape

Grounded competitive positioning, researched **2026-07-02** against the cited public
sources below. Claim discipline applies to positioning too: every comparative statement
here is dated and sourced; if the landscape moves, this document is stale until re-run —
it does not silently stay true.

## The landscape: three vendor classes, one open loop

As of mid-2026 the agentic-CS market has converged on the *language* this system was
built around — "AI agents propose actions and humans approve them" is now the category
norm, not a differentiator:

- **Capability vendors** ship agents that do CS work. Gainsight launched an agentic
  stack and MCP access across its platform (April–May 2026); ChurnZero ships a
  marketplace of 14 agentic "AI teammates" that detect risk and draft plans; startups
  sell "the AI CSM" outright. The trust story is UX and marketing — none publishes a
  human-anchored quality measurement, none makes the model *structurally* unable to
  mint authority, and health scores are model-derived rather than auditable
  derivations.
- **Control vendors** (decision-authority / agent-governance platforms) wrap approval
  routing, policy gates, and audit trails **around opaque agents from the outside**.
  They gate actions but cannot see or constrain the reasoning, hold no domain world
  model, and measure nothing about output quality.
- **Measurement vendors** (LLM-eval platforms) measure quality — detached from both the
  domain and the control plane. Evals inform a dashboard; they do not change what an
  agent is permitted to do.

**The open loop:** none of the three classes feeds *measured reliability* back into
*enforced permission*. Capability vendors don't measure; control vendors don't
understand; measurement vendors don't enforce.

## What this system is

This system closes that loop: **measurement → control → capability, in one provenance
chain.** A human-anchored judge measures output quality per capability (reported as
per-dimension agreement with confidence intervals, never averaged); a tiered action gate
converts permission into enforced, hash-bound mechanics; an earned-autonomy mechanism
proposes expanding permission **only from measured verdict history**, and never applies
a change itself; every step — finding, proposal, verdict, hold, release, override,
degradation — lands in the same evidentiary ledger.

Concretely, it is five things at once:

1. **A deterministic customer-state engine** — one value model (usage, penetration,
   feature depth, outcome; cross-source divergence detection), computed once, projected
   through thin lenses. Every score is an auditable derivation, not a model opinion.
2. **An autonomy governor** — tiered permissions enforced at propose, approve, and
   commit time; a declarative precedence matrix that can suppress *actions* but is
   structurally incapable of suppressing *findings*; releases that re-derive from
   current reality rather than replaying stale drafts.
3. **A self-measuring LLM deployment** — blinded gold sets, judge-vs-human κ with CIs,
   determinism probes on the judge itself, degradation ladders with negative controls,
   and a standing rule: mechanize whatever proves checkable, shrink the judge.
4. **An evidentiary ledger** — every oversight event carries context, actor, and
   timestamp; machine-readable claim boundaries state what each artifact does and does
   not prove.
5. **A ground-truth server for other agents** — deterministic read-only tools any MCP
   host can safely converse over, with write authority structurally absent from that
   surface.

## Honest overlap (what is NOT unique here)

Health scoring and CTAs (every CS platform, with better live-data integration today);
LLM output validation (multiple mature libraries); human-approval workflow steps (any
automation tool); LLM-as-judge with human labels (standard eval-tooling practice); MCP
exposure of business data (now including Gainsight); RBAC/SoD/audit (standard enterprise
compliance patterns). Any single mechanism is catchable. The defensible position is the
closed loop plus the discipline cost of running all of it together — real, but erodible;
this is a method lead, not a patent.

## Why the timing matters

Human-oversight obligations for high-risk AI under the EU AI Act (Article 14) take
effect **August 2026**, requiring documented, defensible oversight records. The gate
ledger and verdict stream here already *are* that evidence class — oversight as a native
property rather than a retrofit. Separately: now that every incumbent claims
propose-and-approve agents, the buyer's next question is *prove it* — and this is the
architecture built to answer that question with a test suite rather than a slide.

**One line:** the market spent 2025–2026 promising governed autonomous customer success;
this is the version where the promise is checkable.

## Claim boundary

This document positions a **simulation-stage system**: no live tenant has run through
it; quality claims are gated per-dimension on judge validation status (see `STATUS.md`,
which is rendered from artifacts, not hand-written); connectors are verified to the
credential boundary. Comparative statements reflect the cited sources as of 2026-07-02.

## Sources

- Gainsight MCP launch: https://www.gainsight.com/press/gainsight-opens-its-platform-with-mcp-bringing-customer-retention-into-the-agentic-era/
- Gainsight agentic stack: https://www.gainsight.com/press/gainsight-launches-the-agentic-stack-for-customer-retention/
- Gainsight Atlas agents: https://www.gainsight.com/press/gainsight-launches-atlas-ai-agents-for-customer-retention-and-growth/
- ChurnZero AI teammates: https://churnzero.com/press-release/churnzero-extends-industry-leadership-by-reshaping-customer-success-with-ai-teammates/
- Category norm ("agents propose, CSMs approve"): https://www.thrivestack.ai/research/ai-customer-success-platforms
- Planhat Model Hub: https://www.planhat.com/switch/churnzero
- Decision-authority layer (control-vendor class): https://humanlayer.systems/index-en.html
- Agent-governance platform criteria: https://www.exemplar.dev/blog/best-ai-agent-governance-platforms
- HITL oversight & EU AI Act Article 14 timing: https://www.strata.io/blog/agentic-identity/practicing-the-human-in-the-loop/

// Two-register rule (UI_DESIGN_BRIEF.md): plain-English label is the
// primary text; the raw system vocabulary rides along as a mono receipt
// (tooltip/title attribute), never as the primary label itself.
export const TRIGGER_LABELS: Record<string, string> = {
  feature_shallow_depth: "Paid features unused",
  trajectory_decline: "Health trending down",
  milestones_overdue: "Onboarding running late",
  low_seat_penetration: "Seats not activated",
  outcome_unknown: "No proven results yet",
  health_yellow: "Health slipping",
  health_red: "Health critical",
  usage_decay_silent: "Usage fading quietly",
  product_qualified_lead: "Expansion signal",
  renewal_window: "Renewal approaching",
  seats_near_cap: "Seats near cap",
  onboarding_activation_gap: "Onboarding-stage activation gap",
  // Reconciliation agent (Harvest 31/32): value_model divergences + Risk/
  // Expansion lens factors (report 51/52) surfaced as Tier-1 signals.
  single_threaded_risk: "Usage concentrated in one person",
  usage_concentration: "One user drives most activity",
  arr_risk_exposure: "Revenue at risk",
  champion_departed: "Champion departed",
  new_stakeholder_unengaged: "New stakeholder hasn't engaged",
  health_usage_divergence: "Health score outpaces real usage",
  expansion_readiness_high_adoption: "High adoption, ready to expand",
  arr_expansion_surface: "Expansion headroom on contract value",
  usage_outcome_unverified: "Usage without a proven outcome",
  overdue_success_plan: "Success plan overdue",
  open_expansion_opportunity: "Open expansion opportunity",
  success_plan_overdue: "Success plan overdue",
  arr_tier: "Contract value requires review",
  days_overdue: "Days overdue",
  feature_depth_gap: "Paid capabilities unused",
};

export const MOTION_LABELS: Record<string, string> = {
  personal_email: "Personal email",
  working_session: "Working session",
  qbr: "QBR",
  escalation: "Escalate to human",
  content_route: "Send help content",
  campaign_enroll: "Add to campaign",
  cohort_action: "One campaign, many accounts",
};

export const TIER_LABELS: Record<string, string> = {
  high_touch: "High touch",
  mid_touch: "Mid touch",
  tech_touch: "Self-serve tier",
};

export const DISPOSITION_LABELS: Record<string, string> = {
  propose_customer_action: "AI-written — needs your approval",
  internal_review: "Rule-based · no AI",
  escalate: "Needs judgment",
};

export const PROPOSAL_STATUS_LABELS: Record<string, string> = {
  pending: "needs your approval",
  approved: "approved · sent",
  denied: "denied · won't recur",
};

export function label(map: Record<string, string>, key: string | null | undefined): string {
  if (!key) return "—";
  return map[key] ?? key;
}

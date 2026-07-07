import { WorkItem } from "@/lib/api";
import { label, MOTION_LABELS } from "@/lib/labels";

export type WorkCadence = "daily" | "weekly" | "monthly" | "quarterly" | "annual" | "event";
export type WorkKind =
  | "customer_action"
  | "briefing_packet"
  | "internal_handoff"
  | "integrity_task"
  | "cohort_packet"
  | "approval_audit";

export interface WorkDescriptor {
  cadence: WorkCadence;
  cadenceLabel: string;
  kind: WorkKind;
  kindLabel: string;
  packetLabel: string;
  shortPacketLabel: string;
  authorityLabel: string;
}

const CADENCE_LABELS: Record<WorkCadence, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  quarterly: "Quarterly",
  annual: "Annual",
  event: "Event",
};

export function workItemKey(item: WorkItem): string {
  if (item.proposal?.proposal_id) return item.proposal.proposal_id;
  const subject = (item.account_id ?? item.candidate_account_ids.join(",")) || "program";
  return [
    item.disposition,
    subject,
    item.motion ?? item.recommended_action ?? "work",
    item.swept_at,
  ].join(":");
}

export function describeWork(item: WorkItem): WorkDescriptor {
  const hasInternalTarget = Boolean(
    item.internal_bridge_decision && !item.internal_bridge_decision.abstained
  );
  const action = item.proposal?.action_type ?? item.recommended_action;
  const motion = item.motion;
  let cadence: WorkCadence = "daily";
  let kind: WorkKind = "customer_action";

  if (hasInternalTarget && !item.proposal) {
    cadence = "event";
    kind = "internal_handoff";
  } else if (hasInternalTarget) {
    cadence = "event";
    kind = "briefing_packet";
  } else if (motion === "qbr") {
    cadence = "quarterly";
    kind = "briefing_packet";
  } else if (motion === "escalation") {
    cadence = "event";
    kind = "customer_action";
  } else if (motion === "cohort_action" || action === "cohort_action") {
    cadence = "monthly";
    kind = "cohort_packet";
  } else if (motion === "campaign_enroll" || action === "campaign_enroll") {
    cadence = "weekly";
    kind = "customer_action";
  } else if (item.disposition === "internal_review") {
    cadence = "weekly";
    kind = "integrity_task";
  }

  const motionLabel = motion ? label(MOTION_LABELS, motion) : null;
  const diagnosticLabel = diagnosticPacketLabel(item);
  const packetLabel =
    kind === "briefing_packet"
      ? hasInternalTarget
        ? `${targetLabel(item)} briefing packet`
        : "Briefing packet"
      : kind === "internal_handoff"
        ? `${targetLabel(item)} handoff packet`
        : kind === "integrity_task"
          ? "Integrity task"
          : kind === "cohort_packet"
            ? "Cohort packet"
            : diagnosticLabel
              ? diagnosticLabel
            : motionLabel
              ? `${motionLabel} packet`
              : "Customer action packet";

  return {
    cadence,
    cadenceLabel: CADENCE_LABELS[cadence],
    kind,
    kindLabel: kindLabel(kind),
    packetLabel,
    shortPacketLabel: packetLabel.replace(/ packet$/, ""),
    authorityLabel: item.proposal
      ? item.proposal.status === "pending"
        ? "human approval required"
        : `proposal ${item.proposal.status}`
      : "no customer-facing release",
  };
}

function diagnosticPacketLabel(item: WorkItem): string | null {
  const trigger = item.motion_source?.trigger_factor;
  if (trigger === "milestones_overdue") return "Onboarding recovery packet";
  if (trigger === "feature_shallow_depth") return "Adoption unblock packet";
  if (trigger === "health_red") return "Critical-risk triage packet";
  if (trigger === "health_yellow") return "Health-risk review packet";
  if (trigger === "outcome_unknown") return "Outcome proof packet";
  if (trigger === "low_seat_penetration") return "Seat activation packet";
  if (trigger === "champion_inactive") return "Champion reactivation packet";
  return null;
}

function kindLabel(kind: WorkKind): string {
  switch (kind) {
    case "briefing_packet":
      return "Briefing";
    case "internal_handoff":
      return "Internal";
    case "integrity_task":
      return "Integrity";
    case "cohort_packet":
      return "Cohort";
    case "approval_audit":
      return "Audit";
    case "customer_action":
    default:
      return "Customer";
  }
}

function targetLabel(item: WorkItem): string {
  const target = item.internal_bridge_decision?.target;
  if (target === "engineering") return "Engineering";
  if (target === "product") return "Product";
  return "Internal";
}

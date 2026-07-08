"use client";

import { useEffect, useState } from "react";
import {
  api,
  CentralizeTelemetryResponse,
  CSMWorkPacket,
  EnterpriseOnboardingPacket,
  SelfServeActivationPacket,
  WorkItem,
} from "@/lib/api";
import { label, MOTION_LABELS, TRIGGER_LABELS } from "@/lib/labels";
import { ReconciliationSection } from "./ReconciliationSection";

type Brief = Record<string, unknown>;

// Row shapes for the 4 remaining generic-Drawer sources, verified against
// _api_helpers.py's _build_account_brief -> asdict() output (Phase 1's
// contract table): TimeToValueMilestone, UsageSignal, SuccessPlan, CRMCase
// (contracts.py). Stakeholders already has its own bespoke drawer (Harvest
// 17); Comms/Calendar/Agent-history stay dormant (briefField: null) -- no
// live source exists for them (see DRAWERS below), untouched here.
interface MilestoneRow {
  milestone: string;
  expected_by: string;
  achieved_at: string | null;
}
interface UsageSignalRow {
  metric_name: string;
  value: number;
  unit: string;
  observed_at: string;
}
interface SuccessPlanRow {
  status: string;
  objectives: string[];
  target_date: string;
}
interface CaseRow {
  subject: string;
  status: string;
  priority: string;
}

// snake_case code -> plain phrase, shared by milestone/objective rows (both
// carry short verb-object codes rather than free text, unlike case.subject
// which is already natural language). Falls back to a spaced, lowercased
// rendering of the raw code for any value not in this table, rather than
// hiding or inventing a claim about codes we haven't authored a phrase for.
function humanizeCode(code: string): string {
  const known: Record<string, string> = {
    activate_50pct_assets: "Activate 50% of fleet",
    first_route_optimization: "First route optimization",
    activate_core_fleet: "Activate core fleet",
    complete_driver_onboarding: "Complete driver onboarding",
  };
  return known[code] ?? code.replace(/_/g, " ");
}

// Person UI depth (Harvest 17): a stakeholder row as served by the
// additive AccountBriefResponse.stakeholders field (_api_helpers.py's
// _stakeholder_rows) -- name/role/recency/consent/flags precomputed
// server-side (K13: the UI renders, it does not compute).
interface StakeholderRow {
  contact_id: string;
  name: string;
  relationship_type: string | null;
  title: string | null;
  consent_to_contact: boolean;
  days_since_interaction: number | null;
  champion: boolean;
  departed: boolean;
  new_unengaged: boolean;
}

// Plain-English role labels (two-register rule) -- mono relationship_type
// rides along as the title attribute, never as the primary label.
const ROLE_LABELS: Record<string, string> = {
  champion: "Champion",
  executive_sponsor: "Exec sponsor",
  technical_lead: "Technical lead",
  end_user: "End user",
  admin: "Admin",
};

// Per-drawer row formatter: plain-language primary text + optional mono/
// colored metadata, mirroring StakeholderPersonRow's established two-part
// shape (sname/smeta) rather than the raw-JSON .evid-row/.eval styling
// (globals.css:160-162 -- .eval is monospace by default, wrong container
// for plain-English text). Formats ONLY fields the row actually carries,
// verified against contracts.py's dataclasses (Phase 1 reading list) --
// no invented percentages/trends/comparisons.
function milestoneRowText(row: MilestoneRow): { name: string; meta: string } {
  const label = humanizeCode(row.milestone);
  if (row.achieved_at) {
    return { name: label, meta: `completed ${row.achieved_at}` };
  }
  return { name: label, meta: `expected by ${row.expected_by}` };
}

function usageSignalRowText(row: UsageSignalRow): { name: string; meta: string } {
  const label = humanizeCode(row.metric_name);
  return { name: label, meta: `${row.value} ${row.unit} · ${row.observed_at.slice(0, 10)}` };
}

function successPlanRowText(row: SuccessPlanRow): { name: string; meta: string } {
  const name = row.objectives.length > 0 ? humanizeCode(row.objectives[0]) : "Success plan";
  const extra = row.objectives.length > 1 ? ` +${row.objectives.length - 1} more` : "";
  return { name: name + extra, meta: `${row.status} · due ${row.target_date}` };
}

function caseRowText(row: CaseRow): { name: string; meta: string } {
  return { name: row.subject, meta: `${row.status} · ${row.priority} priority` };
}

function genericDrawerRowText(row: unknown): { name: string; meta: string } {
  if (!row || typeof row !== "object") {
    return { name: "Record available", meta: "unformatted source row" };
  }
  const record = row as Record<string, unknown>;
  const name =
    firstString(record, ["subject", "title", "name", "milestone", "metric_name", "status"]) ??
    "Record available";
  const meta =
    firstString(record, ["observed_at", "timestamp", "expected_by", "target_date", "priority"]) ??
    "unformatted source row";
  return { name: humanizeCode(name), meta };
}

function firstString(record: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return null;
}

// Drawer -> brief field mapping, verified against api.py's AccountBriefResponse
// (Phase 1's contract table). Stakeholders now reads the additive
// `stakeholders` field (per-person role graph) instead of raw `contacts`.
// Comms is rendered by CommsDrawer (three sources, own tab strip) instead of
// the generic single-field Drawer -- its briefField is unused, kept null only
// so this array's shape stays uniform. Calendar/Agent-history have NO live
// source anywhere this endpoint reads from -- rendered dormant honestly, never
// populated with placeholder rows (UI_DESIGN_BRIEF's no-fake-data rule).
const DRAWERS: {
  key: string;
  name: string;
  briefField: string | null;
  formatter?: (row: unknown) => { name: string; meta: string };
}[] = [
  { key: "comms", name: "Comms", briefField: null },
  { key: "centralize", name: "Centralize", briefField: null },
  { key: "calendar", name: "Calendar", briefField: null },
  { key: "people", name: "Stakeholders", briefField: "stakeholders" },
  {
    key: "onboarding",
    name: "Onboarding (Rocketlane)",
    briefField: "milestones",
    formatter: milestoneRowText as (row: unknown) => { name: string; meta: string },
  },
  {
    key: "telemetry",
    name: "Telemetry",
    briefField: "recent_usage_signals",
    formatter: usageSignalRowText as (row: unknown) => { name: string; meta: string },
  },
  {
    key: "plan",
    name: "Success plan",
    briefField: "success_plans",
    formatter: successPlanRowText as (row: unknown) => { name: string; meta: string },
  },
  {
    key: "cases",
    name: "Cases",
    briefField: "open_cases",
    formatter: caseRowText as (row: unknown) => { name: string; meta: string },
  },
  { key: "agent", name: "Agent history", briefField: null },
];

export function QueueDetail({
  item,
  packet,
  day,
}: {
  item: WorkItem | null;
  packet: CSMWorkPacket;
  day: number | undefined;
}) {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [centralizeTelemetry, setCentralizeTelemetry] = useState<CentralizeTelemetryResponse | null>(null);
  const [enterpriseOnboardingPacket, setEnterpriseOnboardingPacket] =
    useState<EnterpriseOnboardingPacket | null>(null);
  const [selfServeActivationPacket, setSelfServeActivationPacket] =
    useState<SelfServeActivationPacket | null>(null);
  const [openDrawer, setOpenDrawer] = useState<string | null>(null);
  const [openFactor, setOpenFactor] = useState<number | null>(null);

  useEffect(() => {
    setBrief(null);
    setCentralizeTelemetry(null);
    setEnterpriseOnboardingPacket(null);
    setSelfServeActivationPacket(null);
    if (!item?.account_id) return;
    api
      .accountBrief(item.account_id, day)
      .then(setBrief)
      .catch(() => setBrief(null));
    api
      .accountCentralizeTelemetry(item.account_id, day)
      .then(setCentralizeTelemetry)
      .catch(() => setCentralizeTelemetry(null));
    api
      .enterpriseOnboardingPackets(item.account_id)
      .then((r) => setEnterpriseOnboardingPacket(r.packets[0] ?? null))
      .catch(() => setEnterpriseOnboardingPacket(null));
    api
      .selfServeActivationPackets(item.account_id)
      .then((r) => setSelfServeActivationPacket(r.packets[0] ?? null))
      .catch(() => setSelfServeActivationPacket(null));
  }, [item?.account_id, day]);

  if (!item || item.account_id === null) {
    return (
      <div className="detail-scroll">
        <PacketIdentity packet={packet} />
        <PacketActionBrief packet={packet} />
        <PacketTrace packet={packet} />
      </div>
    );
  }

  return (
    <div className="detail-scroll">
      <PacketIdentity packet={packet} lifecycle={(brief?.lifecycle_stage as string | undefined) ?? null} />
      <PacketActionBrief packet={packet} />
      <EnterpriseOnboardingPanel packet={enterpriseOnboardingPacket} />
      <SelfServeActivationPanel packet={selfServeActivationPacket} />
      <PacketTrace packet={packet} />

      <div className="sec">
        <div className="sec-h">
          <span className="t">Account sources</span>
          <span className="prov">
            <span className="chip-det">9 systems — 6 live, 3 no source yet</span>
          </span>
        </div>
        {DRAWERS.map((d) =>
          d.key === "people" ? (
            <StakeholderDrawer
              key={d.key}
              brief={brief}
              open={openDrawer === d.key}
              onToggle={() => setOpenDrawer(openDrawer === d.key ? null : d.key)}
            />
          ) : d.key === "comms" ? (
            <CommsDrawer key={d.key} brief={brief} open={openDrawer === d.key}
              onToggle={() => setOpenDrawer(openDrawer === d.key ? null : d.key)} />
          ) : d.key === "centralize" ? (
            <CentralizeDrawer
              key={d.key}
              telemetry={centralizeTelemetry}
              open={openDrawer === d.key}
              onToggle={() => setOpenDrawer(openDrawer === d.key ? null : d.key)}
            />
          ) : (
            <Drawer key={d.key} name={d.name} field={d.briefField} brief={brief} formatter={d.formatter} open={openDrawer === d.key}
              onToggle={() => setOpenDrawer(openDrawer === d.key ? null : d.key)} />
          )
        )}
      </div>

      <div className="sec">
        <div className="sec-h">
          <span className="t">Why this account, why now</span>
          <span className="prov">
            <span className="chip-det">Rule-based · no AI</span>
          </span>
        </div>
        <div className="scoreline">
          <span className="v num">{item.priority?.score ?? "—"}</span>
          <span className="cap">
            {item.priority?.factors.length ?? 0} signals detected — higher = sooner
          </span>
        </div>
        {(item.priority?.factors ?? []).map((factor, fi) => (
          <div key={factor.name}>
            <div
              className="factor"
              onClick={() => setOpenFactor(openFactor === fi ? null : fi)}
            >
              <span className="fname">{label(TRIGGER_LABELS, factor.name)}</span>
              <span className="contrib" title={`adds ${factor.contribution} points`}>
                +{factor.contribution}
              </span>
              <span className="fmeta">
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-2)" }}>
                  {factor.name}
                </span>
                <span>{factor.evidence?.length ?? 0} records</span>
              </span>
            </div>
            {openFactor === fi && (
              <div className="evid-in">
                {(factor.evidence ?? []).map((ev, ei) => {
                  // Person-cited evidence (Harvest 17): the sweep attaches an
                  // additive `person_name` to crm-sourced evidence for a
                  // person-derived factor (_enrich_person_evidence, api.py) --
                  // plain-language citation with the raw record id as the
                  // mono receipt (two-register rule).
                  const personName = ev.person_name as string | undefined;
                  return (
                    <div className="evid-row" key={ei}>
                      <span className="esys">
                        {(ev.source as string) ?? "evidence"}
                      </span>
                      {personName ? (
                        <span className="eval">
                          {label(TRIGGER_LABELS, factor.name)} — {personName}
                          <span className="mono" style={{ marginLeft: 6, color: "var(--fg-2)" }}>
                            {(ev.source as string) ?? "crm"} · {String(ev.source_id ?? "").slice(0, 8)}
                          </span>
                        </span>
                      ) : (
                        // General case (EvidenceRef, contracts.py): every
                        // record carries source/source_id/field/observed_at
                        // (verified live against a real brief response) --
                        // humanize the field name, keep source_id as the
                        // mono receipt, same register as the person-cited
                        // branch above. No invented claim beyond these
                        // fields.
                        <span className="eval">
                          {humanizeCode((ev.field as string) ?? "record")} · observed {(ev.observed_at as string) ?? "—"}
                          <span className="mono" style={{ marginLeft: 6, color: "var(--fg-2)" }}>
                            {(ev.source as string) ?? "evidence"} · {String(ev.source_id ?? "").slice(0, 8)}
                          </span>
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>

      <ReconciliationSection accountId={item.account_id} day={day} />

      <InternalHandoff decision={item.internal_bridge_decision ?? null} />

      <div className="sec">
        <div className="sec-h">
          <span className="t">Chosen action — and why</span>
          <span className="prov">
            <span className="chip-det">Rule-based</span>
          </span>
        </div>
        <div className="resolve">
          <div className="line">
            <span className="m-final" title={item.motion ?? undefined}>
              {item.motion ? label(MOTION_LABELS, item.motion) : "dormant — no live motion"}
            </span>
            {item.recipient_name && (
              <span
                className="chip-det"
                title={`resolution: ${item.recipient_resolution ?? "unknown"}`}
              >
                to: {item.recipient_name}
                {item.recipient_role ? ` · ${label(ROLE_LABELS, item.recipient_role)}` : ""}
              </span>
            )}
          </div>
          <div className="why">{item.reason}</div>
        </div>
      </div>

      {item.customer_draft && (
        <div className="sec">
          <div className="sec-h">
            <span className="t">Proposed draft</span>
            <span className="prov">
              <span className="chip-llm">AI-written — needs your approval</span>
            </span>
          </div>
          <div className="draft">
            <div className="draft-h">draft · quality score dormant, no live source yet</div>
            <div className="draft-body">{item.customer_draft}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function PacketIdentity({
  packet,
  lifecycle,
}: {
  packet: CSMWorkPacket;
  lifecycle?: string | null;
}) {
  return (
    <div className="identity">
      <div className="mono-avatar">
        {packet.account_name.slice(0, 2).toUpperCase()}
      </div>
      <div>
        <div className="id-name">{packet.account_name}</div>
        <div className="id-meta">
          <span className="tierpill">{packet.job_type.replace(/_/g, " ")}</span>
          <span className="tierpill">{packet.lane.replace(/_/g, " ")}</span>
          <span className="tierpill">{packet.cadence.replace(/_/g, " ")}</span>
          {lifecycle && <span className="tierpill">{lifecycle}</span>}
        </div>
      </div>
    </div>
  );
}

function PacketActionBrief({ packet }: { packet: CSMWorkPacket }) {
  const contact = packet.contact_plan.primary_contact;
  const backup = packet.contact_plan.backup_contact;
  const artifact = packet.prepared_artifacts[0];
  return (
    <div className="packet-brief">
      <div className="packet-main">
        <div className="packet-kicker">Here is what the human can do</div>
        <h2>{packet.primary_next_step}</h2>
        <p>{packet.why_now}</p>
      </div>
      <div className="packet-grid">
        <BriefCell label="What it implies" value={packet.implied_customer_state} />
        <BriefCell label="Agent recommendation" value={packet.recommended_action.objective} />
        <BriefCell
          label="Contact / owner"
          value={
            contact
              ? `${String(contact.name)} · ${String(contact.role ?? contact.title ?? "contact")}`
              : packet.contact_plan.internal_owner ?? "internal review"
          }
          meta={backup ? `backup: ${String(backup.name)}` : packet.contact_plan.reason_for_contact_choice}
        />
        <BriefCell
          label="Gate state"
          value={
            packet.governance.requires_action_gate
              ? "ActionGate required before execution"
              : "local review only"
          }
          meta={packet.governance.can_execute_from_ui ? "executable" : "not executable from UI"}
        />
      </div>
      {artifact && (
        <div className="packet-artifact">
          <div className="packet-kicker">Here is what the agent prepared</div>
          <div className="artifact-title">{artifact.title}</div>
          <div className="artifact-body">{artifact.body_or_outline}</div>
        </div>
      )}
    </div>
  );
}

function BriefCell({
  label,
  value,
  meta,
}: {
  label: string;
  value: string;
  meta?: string;
}) {
  return (
    <div className="brief-cell">
      <span>{label}</span>
      <strong>{value}</strong>
      {meta && <em>{meta}</em>}
    </div>
  );
}

function EnterpriseOnboardingPanel({
  packet,
}: {
  packet: EnterpriseOnboardingPacket | null;
}) {
  if (!packet) return null;

  const payload = asRecord(packet.packet);
  const coverage = asRecord(payload.coverage);
  const methodology = asRecord(payload.success_plan_methodology);
  const alignment = asRecord(methodology.value_model_alignment);
  const rails = asArray(alignment.rails).map(asRecord);
  const milestones = asArray(payload.success_plan_v0).map(asRecord);
  const integrations = asArray(payload.customer_integrations).map(asRecord);
  const checks = asArray(methodology.validation_checks).map(asRecord);
  const failedChecks = checks.filter((check) => check.passed === false);
  const missingSources = asArray(coverage.missing_required_sources)
    .map((value) => String(value))
    .filter(Boolean);
  const proposals = asArray(payload.proposals).map(asRecord);
  const receipts = asArray(payload.source_receipts);
  const packetStatus = String(payload.status ?? packet.status);
  const isReady = packetStatus === "ready";

  return (
    <div className={`sec launch-packet ${isReady ? "ready" : "blocked"}`}>
      <div className="sec-h">
        <span className="t">Enterprise launch packet</span>
        <span className="prov">
          <span className={isReady ? "chip-det launch-ok" : "chip-det launch-stop"}>
            {packetStatus.replace(/_/g, " ")}
          </span>
        </span>
      </div>
      <div className="launch-head">
        <div>
          <div className="launch-title">{String(payload.recommended_next_action ?? "Review launch packet")}</div>
          <div className="launch-meta">
            opportunity {packet.opportunity_id.slice(0, 8)} · {receipts.length} receipts · {proposals.length} gated proposal{proposals.length === 1 ? "" : "s"}
          </div>
        </div>
        <div className="launch-score">
          <span className="num">{numberOrDash(alignment.ttv_priority_score)}</span>
          <em>TTV priority</em>
        </div>
      </div>

      <div className="launch-grid">
        <LaunchMetric label="Lifecycle" value={String(alignment.lifecycle_stage ?? "unknown")} />
        <LaunchMetric label="Service tier" value={String(alignment.service_tier ?? "unknown").replace(/_/g, " ")} />
        <LaunchMetric label="Threshold rule" value={String(alignment.rule_name ?? "unresolved")} />
        <LaunchMetric label="Config" value={String(alignment.config_version ?? "unresolved")} />
      </div>

      {(missingSources.length > 0 || failedChecks.length > 0) && (
        <div className="launch-alert">
          {missingSources.map((source) => (
            <span key={`missing-${source}`}>missing: {source.replace(/_/g, " ")}</span>
          ))}
          {failedChecks.map((check) => (
            <span key={`failed-${String(check.check_name)}`}>
              failed: {String(check.check_name).replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}

      {rails.length > 0 && (
        <div className="launch-rails">
          {rails.map((rail) => (
            <LaunchRail key={String(rail.rail)} rail={rail} />
          ))}
        </div>
      )}

      {milestones.length > 0 && (
        <div className="launch-list">
          <div className="packet-kicker">Measured milestones</div>
          {milestones.slice(0, 5).map((milestone) => {
            const measurement = asRecord(milestone.measurement);
            return (
              <div className="launch-row" key={String(milestone.milestone)}>
                <span>{String(milestone.milestone ?? "Milestone")}</span>
                <em>
                  {String(measurement.rail ?? "unmeasured").replace(/_/g, " ")} · target {numberOrDash(measurement.target_value)}
                </em>
              </div>
            );
          })}
        </div>
      )}

      {integrations.length > 0 && (
        <div className="launch-integrations">
          {integrations.map((integration) => (
            <span
              key={String(integration.family)}
              className={`launch-integration ${String(integration.status ?? "unknown")}`}
              title={String(integration.note ?? "")}
            >
              {String(integration.label ?? integration.family)} · {String(integration.status ?? "unknown")}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function SelfServeActivationPanel({
  packet,
}: {
  packet: SelfServeActivationPacket | null;
}) {
  if (!packet) return null;

  const payload = asRecord(packet.packet);
  const coverage = asRecord(payload.coverage);
  const path = asRecord(payload.value_path);
  const action = asRecord(payload.recommended_action);
  const milestones = asArray(path.milestones).map(asRecord);
  const secondaryHypotheses = asArray(path.secondary_hypotheses).map(asRecord);
  const missingSources = asArray(coverage.missing_required_sources)
    .map((value) => String(value))
    .filter(Boolean);
  const blockers = [
    ...asArray(coverage.customer_output_blockers),
    ...asArray(action.suppression_reasons),
  ].map((value) => String(value)).filter(Boolean);
  const proposals = asArray(payload.proposals).map(asRecord);
  const receipts = asArray(payload.source_receipts);
  const packetStatus = String(payload.status ?? packet.status);
  const isReady = packetStatus === "ready";
  const firstValue = path.first_value_reached === true;
  const currentMilestone = milestones.find((milestone) =>
    ["current", "stale"].includes(String(milestone.status))
  );

  return (
    <div className={`sec launch-packet activation-packet ${isReady ? "ready" : "blocked"}`}>
      <div className="sec-h">
        <span className="t">Self-serve value path</span>
        <span className="prov">
          <span className={isReady ? "chip-det launch-ok" : "chip-det launch-stop"}>
            {packetStatus.replace(/_/g, " ")}
          </span>
        </span>
      </div>
      <div className="launch-head">
        <div>
          <div className="launch-title">{String(path.archetype ?? "Activation path")}</div>
          <div className="launch-meta">
            workspace {packet.workspace_id.slice(0, 12)} · {receipts.length} receipts · {proposals.length} gated proposal{proposals.length === 1 ? "" : "s"}
          </div>
        </div>
        <div className="launch-score">
          <span className="num">{firstValue ? "yes" : "no"}</span>
          <em>first value</em>
        </div>
      </div>

      <div className="launch-grid">
        <LaunchMetric label="Path" value={String(path.path_id ?? "unknown").replace(/_/g, " ")} />
        <LaunchMetric label="Current" value={String(path.current_milestone_id ?? "complete").replace(/_/g, " ")} />
        <LaunchMetric label="Action trigger" value={String(action.trigger ?? "none").replace(/_/g, " ")} />
        <LaunchMetric label="Config" value={String(path.config_version ?? "unversioned").replace(/_/g, " ")} />
      </div>

      {(missingSources.length > 0 || blockers.length > 0) && (
        <div className="launch-alert">
          {missingSources.map((source) => (
            <span key={`missing-${source}`}>missing: {source.replace(/_/g, " ")}</span>
          ))}
          {blockers.slice(0, 4).map((blocker) => (
            <span key={`blocker-${blocker}`}>blocked: {blocker.replace(/_/g, " ")}</span>
          ))}
        </div>
      )}

      <div className="activation-summary">
        <span>{String(path.first_value_definition ?? "First value definition unavailable")}</span>
        <em>{String(path.selection_reason ?? "No selection reason recorded")}</em>
      </div>

      {secondaryHypotheses.length > 0 && (
        <div className="activation-hypotheses">
          {secondaryHypotheses.slice(0, 3).map((hypothesis) => (
            <span key={String(hypothesis.path_id)}>
              {String(hypothesis.path_id ?? "alternate").replace(/_/g, " ")} · {numberOrDash(hypothesis.score)}
            </span>
          ))}
        </div>
      )}

      {milestones.length > 0 && (
        <div className="activation-milestones">
          {milestones.map((milestone) => (
            <div
              className={`activation-step ${String(milestone.status)}`}
              key={String(milestone.milestone_id)}
              title={String(milestone.customer_safe_interpretation ?? "")}
            >
              <span>{String(milestone.label ?? milestone.milestone_id)}</span>
              <em>{String(milestone.status ?? "unknown").replace(/_/g, " ")}</em>
            </div>
          ))}
        </div>
      )}

      <div className="launch-list">
        <div className="packet-kicker">Recommended action</div>
        <div className="launch-row">
          <span>{String(action.label ?? "Review activation packet")}</span>
          <em>
            {String(action.action_type ?? "internal_review").replace(/_/g, " ")}
            {currentMilestone ? ` · ${String(currentMilestone.label ?? "")}` : ""}
          </em>
        </div>
      </div>
    </div>
  );
}

function LaunchMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="launch-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function LaunchRail({ rail }: { rail: Record<string, unknown> }) {
  const current = asNumber(rail.current_value);
  const target = asNumber(rail.target_value);
  const progress =
    current === null || target === null || target === 0
      ? null
      : rail.rail === "ttv_priority"
        ? Math.max(0, Math.min(100, 100 - (current / Math.max(target + current, 1)) * 100))
        : Math.max(0, Math.min(100, (current / target) * 100));
  const factors = asArray(rail.factors);
  return (
    <div className="launch-rail">
      <div className="launch-rail-top">
        <span>{String(rail.rail ?? "rail").replace(/_/g, " ")}</span>
        <em>{String(rail.state ?? "unknown")}</em>
      </div>
      <div className="launch-bar" title={String(rail.interpretation ?? "")}>
        <span style={{ width: `${progress ?? 0}%` }} />
      </div>
      <div className="launch-rail-meta">
        <span>{numberOrDash(current)} now</span>
        <span>{numberOrDash(target)} target</span>
        <span>{factors.length} factor{factors.length === 1 ? "" : "s"}</span>
      </div>
    </div>
  );
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function numberOrDash(value: unknown): string {
  const n = asNumber(value);
  if (n === null) return "—";
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

function PacketTrace({ packet }: { packet: CSMWorkPacket }) {
  return (
    <div className="sec packet-trace">
      <div className="sec-h">
        <span className="t">Drill down</span>
        <span className="prov">
          <span className="chip-det">{Math.round(packet.confidence * 100)}% confidence</span>
        </span>
      </div>
      <details open>
        <summary>Diagnostic chain</summary>
        <div className="trace-body">
          <p>{packet.diagnostic_hypothesis.summary}</p>
          {packet.diagnostic_hypothesis.signals.map((signal) => (
            <div className="trace-line" key={signal}>{signal}</div>
          ))}
          {packet.open_questions.length > 0 && (
            <div className="trace-muted">Open: {packet.open_questions.join("; ")}</div>
          )}
        </div>
      </details>
      <details>
        <summary>Evidence</summary>
        <div className="trace-body">
          {packet.evidence_chain.length === 0 && (
            <div className="trace-muted">No confident evidence chain for this packet.</div>
          )}
          {packet.evidence_chain.map((step) => (
            <div className="source-card" key={step.step_id}>
              <div className="source-head">
                <span>{step.source_type}</span>
                <span className="mono">{step.source_id.slice(0, 10)}</span>
                <span>{step.strength}</span>
              </div>
              <strong>{step.claim}</strong>
              <p>{step.interpretation}</p>
              <em>{step.observed_value}</em>
            </div>
          ))}
        </div>
      </details>
      <details>
        <summary>Why this bucket?</summary>
        <div className="trace-body">
          <div className="trace-line">{packet.bucket_trace.rule_label}</div>
          <div className="trace-muted">Matched: {packet.bucket_trace.matched.join(", ")}</div>
          <div className="trace-muted">
            Coverage: {packet.coverage_trace.included_reason}
            {packet.coverage_trace.excluded_or_suppressed_reason
              ? ` · ${packet.coverage_trace.excluded_or_suppressed_reason}`
              : ""}
          </div>
          <div className="trace-muted">
            Scanned {packet.coverage_trace.accounts_scanned} of {packet.coverage_trace.book_size}
          </div>
        </div>
      </details>
      <details>
        <summary>Leave feedback</summary>
        <div className="feedback-grid">
          {packet.feedback_hooks.map((hook) => (
            <button className="feedback-chip" key={hook.category} title={hook.readonly_behavior}>
              {hook.label}
            </button>
          ))}
        </div>
      </details>
    </div>
  );
}

function InternalHandoff({
  decision,
}: {
  decision: WorkItem["internal_bridge_decision"] | null;
}) {
  if (!decision) return null;
  const target = decision.abstained ? "No internal handoff" : label(
    { engineering: "Engineering", product: "Product" },
    decision.target ?? "unknown"
  );
  const motion = decision.motion ? humanizeCode(decision.motion) : null;
  const signal = decision.signal ? humanizeCode(decision.signal) : null;

  return (
    <div className="sec">
      <div className="sec-h">
        <span className="t">Internal handoff</span>
        <span className="prov">
          <span className="chip-det">Rule-based · CRM evidence</span>
        </span>
      </div>
      <div className={`handoff-card${decision.abstained ? " abstain" : ""}`}>
        <div className="handoff-line">
          <span className="handoff-target">{target}</span>
          {motion && <span className="chip-det">{motion}</span>}
          {signal && <span className="chip-det">{signal}</span>}
        </div>
        <div className="handoff-reason">{decision.reason}</div>
        {decision.evidence.length > 0 && (
          <div className="handoff-evidence">
            {decision.evidence.map((ev, idx) => (
              <span key={`${ev.source_id}-${idx}`} className="mono">
                {ev.source}:{ev.source_id.slice(0, 8)}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Drawer({
  name,
  field,
  brief,
  formatter,
  open,
  onToggle,
}: {
  name: string;
  field: string | null;
  brief: Brief | null;
  formatter?: (row: unknown) => { name: string; meta: string };
  open: boolean;
  onToggle: () => void;
}) {
  const dormant = field === null;
  const rows = field && brief ? (brief[field] as unknown[]) : null;
  const summary = dormant
    ? "no live source yet"
    : rows
      ? `${rows.length} record${rows.length === 1 ? "" : "s"}`
      : "…";
  return (
    <div className="drawer">
      <div className={`drawer-h${dormant ? " dormant" : ""}`} onClick={onToggle}>
        <span className="dn">{name}</span>
        <span className="ds">{summary}</span>
      </div>
      {open && !dormant && (
        <div className="drawer-b">
          {(rows ?? []).map((row, i) =>
            <DrawerRow key={i} row={row} formatter={formatter ?? genericDrawerRowText} />
          )}
          {(rows ?? []).length === 0 && (
            <div className="evid-row">
              <span className="eval" style={{ color: "var(--fg-2)" }}>
                none
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Plain-language row for a humanized drawer source, reusing StakeholderPersonRow's
// established .stake-row shape (globals.css: plain-English primary text, NOT
// monospace by default -- unlike .evid-row/.eval which IS mono, wrong container
// for a formatted sentence) rather than adding a new CSS pattern per drawer.
function DrawerRow<T>({ row, formatter }: { row: T; formatter: (row: T) => { name: string; meta: string } }) {
  const { name, meta } = formatter(row);
  return (
    <div className="stake-row">
      <span className="sname">{name}</span>
      <span className="smeta">{meta}</span>
    </div>
  );
}

// Person UI depth (Harvest 17): the Stakeholders drawer deepened to render
// the real per-person role graph (UI_DESIGN_BRIEF's source-drawer spec:
// roles, champion/quiet flags, consent) instead of the generic Drawer's raw
// JSON-per-row dump. Still an in-place expansion inside account detail --
// no new view (two-view cap). No-fake-data: an account with no stakeholder
// graph (empty array from the API, never fabricated) shows honest dormant
// microcopy, same as every other drawer.
function StakeholderDrawer({
  brief,
  open,
  onToggle,
}: {
  brief: Brief | null;
  open: boolean;
  onToggle: () => void;
}) {
  const rows = (brief?.stakeholders as StakeholderRow[] | undefined) ?? null;
  const championActive = rows?.some((r) => r.champion && !r.departed);
  const quietCount = rows?.filter((r) => (r.days_since_interaction ?? 0) > 14).length ?? 0;
  const summary =
    rows === null
      ? "…"
      : rows.length === 0
        ? "no stakeholder graph for this account"
        : `${rows.length} contact${rows.length === 1 ? "" : "s"}` +
          (championActive ? " · champion active" : "") +
          (quietCount > 0 ? ` · ${quietCount} quiet` : "");

  return (
    <div className="drawer">
      <div className={`drawer-h${rows !== null && rows.length === 0 ? " dormant" : ""}`} onClick={onToggle}>
        <span className="dn">Stakeholders</span>
        <span className="ds">{summary}</span>
      </div>
      {open && rows !== null && (
        <div className="drawer-b">
          {rows.length === 0 && (
            <div className="evid-row">
              <span className="eval" style={{ color: "var(--fg-2)" }}>
                no stakeholder graph for this account
              </span>
            </div>
          )}
          {rows.map((r) => (
            <StakeholderPersonRow key={r.contact_id} row={r} />
          ))}
        </div>
      )}
    </div>
  );
}

function StakeholderPersonRow({ row }: { row: StakeholderRow }) {
  const recency =
    row.days_since_interaction === null
      ? null
      : row.days_since_interaction <= 14
        ? `active ${row.days_since_interaction}d`
        : `quiet ${row.days_since_interaction}d`;
  const quiet = (row.days_since_interaction ?? 0) > 14;

  return (
    <div className="stake-row">
      <span className="sname">{row.name}</span>
      <span className="smeta">
        {row.title ? `${row.title} · ` : ""}
        {row.relationship_type && (
          <span title={row.relationship_type}>{label(ROLE_LABELS, row.relationship_type)} · </span>
        )}
        {recency && <span style={{ color: quiet ? "var(--warn)" : "var(--fg-2)" }}>{recency} · </span>}
        {row.consent_to_contact ? (
          "consent ✓"
        ) : (
          <span style={{ color: "var(--danger)" }}>consent ✗ — no outreach permitted</span>
        )}
      </span>
      {row.departed && (
        <span className="mono" style={{ color: "var(--danger)" }}>
          departed
        </span>
      )}
      {row.new_unengaged && (
        <span className="mono" style={{ color: "var(--warn)" }}>
          new · unengaged
        </span>
      )}
    </div>
  );
}

const COMMS_TABS: { key: string; label: string; field: string }[] = [
  { key: "gmail", label: "Gmail", field: "comms_gmail" },
  { key: "calls", label: "Call Transcripts", field: "comms_call_transcripts" },
  { key: "internal", label: "Internal", field: "comms_internal" },
];

// One human-readable line per row, source-shape-aware -- mirrors the
// original design mockup's comms rows (source tag + natural-language
// line, e.g. "gmail · re: rollout timeline · replied 3.1h"), not a raw
// JSON dump. Does NOT synthesize a claim the data doesn't carry (e.g. the
// mockup's hand-authored "vs 4h norm" comparison) -- only formats fields
// the row actually has.
function commsRowText(field: string, row: Record<string, unknown>): { source: string; line: string } {
  if (field === "comms_internal") {
    const author = (row.author as string) ?? "unknown";
    const content = String(row.content ?? "").slice(0, 100);
    return { source: (row.source as string) === "slack" ? "slack" : "note", line: `${author}: ${content}` };
  }
  const direction = (row.direction as string) ?? "";
  const timestamp = (row.timestamp as string) ?? "";
  const responseHours = row.response_time_hours as number | null | undefined;
  const replySuffix = typeof responseHours === "number" ? ` · replied in ${responseHours}h` : "";
  return { source: (row.channel as string) ?? "comms", line: `${direction}${replySuffix} · ${timestamp}` };
}

// Three customer/internal comms sources (Gmail, Notion call transcripts,
// internal notes -- see api.py's AccountBriefResponse), one drawer, own
// tab strip -- distinct from the generic single-field Drawer below because
// no other drawer needs a multi-source split.
function CommsDrawer({
  brief,
  open,
  onToggle,
}: {
  brief: Brief | null;
  open: boolean;
  onToggle: () => void;
}) {
  const [activeTab, setActiveTab] = useState(COMMS_TABS[0].key);
  const rowsByTab = COMMS_TABS.map((t) => ({
    ...t,
    rows: (brief?.[t.field] as unknown[] | undefined) ?? [],
  }));
  const total = rowsByTab.reduce((sum, t) => sum + t.rows.length, 0);
  const active = rowsByTab.find((t) => t.key === activeTab) ?? rowsByTab[0];

  return (
    <div className="drawer">
      <div className="drawer-h" onClick={onToggle}>
        <span className="dn">Comms</span>
        <span className="ds">{total} record{total === 1 ? "" : "s"} across 3 sources</span>
      </div>
      {open && (
        <div className="drawer-b">
          <div className="sec-h" style={{ marginBottom: 4 }}>
            {rowsByTab.map((t) => (
              <span
                key={t.key}
                className="tierpill"
                style={{ cursor: "pointer", marginRight: 6, opacity: t.key === activeTab ? 1 : 0.55 }}
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveTab(t.key);
                }}
              >
                {t.label} ({t.rows.length})
              </span>
            ))}
          </div>
          {active.rows.map((row, i) => {
            const { source, line } = commsRowText(active.field, row as Record<string, unknown>);
            return (
              <div className="evid-row" key={i}>
                <span className="esys">{source}</span>
                <span className="eval">{line}</span>
              </div>
            );
          })}
          {active.rows.length === 0 && (
            <div className="evid-row">
              <span className="eval" style={{ color: "var(--fg-2)" }}>
                none
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CentralizeDrawer({
  telemetry,
  open,
  onToggle,
}: {
  telemetry: CentralizeTelemetryResponse | null;
  open: boolean;
  onToggle: () => void;
}) {
  const appEvents = telemetry?.app_events ?? null;
  const posthogEvents = telemetry?.posthog_events ?? null;
  const derivedSignals = telemetry?.derived_usage_signals ?? null;
  const total =
    appEvents === null || posthogEvents === null || derivedSignals === null
      ? null
      : appEvents.length + posthogEvents.length + derivedSignals.length;
  const summary =
    total === null
      ? "…"
      : `${appEvents?.length ?? 0} app · ${posthogEvents?.length ?? 0} posthog · ${derivedSignals?.length ?? 0} rollups`;

  return (
    <div className="drawer">
      <div className="drawer-h" onClick={onToggle}>
        <span className="dn">Centralize</span>
        <span className="ds">{summary}</span>
      </div>
      {open && (
        <div className="drawer-b">
          {telemetry === null ? (
            <div className="evid-row">
              <span className="eval" style={{ color: "var(--fg-2)" }}>
                loading
              </span>
            </div>
          ) : (
            <>
              <CentralizeRows
                label="app"
                rows={telemetry.app_events.slice(0, 5)}
                formatter={centralizeAppEventText}
              />
              <CentralizeRows
                label="posthog"
                rows={telemetry.posthog_events.slice(0, 5)}
                formatter={centralizePosthogEventText}
              />
              <CentralizeRows
                label="rollup"
                rows={telemetry.derived_usage_signals.slice(0, 4)}
                formatter={centralizeUsageSignalText}
              />
            </>
          )}
        </div>
      )}
    </div>
  );
}

function CentralizeRows({
  label,
  rows,
  formatter,
}: {
  label: string;
  rows: Record<string, unknown>[];
  formatter: (row: Record<string, unknown>) => { name: string; meta: string };
}) {
  return (
    <>
      {rows.map((row, i) => {
        const text = formatter(row);
        return (
          <div className="stake-row" key={`${label}-${i}`}>
            <span className="sname">{text.name}</span>
            <span className="smeta">
              <span className="mono" style={{ color: "var(--fg-2)" }}>{label}</span> · {text.meta}
            </span>
          </div>
        );
      })}
      {rows.length === 0 && (
        <div className="evid-row">
          <span className="eval" style={{ color: "var(--fg-2)" }}>
            no {label} records
          </span>
        </div>
      )}
    </>
  );
}

function centralizeAppEventText(row: Record<string, unknown>): { name: string; meta: string } {
  const eventType = String(row.event_type ?? "app event");
  const feature = String(row.feature ?? "centralize");
  const at = String(row.observed_at ?? "").slice(0, 10);
  return { name: humanizeCode(eventType), meta: `${feature} · ${at}` };
}

function centralizePosthogEventText(row: Record<string, unknown>): { name: string; meta: string } {
  const event = String(row.event ?? "posthog event");
  const url = String(row.current_url ?? "");
  const path = url ? url.replace("https://app.usecentralize.com", "") : "session";
  const flags = row.contains_exception ? " · exception" : row.contains_console_logs ? " · console" : "";
  return { name: event, meta: `${path}${flags}` };
}

function centralizeUsageSignalText(row: Record<string, unknown>): { name: string; meta: string } {
  const metric = String(row.metric_name ?? "usage signal");
  const value = typeof row.value === "number" ? row.value : Number(row.value ?? 0);
  const unit = String(row.unit ?? "events");
  const at = String(row.observed_at ?? "").slice(0, 10);
  return { name: humanizeCode(metric), meta: `${value} ${unit} · ${at}` };
}

function ProgramDetail({ item }: { item: WorkItem }) {
  return (
    <div className="detail-scroll">
      <div className="identity">
        <div className="mono-avatar">P</div>
        <div>
          <div className="id-name">Cohort finding</div>
          <div className="id-meta">
            <span className="tierpill">population analysis</span>
            <span>{item.candidate_account_ids.length} accounts affected</span>
          </div>
        </div>
      </div>
      <div className="sec">
        <div className="sec-h">
          <span className="t">The pattern</span>
        </div>
        <div className="resolve">
          <div className="why">{item.reason}</div>
        </div>
      </div>
    </div>
  );
}

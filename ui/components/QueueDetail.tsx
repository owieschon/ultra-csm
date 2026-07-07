"use client";

import { useEffect, useState } from "react";
import { api, WorkItem } from "@/lib/api";
import { label, MOTION_LABELS, TRIGGER_LABELS } from "@/lib/labels";
import { describeWork } from "@/lib/work";
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

export function QueueDetail({ item, day }: { item: WorkItem; day: number | undefined }) {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [openDrawer, setOpenDrawer] = useState<string | null>(null);
  const [openFactor, setOpenFactor] = useState<number | null>(null);

  useEffect(() => {
    setBrief(null);
    if (!item.account_id) return;
    api
      .accountBrief(item.account_id, day)
      .then(setBrief)
      .catch(() => setBrief(null));
  }, [item.account_id, day]);

  if (item.account_id === null) {
    return <ProgramDetail item={item} />;
  }

  return (
    <div className="detail-scroll">
      <WorkPacket item={item} brief={brief} />

      <div className="sec">
        <div className="sec-h">
          <span className="t">Evidence receipt — why now</span>
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
          <span className="t">Agent-prepared work</span>
          <span className="prov">
            <span className="chip-det">Operator review</span>
          </span>
        </div>
        <div className="resolve">
          <div className="line">
            <span className="m-final" title={item.motion ?? undefined}>
              {item.motion ? label(MOTION_LABELS, item.motion) : "prepared review"}
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
            <span className="t">Draft or packet body</span>
            <span className="prov">
              <span className="chip-llm">AI-written — needs your approval</span>
            </span>
          </div>
          <div className="draft">
            <div className="draft-h">customer-facing draft · release gated</div>
            <div className="draft-body">{item.customer_draft}</div>
          </div>
        </div>
      )}
      <div className="sec">
        <div className="sec-h">
          <span className="t">Account context</span>
          <span className="prov">
            <span className="chip-det">8 systems — 5 live, 3 no source yet</span>
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
          ) : (
            <Drawer key={d.key} name={d.name} field={d.briefField} brief={brief} formatter={d.formatter} open={openDrawer === d.key}
              onToggle={() => setOpenDrawer(openDrawer === d.key ? null : d.key)} />
          )
        )}
      </div>
    </div>
  );
}

function WorkPacket({ item, brief }: { item: WorkItem; brief: Brief | null }) {
  const descriptor = describeWork(item);
  const accountName = (brief?.account_name as string | undefined) ?? item.account_id ?? "Program work";
  const lifecycleStage = (brief?.lifecycle_stage as string | undefined) ?? null;
  const trajectory = brief?.trajectory as Record<string, unknown> | undefined;
  const trend = typeof trajectory?.trend === "string" ? trajectory.trend : null;
  const opportunities = (brief?.opportunities as unknown[] | undefined) ?? [];
  const hasBridge = Boolean(
    item.internal_bridge_decision && !item.internal_bridge_decision.abstained
  );

  return (
    <div className="work-packet">
      <div className="work-top">
        <div className="mono-avatar">{accountName.slice(0, 2).toUpperCase()}</div>
        <div>
          <div className="work-kicker">
            <span className={`cadence ${descriptor.cadence}`}>{descriptor.cadenceLabel}</span>
            <span>{descriptor.kindLabel}</span>
            <span>{descriptor.authorityLabel}</span>
          </div>
          <div className="work-title">{descriptor.packetLabel}</div>
          <div className="work-account">
            {accountName}
            {lifecycleStage ? ` · ${humanizeCode(lifecycleStage)}` : ""}
          </div>
        </div>
      </div>
      <div className="work-grid">
        <div>
          <div className="work-label">CS operating job</div>
          <div className="work-copy">
            Agents prepared this {descriptor.cadenceLabel.toLowerCase()} packet for the CSM to review, edit, route, or release.
          </div>
        </div>
        <div>
          <div className="work-label">Receipts in packet</div>
          <div className="work-chips">
            <span className="chip-det">{item.priority?.factors.length ?? 0} value signals</span>
            {trend && <span className="chip-det">trajectory: {trend}</span>}
            {opportunities.length > 0 && (
              <span className="chip-det">{opportunities.length} opportunity</span>
            )}
            {hasBridge && <span className="chip-det">internal briefing ready</span>}
          </div>
        </div>
      </div>
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

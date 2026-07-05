"use client";

import { useEffect, useState } from "react";
import { api, WorkItem } from "@/lib/api";
import { label, MOTION_LABELS, TRIGGER_LABELS } from "@/lib/labels";

type Brief = Record<string, unknown>;

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

// Drawer -> brief field mapping, verified against api.py's AccountBriefResponse
// (Phase 1's contract table). Stakeholders now reads the additive
// `stakeholders` field (per-person role graph) instead of raw `contacts`.
// Comms/Calendar/Agent-history have NO live source anywhere this endpoint
// reads from -- rendered dormant honestly, never populated with placeholder
// rows (UI_DESIGN_BRIEF's no-fake-data rule).
const DRAWERS: { key: string; name: string; briefField: string | null }[] = [
  { key: "comms", name: "Comms", briefField: null },
  { key: "calendar", name: "Calendar", briefField: null },
  { key: "people", name: "Stakeholders", briefField: "stakeholders" },
  { key: "onboarding", name: "Onboarding (Rocketlane)", briefField: "milestones" },
  { key: "telemetry", name: "Telemetry", briefField: "recent_usage_signals" },
  { key: "plan", name: "Success plan", briefField: "success_plans" },
  { key: "cases", name: "Cases", briefField: "open_cases" },
  { key: "agent", name: "Agent history", briefField: null },
];

export function QueueDetail({ item, day }: { item: WorkItem; day: number }) {
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
      <div className="identity">
        <div className="mono-avatar">
          {(brief?.account_name as string | undefined)?.slice(0, 2).toUpperCase() ?? "··"}
        </div>
        <div>
          <div className="id-name">
            {(brief?.account_name as string) ?? item.account_id}
          </div>
          <div className="id-meta">
            <span className="tierpill">
              {(brief?.lifecycle_stage as string) ?? "—"}
            </span>
          </div>
        </div>
      </div>

      <div className="sec">
        <div className="sec-h">
          <span className="t">Account sources</span>
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
          ) : (
            <Drawer key={d.key} name={d.name} field={d.briefField} brief={brief} open={openDrawer === d.key}
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
                <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>
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
                          <span className="mono" style={{ marginLeft: 6, color: "var(--fg-3)" }}>
                            {(ev.source as string) ?? "crm"} · {String(ev.source_id ?? "").slice(0, 8)}
                          </span>
                        </span>
                      ) : (
                        <span className="eval">{JSON.stringify(ev).slice(0, 120)}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>

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

function Drawer({
  name,
  field,
  brief,
  open,
  onToggle,
}: {
  name: string;
  field: string | null;
  brief: Brief | null;
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
          {(rows ?? []).map((row, i) => (
            <div className="evid-row" key={i}>
              <span className="eval">{JSON.stringify(row).slice(0, 160)}</span>
            </div>
          ))}
          {(rows ?? []).length === 0 && (
            <div className="evid-row">
              <span className="eval" style={{ color: "var(--fg-3)" }}>
                none
              </span>
            </div>
          )}
        </div>
      )}
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
              <span className="eval" style={{ color: "var(--fg-3)" }}>
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

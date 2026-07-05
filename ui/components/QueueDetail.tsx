"use client";

import { useEffect, useState } from "react";
import { api, WorkItem } from "@/lib/api";
import { label, MOTION_LABELS, TRIGGER_LABELS } from "@/lib/labels";

type Brief = Record<string, unknown>;

// Drawer -> brief field mapping, verified against api.py's AccountBriefResponse
// (Phase 1's contract table). Comms/Calendar/Agent-history have NO live
// source anywhere this endpoint reads from -- rendered dormant honestly,
// never populated with placeholder rows (UI_DESIGN_BRIEF's no-fake-data rule).
const DRAWERS: { key: string; name: string; briefField: string | null }[] = [
  { key: "comms", name: "Comms", briefField: null },
  { key: "calendar", name: "Calendar", briefField: null },
  { key: "people", name: "Stakeholders", briefField: "contacts" },
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
        {DRAWERS.map((d) => (
          <Drawer key={d.key} name={d.name} field={d.briefField} brief={brief} open={openDrawer === d.key}
            onToggle={() => setOpenDrawer(openDrawer === d.key ? null : d.key)} />
        ))}
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
                {(factor.evidence ?? []).map((ev, ei) => (
                  <div className="evid-row" key={ei}>
                    <span className="esys">
                      {(ev.source as string) ?? "evidence"}
                    </span>
                    <span className="eval">
                      {JSON.stringify(ev).slice(0, 120)}
                    </span>
                  </div>
                ))}
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

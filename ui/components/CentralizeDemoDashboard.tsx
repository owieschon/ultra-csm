"use client";

import { useEffect, useMemo, useState } from "react";
import { api, CentralizeDemoDashboardResponse, CentralizeDemoMoment } from "@/lib/api";

export function CentralizeDemoDashboard({
  day,
  onOpenQueue,
}: {
  day: number | undefined;
  onOpenQueue: () => void;
}) {
  const [dashboard, setDashboard] = useState<CentralizeDemoDashboardResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api
      .centralizeDemoDashboard(day)
      .then((response) => {
        setDashboard(response);
        setSelectedId(response.moments[0]?.moment_id ?? null);
        setFailed(false);
      })
      .catch(() => setFailed(true));
  }, [day]);

  const selected = useMemo(
    () => dashboard?.moments.find((moment) => moment.moment_id === selectedId) ?? dashboard?.moments[0] ?? null,
    [dashboard, selectedId]
  );

  if (failed) {
    return <div className="placeholder-view">Centralize demo data unavailable.</div>;
  }
  if (!dashboard || !selected) {
    return <div className="placeholder-view">Loading Centralize demo…</div>;
  }

  return (
    <div className="centralize-demo">
      <div className="centralize-demo-head">
        <div>
          <div className="packet-kicker">Centralize simulated product data</div>
          <h1>{dashboard.summary.title}</h1>
          <p>{dashboard.summary.job}</p>
          <div className="centralize-integration-strip" aria-label="Simulated Centralize integrations">
            {dashboard.summary.integrations.map((integration) => (
              <span key={integration}>{integration}</span>
            ))}
          </div>
        </div>
        <div className="centralize-demo-stats">
          <DemoStat label="Moments" value={dashboard.summary.moment_count} />
          <DemoStat label="Ready" value={dashboard.summary.ready_count} />
          <DemoStat label="Internal" value={dashboard.summary.internal_only_count} />
          <DemoStat label="Judgment" value={dashboard.summary.needs_judgment_count} />
        </div>
      </div>

      <div className="centralize-demo-grid">
        <section className="centralize-demo-list" aria-label="Agent moments">
          <div className="sec-h">
            <span className="t">Agent-heavy CSM moments</span>
            <span className="prov">
              <span className="chip-det">simulated · no customer writes</span>
            </span>
          </div>
          {dashboard.moments.map((moment) => (
            <MomentButton
              key={moment.moment_id}
              moment={moment}
              selected={moment.moment_id === selected.moment_id}
              onSelect={() => setSelectedId(moment.moment_id)}
            />
          ))}
        </section>

        <section className="centralize-demo-main">
          <div className="centralize-demo-card">
            <div className="launch-head">
              <div>
                <div className="launch-title">{selected.title}</div>
                <div className="launch-meta">
                  {selected.simulated_customer} · day {selected.story_day} · {selected.workflow}
                </div>
              </div>
              <div className="launch-score">
                <span className="num">{selected.status === "ready" ? "go" : "hold"}</span>
                <em>{selected.status.replace(/_/g, " ")}</em>
              </div>
            </div>

            <div className="launch-grid">
              <LaunchMetric label="Surface" value={selected.product_surface} />
              <LaunchMetric label="Value path" value={selected.value_path} />
              <LaunchMetric label="Trigger" value={selected.trigger} />
              <LaunchMetric label="Manual work" value={selected.manual_work_replaced} />
            </div>

            <div className="centralize-heavy-lift">
              <div className="packet-kicker">What the agent assembled</div>
              {selected.agent_heavy_lift.map((line) => (
                <div className="centralize-lift-row" key={line}>{line}</div>
              ))}
            </div>

            <div className="centralize-takeaway">
              <strong>{selected.csm_takeaway}</strong>
              <span>{selected.suggested_next_step}</span>
            </div>
          </div>

          <div className="centralize-demo-columns">
            <EvidencePanel title="Feature metrics" rows={selected.feature_metrics} kind="metric" />
            <EvidencePanel title="Source receipts" rows={selected.source_receipts} kind="receipt" />
          </div>

          <button className="centralize-demo-queue" onClick={onOpenQueue}>
            Open the governed work queue
          </button>
        </section>
      </div>
    </div>
  );
}

function DemoStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="centralize-demo-stat">
      <strong className="num">{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function MomentButton({
  moment,
  selected,
  onSelect,
}: {
  moment: CentralizeDemoMoment;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button className={`centralize-moment${selected ? " selected" : ""}`} onClick={onSelect}>
      <span className={`centralize-status ${moment.status}`}>{moment.status.replace(/_/g, " ")}</span>
      <strong>{moment.title}</strong>
      <em>{moment.product_surface}</em>
    </button>
  );
}

function LaunchMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="launch-metric">
      <span>{label}</span>
      <strong title={value}>{value}</strong>
    </div>
  );
}

function EvidencePanel({
  title,
  rows,
  kind,
}: {
  title: string;
  rows: Record<string, unknown>[];
  kind: "metric" | "receipt";
}) {
  return (
    <div className="centralize-evidence-panel">
      <div className="packet-kicker">{title}</div>
      {rows.slice(0, 7).map((row, index) => {
        const primary = kind === "metric"
          ? String(row.metric_name ?? "metric").replace(/_/g, " ")
          : String(row.field ?? "receipt").replace(/_/g, " ");
        const meta = kind === "metric"
          ? `${String(row.value ?? "—")} ${String(row.unit ?? "")} · ${String(row.source_ref ?? "")}`
          : `${String(row.source_type ?? "source")} · ${String(row.feature ?? "")}`;
        return (
          <div className="launch-row" key={`${primary}-${index}`}>
            <span>{primary}</span>
            <em>{meta}</em>
          </div>
        );
      })}
    </div>
  );
}

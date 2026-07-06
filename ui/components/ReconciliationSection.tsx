"use client";

import { useEffect, useState } from "react";
import {
  api,
  CandidateDivergenceRow,
  DeterministicSignalRow,
  EvidenceRefRow,
  ReconciliationResponse,
} from "@/lib/api";
import { label, TRIGGER_LABELS } from "@/lib/labels";

// Reconciliation agent (Harvest 31/32, report 52/53): reconciles what CS
// tools report against what telemetry shows for this account. An
// EXPANSION inside account detail -- no new view (two-view cap holds).
// The UI computes nothing (K13): every value below is already resolved
// server-side; this component only renders and formats.
function evidenceLine(ref: EvidenceRefRow): string {
  return `${ref.source} · ${ref.field} · observed ${ref.observed_at.slice(0, 10)}`;
}

function DeterministicSignalRowView({ signal }: { signal: DeterministicSignalRow }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <div className="factor" onClick={() => setOpen(!open)}>
        <span className="fname">{label(TRIGGER_LABELS, signal.name)}</span>
        <span className="contrib" title={`adds ${signal.contribution} points`}>
          +{signal.contribution}
        </span>
        <span className="fmeta">
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)" }}>
            {signal.name}
          </span>
          <span>{signal.surfaced_by_lenses.join(", ")}</span>
        </span>
      </div>
      {open && (
        <div className="evid-in">
          {signal.evidence.map((ref, i) => (
            <div className="evid-row" key={i}>
              <span className="esys">{ref.source}</span>
              <span className="eval">
                {evidenceLine(ref)}
                <span className="mono" style={{ marginLeft: 6, color: "var(--fg-3)" }}>
                  {ref.source_id.slice(0, 8)}
                </span>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CandidateDivergenceRowView({ candidate }: { candidate: CandidateDivergenceRow }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <div className="hyp-row" onClick={() => setOpen(!open)}>
        <span className="hyp-badge">Hypothesis — not verified</span>
        <span className="hyp-claim">{candidate.claim}</span>
        <span className="hyp-conf">{candidate.confidence} confidence</span>
      </div>
      <div className="hyp-disclaimer">{candidate.disclaimer}</div>
      {open && (
        <div className="evid-in">
          {candidate.evidence.map((ref, i) => (
            <div className="evid-row" key={i}>
              <span className="esys">{ref.source}</span>
              <span className="eval">
                {evidenceLine(ref)}
                <span className="mono" style={{ marginLeft: 6, color: "var(--fg-3)" }}>
                  {ref.source_id.slice(0, 8)}
                </span>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ReconciliationSection({
  accountId,
  day,
}: {
  accountId: string;
  day: number | undefined;
}) {
  const [data, setData] = useState<ReconciliationResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setData(null);
    setFailed(false);
    api
      .accountReconciliation(accountId, day)
      .then(setData)
      .catch(() => setFailed(true));
  }, [accountId, day]);

  const noSignal =
    data !== null &&
    data.deterministic_signals.length === 0 &&
    data.candidate_divergences.length === 0;

  return (
    <div className="sec">
      <div className="sec-h">
        <span className="t">Reconciliation — reported vs. experienced</span>
        <span className="prov">
          <span className="chip-det">Rule-based signals · AI-explained</span>
        </span>
      </div>

      {failed && (
        <div className="evid-row">
          <span className="eval" style={{ color: "var(--fg-3)" }}>
            no reconciliation signal for this account
          </span>
        </div>
      )}

      {data && noSignal && (
        <div className="evid-row">
          <span className="eval" style={{ color: "var(--fg-3)" }}>
            no reconciliation signal for this account
          </span>
        </div>
      )}

      {data && !noSignal && (
        <>
          {data.deterministic_signals.map((signal) => (
            <DeterministicSignalRowView key={signal.name} signal={signal} />
          ))}

          <div className="rec-explain">
            <span className="chip-llm" style={{ marginBottom: 6, display: "inline-block" }}>
              AI-written — explanation only
            </span>
            <div>{data.explanation.text}</div>
          </div>
          <div className="hyp-disclaimer">{data.explanation.disclaimer}</div>

          {data.candidate_divergences.map((candidate, i) => (
            <CandidateDivergenceRowView key={i} candidate={candidate} />
          ))}
        </>
      )}
    </div>
  );
}

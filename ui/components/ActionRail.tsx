"use client";

import { useEffect, useState } from "react";
import { api, LedgerEvent, WorkItem } from "@/lib/api";
import { PROPOSAL_STATUS_LABELS, label } from "@/lib/labels";

export function ActionRail({
  item,
  onVerdict,
}: {
  item: WorkItem | null;
  onVerdict: (proposalId: string) => void;
}) {
  const [ledger, setLedger] = useState<LedgerEvent[]>([]);
  const [ledgerGap, setLedgerGap] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshLedger = () => {
    api
      .ledger(50)
      .then((r) => {
        setLedger(r.events);
        setLedgerGap(r.ledger_gap);
      })
      .catch(() => {});
  };

  useEffect(() => {
    refreshLedger();
    const id = setInterval(refreshLedger, 5000);
    return () => clearInterval(id);
  }, []);

  const proposalId = item?.proposal?.proposal_id ?? null;
  const status = item?.proposal?.status ?? null;
  const canAct = proposalId != null && status === "pending";

  async function act(verdict: "approve" | "deny") {
    if (!proposalId) return;
    setBusy(true);
    setError(null);
    try {
      await api.submitVerdict(proposalId, verdict, "ops-surface UI action");
      refreshLedger();
      onVerdict(proposalId);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="rail-top">
        <div className="t">Decision</div>
        <div className="gate">
          {item ? (
            proposalId ? (
              <>
                proposal <span className="mono">{proposalId.slice(0, 8)}</span> ·{" "}
                <span className="st">{label(PROPOSAL_STATUS_LABELS, status)}</span>
              </>
            ) : (
              "no gate-tracked proposal for this item"
            )
          ) : (
            "select an item"
          )}
        </div>
        {error && (
          <div className="gate" style={{ color: "var(--danger)" }}>
            {error}
          </div>
        )}
      </div>
      <div className="actions">
        <button
          className="btn approve"
          disabled={!canAct || busy}
          onClick={() => act("approve")}
        >
          Approve &amp; send<span className="k">A</span>
        </button>
        <button className="btn edit" disabled title="revise endpoint pending">
          Edit draft<span className="k">E</span>
        </button>
        <button
          className="btn deny"
          disabled={!canAct || busy}
          onClick={() => act("deny")}
        >
          Deny<span className="k">D</span>
        </button>
      </div>
      <div className="audit">
        <div className="audit-h">
          <span className="t">Audit ledger</span>
          <span className="gap" title={ledgerGap.join(", ")}>
            {ledgerGap.length} event types have no live source yet
          </span>
        </div>
        <div className="ledger">
          {ledger.length === 0 && (
            <div className="lg">
              <span className="rest" style={{ color: "var(--fg-3)" }}>
                no proposal/verdict events yet this run
              </span>
            </div>
          )}
          {ledger.map((e, i) => (
            <div className="lg" key={i}>
              <span className="ts mono">{e.ts.slice(11, 19)}</span>
              <span className="ev" title={e.event}>
                {e.label}
              </span>
              <span className="rest">{e.detail}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

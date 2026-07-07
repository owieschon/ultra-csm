"use client";

import { forwardRef, useEffect, useImperativeHandle, useMemo, useState } from "react";
import { api, AllowedCTA, LedgerEvent } from "@/lib/api";
import { QueueSelection } from "@/components/QueueView";

export interface ActionRailHandle {
  approve: () => void;
  deny: () => void;
  edit: () => void;
}

export const ActionRail = forwardRef<
  ActionRailHandle,
  { selection: QueueSelection | null; onVerdict: (proposalId: string) => void; readOnly?: boolean }
>(function ActionRail({ selection, onVerdict, readOnly = false }, ref) {
  const [ledger, setLedger] = useState<LedgerEvent[]>([]);
  const [ledgerGap, setLedgerGap] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const packet = selection?.packet ?? null;
  const item = selection?.item ?? null;
  const proposalId = item?.proposal?.proposal_id ?? null;
  const artifact = packet?.prepared_artifacts[0] ?? null;
  const ctas = useMemo(() => packet?.allowed_ctas ?? [], [packet]);
  const ctaByKind = useMemo(
    () => new Map(ctas.map((cta) => [cta.kind, cta])),
    [ctas]
  );

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

  async function submit(verdict: "approve" | "deny" | "revise") {
    if (readOnly) {
      setError("Hosted demo is read-only. Governed execution is disabled.");
      return;
    }
    const cta = ctaByKind.get(verdict === "approve" ? "approve" : verdict === "deny" ? "reject" : "edit");
    if (!proposalId || !cta?.enabled || busy) {
      setError(cta?.disabled_reason ?? "This packet has no enabled governed action.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.submitVerdict(proposalId, verdict, `packet CTA: ${cta.cta_id}`);
      refreshLedger();
      onVerdict(proposalId);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  useImperativeHandle(ref, () => ({
    approve: () => submit("approve"),
    deny: () => submit("deny"),
    edit: () => setPreviewOpen(true),
  }));

  return (
    <>
      <div className="rail-top">
        <div className="t">Human action</div>
        <div className="gate">
          {packet ? (
            <>
              {packet.governance.mode.replace(/_/g, " ")} ·{" "}
              {packet.governance.requires_action_gate ? "ActionGate required" : "local review"}
            </>
          ) : (
            "select a packet"
          )}
        </div>
        {proposalId && (
          <div className="gate">
            proposal <span className="mono">{proposalId.slice(0, 8)}</span> ·{" "}
            {item?.proposal?.status}
          </div>
        )}
        {error && (
          <div className="gate" style={{ color: "var(--danger)" }}>
            {error}
          </div>
        )}
      </div>

      {previewOpen && artifact && (
        <div className="edit-panel">
          <div className="edit-label">{artifact.title}</div>
          <div className="rail-preview">{artifact.body_or_outline}</div>
        </div>
      )}

      <div className="actions">
        {ctas.map((cta) => (
          <CTAButton
            key={cta.cta_id}
            cta={cta}
            busy={busy}
            onClick={() => {
              if (cta.kind === "preview" || cta.kind === "inspect") {
                setPreviewOpen((open) => !open);
                setError(null);
              } else if (cta.kind === "approve") {
                submit("approve");
              } else if (cta.kind === "reject") {
                submit("deny");
              } else {
                setError(cta.readonly_behavior);
              }
            }}
          />
        ))}
      </div>

      <div className="audit">
        <div className="audit-h">
          <span className="t">Audit ledger</span>
          <span className="gap" title={ledgerGap.join(", ")}>
            {ledgerGap.length} event gaps
          </span>
        </div>
        <div className="ledger">
          {ledger.length === 0 && (
            <div className="lg">
              <span className="rest" style={{ color: "var(--fg-2)" }}>
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
});

function CTAButton({
  cta,
  busy,
  onClick,
}: {
  cta: AllowedCTA;
  busy: boolean;
  onClick: () => void;
}) {
  const className = cta.kind === "approve" ? "btn approve" : cta.kind === "reject" ? "btn deny" : "btn edit";
  return (
    <button
      className={className}
      disabled={busy || !cta.enabled}
      onClick={onClick}
      title={cta.disabled_reason ?? cta.readonly_behavior}
    >
      {cta.label}
      <span className="k">{cta.kind.replace(/_/g, " ")}</span>
    </button>
  );
}

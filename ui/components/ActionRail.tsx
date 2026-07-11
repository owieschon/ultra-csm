"use client";

import { forwardRef, useEffect, useImperativeHandle, useState } from "react";
import { api, LedgerEvent, WorkItem } from "@/lib/api";
import {
  DemoLedgerEvent,
  DemoVerdict,
  simulateApproval,
  simulateDenial,
  simulateRevision,
} from "@/lib/demoSim";
import { PROPOSAL_STATUS_LABELS, label } from "@/lib/labels";

export interface ActionRailHandle {
  approve: () => void;
  deny: () => void;
  edit: () => void;
}

export const ActionRail = forwardRef<
  ActionRailHandle,
  {
    item: WorkItem | null;
    onVerdict: (proposalId: string) => void;
    readOnly?: boolean;
    demoLedger?: DemoLedgerEvent[];
    onDemoVerdict?: (
      proposalId: string,
      verdict: DemoVerdict | null,
      events: DemoLedgerEvent[]
    ) => void;
  }
>(function ActionRail(
  { item, onVerdict, readOnly = false, demoLedger = [], onDemoVerdict },
  ref
) {
  const [ledger, setLedger] = useState<LedgerEvent[]>([]);
  const [ledgerGap, setLedgerGap] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editInstruction, setEditInstruction] = useState("");

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
  const packetCtas = item?.work_packet?.allowed_ctas ?? [];
  const gateApprovalCta = packetCtas.find((cta) => cta.cta_id === "request_gate_approval");
  const canAct =
    proposalId != null &&
    status === "pending" &&
    (gateApprovalCta ? gateApprovalCta.enabled : true);
  const canEdit = canAct && item?.proposal?.action_type === "draft_customer_outreach";
  const receiptEvents = proposalId
    ? [
        ...ledger.filter((event) => event.proposal_id === proposalId),
        ...demoLedger.filter((event) => event.proposal_id === proposalId),
      ].slice(-12)
    : [];

  useEffect(() => {
    if (!canEdit) {
      setEditOpen(false);
      setEditInstruction("");
    }
  }, [canEdit, proposalId]);

  // Hosted demo: the verdict is simulated client-side (labeled below and on
  // every simulated receipt line) — the live path posts through the gate.
  function actDemo(verdict: "approve" | "deny" | "revise") {
    if (!proposalId || !canAct) return;
    if (verdict === "revise") {
      const instruction = editInstruction.trim();
      if (!instruction) {
        setError("Add an edit instruction before saving.");
        return;
      }
      onDemoVerdict?.(proposalId, null, simulateRevision(proposalId, instruction));
      setEditOpen(false);
      setEditInstruction("");
      return;
    }
    setError(null);
    onDemoVerdict?.(
      proposalId,
      verdict === "approve" ? "approved" : "denied",
      verdict === "approve"
        ? simulateApproval(proposalId)
        : simulateDenial(proposalId)
    );
  }

  async function act(verdict: "approve" | "deny" | "revise") {
    if (readOnly) {
      actDemo(verdict);
      return;
    }
    if (!proposalId || !canAct || busy) return;
    if (verdict === "revise" && !canEdit) return;
    const instruction = editInstruction.trim();
    if (verdict === "revise" && !instruction) {
      setError("Add an edit instruction before saving.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.submitVerdict(
        proposalId,
        verdict,
        verdict === "revise" ? "ops-surface UI edit" : "ops-surface UI action",
        verdict === "revise" ? instruction : undefined
      );
      if (verdict === "revise") {
        setEditOpen(false);
        setEditInstruction("");
      }
      refreshLedger();
      onVerdict(proposalId);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  useImperativeHandle(ref, () => ({
    approve: () => act("approve"),
    deny: () => act("deny"),
    edit: () => {
      if (canEdit) setEditOpen(true);
    },
  }));

  return (
    <>
      <div className="rail-top">
        <h2 className="t">Decision</h2>
        <div className="gate">
          {item ? (
            proposalId ? (
              <>
                proposal <span className="mono">{proposalId.slice(0, 8)}</span> ·{" "}
                <span className="st">
                  {readOnly && status === "approved"
                    ? "approved · sent (simulated)"
                    : label(PROPOSAL_STATUS_LABELS, status)}
                </span>
              </>
            ) : (
              "no gate-tracked proposal for this item"
            )
          ) : (
            "select an item"
          )}
        </div>
        {error && (
          <div className="gate" role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </div>
        )}
        {readOnly && (
          <div className="gate" role="note">
            Simulated — decisions update this page only; nothing is sent
          </div>
        )}
      </div>
      <div className="actions" aria-label="Proposal actions">
        {packetCtas.length > 0 && (
          <div className="cta-stack">
            {packetCtas.map((cta) => (
              <div className={`cta-row${cta.enabled ? " on" : ""}`} key={cta.cta_id}>
                <span>{cta.label}</span>
                <span className="cta-state">
                  {cta.enabled ? "enabled" : "blocked"}
                </span>
              </div>
            ))}
          </div>
        )}
        <button
          type="button"
          className="btn approve"
          aria-keyshortcuts="A"
          disabled={!canAct || busy}
          onClick={() => act("approve")}
        >
          Approve exact draft<span className="k">A</span>
        </button>
        <button
          type="button"
          className="btn edit"
          aria-keyshortcuts="E"
          disabled={!canEdit || busy}
          onClick={() => setEditOpen((open) => !open)}
        >
          Edit draft<span className="k">E</span>
        </button>
        <button
          type="button"
          className="btn deny"
          aria-keyshortcuts="D"
          disabled={!canAct || busy}
          onClick={() => act("deny")}
        >
          Deny<span className="k">D</span>
        </button>
      </div>
      {editOpen && (
        <div className="edit-panel">
          <label className="edit-label" htmlFor="draft-edit-instruction">
            Edit instruction
          </label>
          <textarea
            id="draft-edit-instruction"
            className="edit-input"
            value={editInstruction}
            maxLength={280}
            disabled={busy}
            onChange={(e) => setEditInstruction(e.target.value)}
            placeholder="Make the tone warmer."
          />
          <div className="edit-actions">
            <span className="edit-count num">{editInstruction.length}/280</span>
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={() => {
                setEditOpen(false);
                setEditInstruction("");
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn approve"
              disabled={!canEdit || busy || !editInstruction.trim()}
              onClick={() => act("revise")}
            >
              Save edit
            </button>
          </div>
        </div>
      )}
      <div className="audit">
        <div className="audit-h">
          <span className="t">Decision receipt</span>
          {proposalId && (
            <span className="gap" title={ledgerGap.join(", ")}>
              {receiptEvents.length} events
              {ledgerGap.length > 0 ? ` · ${ledgerGap.length} source gaps` : ""}
            </span>
          )}
        </div>
        <div className="ledger" role="log" aria-live="polite" aria-label="Selected proposal receipt events">
          {proposalId && receiptEvents.length === 0 && (
            <div className="lg">
              <span className="rest" style={{ color: "var(--fg-2)" }}>
                no receipt events recorded for this proposal
              </span>
            </div>
          )}
          {!proposalId && (
            <div className="lg">
              <span className="rest" style={{ color: "var(--fg-2)" }}>
                select a proposal to inspect its receipt
              </span>
            </div>
          )}
          {receiptEvents.map((e, i) => (
            <div className="lg" key={i}>
              {/* Sim lines happen in the viewer's wall-clock, not the
                  snapshot's day — "now" keeps the fixture world coherent. */}
              <span className="ts mono">
                {"simulated" in e && e.simulated === true
                  ? "now"
                  : e.ts.slice(11, 19)}
              </span>
              <span className="ev" title={e.event}>
                {e.label}
              </span>
              <span className="rest" title={e.detail}>
                {e.detail}
              </span>
              {"simulated" in e && e.simulated === true && (
                <span className="sim-chip" title="Simulated in this demo — not a backend event">
                  sim
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </>
  );
});

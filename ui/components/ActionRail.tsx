"use client";

import { forwardRef, useEffect, useImperativeHandle, useState } from "react";
import { api, LedgerEvent, WorkItem } from "@/lib/api";
import { PROPOSAL_STATUS_LABELS, label } from "@/lib/labels";

export interface ActionRailHandle {
  approve: () => void;
  deny: () => void;
  edit: () => void;
}

export const ActionRail = forwardRef<
  ActionRailHandle,
  { item: WorkItem | null; onVerdict: (proposalId: string) => void; readOnly?: boolean }
>(function ActionRail({ item, onVerdict, readOnly = false }, ref) {
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
  const canAct = proposalId != null && status === "pending";
  const canEdit = canAct && item?.proposal?.action_type === "draft_customer_outreach";

  useEffect(() => {
    if (!canEdit) {
      setEditOpen(false);
      setEditInstruction("");
    }
  }, [canEdit, proposalId]);

  async function act(verdict: "approve" | "deny" | "revise") {
    if (readOnly) {
      setError("Hosted demo is read-only. Decisions are disabled.");
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
      if (readOnly) {
        setError("Hosted demo is read-only. Decisions are disabled.");
      } else if (canEdit) setEditOpen(true);
    },
  }));

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
        {readOnly && (
          <div className="gate">
            hosted read-only demo — approvals and sends disabled
          </div>
        )}
      </div>
      <div className="actions">
        <button
          className="btn approve"
          disabled={readOnly || !canAct || busy}
          onClick={() => act("approve")}
        >
          Approve &amp; send<span className="k">A</span>
        </button>
        <button
          className="btn edit"
          disabled={readOnly || !canEdit || busy}
          onClick={() => setEditOpen((open) => !open)}
        >
          Edit draft<span className="k">E</span>
        </button>
        <button
          className="btn deny"
          disabled={readOnly || !canAct || busy}
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
});

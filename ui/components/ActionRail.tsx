"use client";

import { forwardRef, useEffect, useImperativeHandle, useState } from "react";
import { api, LedgerEvent, WorkItem } from "@/lib/api";
import {
  DemoApprovalSnapshot,
  DemoLedgerEvent,
  DemoVerdict,
  simulateApproval,
  simulateDenial,
} from "@/lib/demoSim";
import { replacementItem } from "@/lib/revisions";
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
    onVerdict: (item: WorkItem, replacement?: WorkItem) => void;
    readOnly?: boolean;
    demoLedger?: DemoLedgerEvent[];
    onDemoVerdict?: (
      proposalId: string,
      verdict: DemoVerdict | null,
      events: DemoLedgerEvent[],
      snapshot?: { revisionId: string; body: string }
    ) => void;
    onDemoEdit?: (proposalId: string, newBody: string, expectedRevision: string) => void;
    demoApprovals?: Record<string, DemoApprovalSnapshot>;
  }
>(function ActionRail(
  {
    item,
    onVerdict,
    readOnly = false,
    demoLedger = [],
    onDemoVerdict,
    onDemoEdit,
    demoApprovals = {},
  },
  ref
) {
  const [ledger, setLedger] = useState<LedgerEvent[]>([]);
  const [ledgerGap, setLedgerGap] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editText, setEditText] = useState("");

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
  const canEdit = canAct && !item?.redrafted_from && item?.proposal?.action_type === "draft_customer_outreach";
  const receiptEvents = proposalId
    ? [
        ...ledger.filter((event) => event.proposal_id === proposalId),
        ...demoLedger.filter((event) => event.proposal_id === proposalId),
      ].slice(-12)
    : [];
  const approvalSnapshot = proposalId ? demoApprovals[proposalId] ?? null : null;

  function openEdit() {
    if (!canEdit) return;
    setError(null);
    setEditText(readOnly ? item?.customer_draft ?? "" : "");
    setEditOpen(true);
  }

  function closeEdit() {
    setEditOpen(false);
    setEditText("");
  }

  function actDemo(action: "approve" | "deny" | "edit-save", newBody?: string) {
    if (!proposalId || !canAct) return;
    if (action === "edit-save") {
      const trimmed = (newBody ?? "").trim();
      const current = (item?.customer_draft ?? "").trim();
      if (!trimmed || trimmed === current) {
        setError(
          !trimmed
            ? "Draft text can't be blank."
            : "No changes to save — edit the text before saving."
        );
        return;
      }
      setError(null);
      onDemoEdit?.(proposalId, trimmed, item?.demo_edit?.revision_id ?? proposalId);
      closeEdit();
      return;
    }
    setError(null);
    if (action === "approve") {
      if (editOpen) return; // unsaved edit open — approval stays blocked
      const revisionId = item?.demo_edit?.revision_id ?? proposalId;
      const body = item?.customer_draft ?? "";
      onDemoVerdict?.(proposalId, "approved", simulateApproval(proposalId, revisionId), {
        revisionId,
        body,
      });
    } else {
      onDemoVerdict?.(proposalId, "denied", simulateDenial(proposalId));
    }
  }

  async function act(verdict: "approve" | "deny") {
    if (readOnly) {
      actDemo(verdict);
      return;
    }
    if (!proposalId || !canAct || busy) return;
    if (verdict === "approve" && editOpen) return; // unsaved redraft instruction open
    setBusy(true);
    setError(null);
    try {
      const result = await api.submitVerdict(proposalId, verdict, "ops-surface UI action");
      refreshLedger();
      onVerdict({ ...item!, proposal: { ...item!.proposal!, status: result.status as "approved" | "denied" } });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function loadReplacement(original: WorkItem, id: string) {
    try {
      const list = await api.proposals();
      onVerdict(original, replacementItem(original, id, list.proposals));
      setError(null);
    } catch {
      setError("The original draft is closed. Could not load a verified replacement; retry loading before approval.");
    }
  }

  async function actRedraft() {
    if (!proposalId || !item || !canEdit || busy || !editText.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.submitVerdict(proposalId, "revise", "ops-surface UI edit", editText.trim());
      closeEdit();
      refreshLedger();
      const original: WorkItem = {
        ...item,
        proposal: { ...item.proposal!, status: "denied" },
        replacement_proposal_id: result.superseding_proposal_id ?? undefined,
      };
      onVerdict(original);
      if (result.superseding_proposal_id) {
        await loadReplacement(original, result.superseding_proposal_id);
      } else {
        setError("The original draft is closed, but the server returned no replacement. Refresh to inspect its status.");
      }
    } catch {
      setError("Redraft request did not complete. Refresh to check the proposal status before retrying.");
    } finally {
      setBusy(false);
    }
  }

  useImperativeHandle(ref, () => ({
    approve: () => act("approve"),
    deny: () => act("deny"),
    edit: () => openEdit(),
  }));

  const saveDisabled = readOnly
    ? busy || !editText.trim() || editText.trim() === (item?.customer_draft ?? "").trim()
    : busy || !editText.trim();

  return (
    <div className="decision-controls" data-proposal-id={proposalId ?? undefined}>
      <div className="rail-top">
        <h2 className="t">Review draft</h2>
        <div className="gate">
          {item ? (
            proposalId ? (
              <span className="st">
                {readOnly && status === "approved"
                  ? "Approved (simulated)"
                  : label(PROPOSAL_STATUS_LABELS, status)}
              </span>
            ) : (
              "No gate-tracked proposal for this item"
            )
          ) : (
            "Select an item"
          )}
        </div>
        {error && (
          <div className="gate" role="alert" style={{ color: "var(--danger)" }}>
            {error}
          </div>
        )}
        {readOnly && (
          <div className="sim-note" role="note">
            Simulated — nothing is sent
          </div>
        )}
      </div>
      {!readOnly && item?.replacement_proposal_id && (
        <div className="sim-note">
          <p>A replacement draft is awaiting retrieval. The original cannot be approved.</p>
          <button className="btn" disabled={busy} onClick={async () => {
            setBusy(true);
            await loadReplacement(item, item.replacement_proposal_id!);
            setBusy(false);
          }}>Load replacement draft</button>
        </div>
      )}
      <div className="actions" aria-label="Proposal actions">
        <div className="cta-actions">
          <button
            type="button"
            className="btn approve"
            aria-keyshortcuts="A"
            disabled={!canAct || busy || editOpen}
            onClick={() => act("approve")}
          >
            Approve exact draft<span className="k">A</span>
          </button>
          <button
            type="button"
            className="btn edit"
            title={item?.redrafted_from ? "This proposal has already used its one redraft." : undefined}
            aria-keyshortcuts="E"
            disabled={!canEdit || busy}
            onClick={() => (editOpen ? closeEdit() : openEdit())}
          >
            {readOnly ? "Edit draft" : "Request redraft"}
            <span className="k">E</span>
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
        {packetCtas.length > 0 && (
          <details className="tech-details">
            <summary>Capability checks</summary>
            <div className="tech-details-body">
              <div className="cta-stack">
                {packetCtas.map((cta) => (
                  <div className={`cta-row${cta.enabled ? " on" : ""}`} key={cta.cta_id}>
                    <span>{cta.label}</span>
                    <span className="cta-state">
                      {cta.enabled ? "enabled" : "blocked"}
                    </span>
                  </div>
                ))}
                {proposalId && (
                  <div className="cta-row">
                    <span>Proposal id</span>
                    <span className="cta-state">{proposalId}</span>
                  </div>
                )}
              </div>
            </div>
          </details>
        )}
      </div>
      {editOpen && (
        <div className="edit-panel">
          <label className="edit-label" htmlFor="draft-edit-instruction">
            {readOnly ? "Draft text" : "Edit instruction"}
          </label>
          <textarea
            id="draft-edit-instruction"
            className="edit-input"
            value={editText}
            maxLength={readOnly ? undefined : 280}
            disabled={busy}
            onChange={(e) => setEditText(e.target.value)}
            placeholder={readOnly ? "Edit the draft text directly." : "Make the tone warmer."}
            aria-label={readOnly ? "Edit draft text" : "Edit instruction"}
            rows={readOnly ? 8 : 4}
          />
          <div className="edit-actions">
            {!readOnly && <span className="edit-count num">{editText.length}/280</span>}
            <button type="button" className="btn" disabled={busy} onClick={closeEdit}>
              Cancel
            </button>
            <button
              type="button"
              className="btn approve"
              disabled={saveDisabled}
              onClick={() => (readOnly ? actDemo("edit-save", editText) : actRedraft())}
            >
              {readOnly ? "Save edit" : "Send redraft request"}
            </button>
          </div>
        </div>
      )}
      <details className="ledger-disclosure" open={status === "approved" || status === "denied"}>
        <summary>
          Decision receipt
          {proposalId && (
            <span className="gap" title={ledgerGap.join(", ")}>
              {receiptEvents.length} events
              {ledgerGap.length > 0 ? ` · ${ledgerGap.length} source gaps` : ""}
            </span>
          )}
        </summary>
        {status === "approved" && (approvalSnapshot || !readOnly) && (
          <div className="approved-message" data-revision-id={approvalSnapshot?.revisionId ?? proposalId}>
            <h3>Approved message{readOnly ? " (simulated)" : ""}</h3>
            <div className="approved-draft-body">{approvalSnapshot?.body ?? item?.customer_draft}</div>
          </div>
        )}
        <div className="audit">
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
      </details>
    </div>
  );
});

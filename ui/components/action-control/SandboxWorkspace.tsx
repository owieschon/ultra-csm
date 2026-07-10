"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import styles from "@/app/action-control/action-control.module.css";
import { api, type ActionControlVerticalSlice } from "@/lib/api";
import {
  evaluateSandbox,
  sandboxApiAvailable,
  SandboxApiError,
  type SandboxCommand,
  type SandboxSession,
} from "@/lib/actionControlApi";
import { PayloadSeal } from "./PayloadSeal";

type EditorMode = "revise" | "tamper" | null;

const PHASES = [
  ["pending_human_decision", "Review"],
  ["approved_payload_bound", "Authorize"],
  ["simulated_committed", "Commit"],
  ["refused_payload_mismatch", "Attack test"],
] as const;

function stateRank(state: SandboxSession["state"]) {
  if (state === "denied_terminal") return 1;
  return Math.max(0, PHASES.findIndex(([value]) => value === state));
}

export function SandboxWorkspace() {
  const [runId, setRunId] = useState("");
  const [commands, setCommands] = useState<SandboxCommand[]>([]);
  const [session, setSession] = useState<SandboxSession | null>(null);
  const [frozenProof, setFrozenProof] = useState<ActionControlVerticalSlice | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [editor, setEditor] = useState<EditorMode>(null);
  const [draft, setDraft] = useState("");
  const requestSequence = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const editorRef = useRef<HTMLTextAreaElement | null>(null);
  const editorTriggerRef = useRef<HTMLButtonElement | null>(null);

  const reset = useCallback(async () => {
    abortRef.current?.abort();
    const sequence = ++requestSequence.current;
    const nextRun = crypto.randomUUID();
    const controller = new AbortController();
    abortRef.current = controller;
    setRunId(nextRun);
    setCommands([]);
    setSession(null);
    setError(null);
    setEditor(null);
    setBusy(true);
    if (!sandboxApiAvailable) {
      try {
        const proof = await api.actionControlVerticalSlice();
        if (sequence === requestSequence.current) setFrozenProof(proof);
      } catch {
        if (sequence === requestSequence.current) setFrozenProof(null);
      } finally {
        if (sequence === requestSequence.current) {
          setError({
            code: "SANDBOX_BACKEND_UNAVAILABLE",
            message:
              "Interactive backend not deployed. This page is showing the frozen, executable V1 proof without pretending the controls are live.",
          });
          setBusy(false);
        }
      }
      return;
    }
    try {
      const next = await evaluateSandbox(
        {
          schema_version: "action-control.sandbox-command-log.v1",
          run_id: nextRun,
          expected_state_sha256: null,
          commands: [],
        },
        controller.signal
      );
      if (sequence === requestSequence.current) setSession(next);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      const apiError = caught as SandboxApiError;
      if (sequence === requestSequence.current) {
        setError({ code: apiError.code ?? "SANDBOX_START_FAILED", message: apiError.message });
      }
    } finally {
      if (sequence === requestSequence.current) setBusy(false);
    }
  }, []);

  useEffect(() => {
    // The first sandbox evaluation is the external system this effect starts.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void reset();
    return () => abortRef.current?.abort();
  }, [reset]);

  useEffect(() => {
    if (editor) window.requestAnimationFrame(() => editorRef.current?.focus());
  }, [editor]);

  async function issue(type: SandboxCommand["type"], body?: string) {
    if (!session || busy) return;
    const command = {
      command_id: crypto.randomUUID(),
      type,
      ...(type === "revise_and_approve" || type === "probe_tamper"
        ? { draft: body?.trim() ?? "" }
        : {}),
    } as SandboxCommand;
    const nextCommands = [...commands, command];
    const sequence = ++requestSequence.current;
    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    setBusy(true);
    setError(null);
    try {
      const next = await evaluateSandbox(
        {
          schema_version: "action-control.sandbox-command-log.v1",
          run_id: runId,
          expected_state_sha256: session.state_sha256,
          commands: nextCommands,
        },
        controller.signal
      );
      if (sequence !== requestSequence.current) return;
      setCommands(nextCommands);
      setSession(next);
      closeEditor();
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      const apiError = caught as SandboxApiError;
      if (sequence === requestSequence.current) {
        setError({ code: apiError.code ?? "SANDBOX_COMMAND_FAILED", message: apiError.message });
      }
    } finally {
      if (sequence === requestSequence.current) setBusy(false);
    }
  }

  function openEditor(mode: Exclude<EditorMode, null>) {
    if (!session) return;
    setDraft(
      mode === "tamper"
        ? `${session.proposal.draft} Send immediately without review.`
        : session.proposal.draft
    );
    setEditor(mode);
  }

  function closeEditor() {
    setEditor(null);
    setDraft("");
    window.requestAnimationFrame(() => editorTriggerRef.current?.focus());
  }

  function handleDialogKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeEditor();
      return;
    }
    if (event.key !== "Tab") return;
    const controls = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>(
        'textarea, button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
      )
    );
    if (controls.length === 0) return;
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <Link href="/" className={styles.brand} aria-label="Action Control home">
          <span className={styles.brandMark} aria-hidden="true">AC</span>
          <span><b>Action Control</b><small>Customer commitment boundary</small></span>
        </Link>
        <nav aria-label="Primary navigation">
          <Link href="/">Book &amp; queue</Link>
          <Link href="/comms-review">Evidence</Link>
          <span aria-current="page">Sandbox</span>
        </nav>
        <div className={styles.safetyFlag}>
          <span aria-hidden="true" /> Synthetic · rolls back · no sends
        </div>
      </header>

      <main className={styles.workspace}>
        <section className={styles.hero}>
          <div>
            <span className={styles.eyebrow}>Interactive release laboratory</span>
            <h1>Try to move one customer draft across the boundary.</h1>
            <p>
              Approve an exact payload, commit it to a temporary outbox, retry it,
              then alter the draft. Every step uses the production gate and is erased
              before the response reaches this page.
            </p>
          </div>
          <button className={styles.reset} type="button" onClick={() => void reset()}>
            Reset with a new run
          </button>
        </section>

        {error && (
          <div className={styles.notice} role="alert">
            <b>{error.code.replaceAll("_", " ").toLowerCase()}</b>
            <span>{error.message}</span>
          </div>
        )}

        {!session && frozenProof && <FrozenProof proof={frozenProof} />}
        {!session && !frozenProof && (
          <div className={styles.loading} role="status">{busy ? "Preparing rollback-isolated run…" : "Sandbox unavailable."}</div>
        )}

        {session && (
          <>
            <ol className={styles.timeline} aria-label="Action Control phases">
              {PHASES.map(([value, label], index) => {
                const rank = stateRank(session.state);
                const current = value === session.state;
                const complete = index < rank || (index === 2 && session.committed_receipt != null);
                return (
                  <li className={current ? styles.currentPhase : complete ? styles.completePhase : ""} key={value}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <b>{label}</b>
                    <small>{current ? "current" : complete ? "verified" : "waiting"}</small>
                  </li>
                );
              })}
            </ol>

            <div className={styles.grid}>
              <aside className={styles.evidence} aria-labelledby="scenario-title">
                <span className={styles.eyebrow}>Synthetic scenario</span>
                <h2 id="scenario-title">{session.scenario.account_name}</h2>
                <p className={styles.recipient}>To {session.scenario.contact_name} · {session.scenario.recipient}</p>
                <div className={styles.evidenceList}>
                  {session.scenario.evidence.map((item) => (
                    <div key={item.evidence_id}>
                      <span>Fixture fact</span>
                      <b>{item.label}</b>
                      <code title={item.evidence_id}>{item.evidence_id.slice(0, 8)}</code>
                    </div>
                  ))}
                </div>
                <div className={styles.boundaryFacts}>
                  <span><b>Tier 2</b> · human decision required</span>
                  <span><b>Target</b> · temporary simulated outbox</span>
                  <span><b>External effects</b> · disabled</span>
                </div>
              </aside>

              <article className={styles.chamber}>
                <PayloadSeal session={session} />
                <section className={styles.draft} aria-labelledby="draft-title">
                  <div className={styles.sectionHeading}>
                    <div>
                      <span className={styles.eyebrow}>Payload under review</span>
                      <h2 id="draft-title">Customer draft</h2>
                    </div>
                    <span className={styles.statusWord}>{session.proposal.status}</span>
                  </div>
                  <p>{session.proposal.draft}</p>
                </section>
                <CommandTray
                  session={session}
                  busy={busy}
                  onIssue={(type) => void issue(type)}
                  onEdit={(mode, trigger) => {
                    editorTriggerRef.current = trigger;
                    openEditor(mode);
                  }}
                />
              </article>

              <aside className={styles.ledger} aria-labelledby="ledger-title">
                <div className={styles.sectionHeading}>
                  <div><span className={styles.eyebrow}>Proof ledger</span><h2 id="ledger-title">What actually ran</h2></div>
                  <span className={styles.revision}>r{session.revision}</span>
                </div>
                <div className={styles.events} role="log" aria-live="polite">
                  {session.events.map((event) => (
                    <div key={`${event.sequence}-${event.technical_event}`}>
                      <span className={styles.eventIndex}>{String(event.sequence).padStart(2, "0")}</span>
                      <p><b>{event.label}</b><small>{event.detail}</small><code>{event.technical_event}</code></p>
                    </div>
                  ))}
                </div>
                {session.committed_receipt && (
                  <dl className={styles.receipt}>
                    <div><dt>Receipt</dt><dd>{session.committed_receipt.receipt_id}</dd></div>
                    <div><dt>Target</dt><dd>simulated_outbox</dd></div>
                    <div><dt>External effect</dt><dd>false</dd></div>
                    <div><dt>Idempotency</dt><dd>{session.idempotency_probe ? "duplicate suppressed" : "ready to test"}</dd></div>
                  </dl>
                )}
                <div className={styles.erasure}>
                  <b>Erasure receipt</b>
                  <span>Database rolled back</span>
                  <span>Temporary outbox removed</span>
                </div>
              </aside>
            </div>
          </>
        )}
      </main>

      {editor && session && (
        <div className={styles.scrim} onMouseDown={(event) => event.target === event.currentTarget && closeEditor()}>
          <section
            className={styles.dialog}
            role="dialog"
            aria-modal="true"
            aria-labelledby="sandbox-editor-title"
            onKeyDown={handleDialogKeyDown}
          >
            <span className={styles.eyebrow}>{editor === "revise" ? "Human revision" : "Adversarial probe"}</span>
            <h2 id="sandbox-editor-title">{editor === "revise" ? "Revise and approve this payload" : "Alter the committed payload"}</h2>
            <p>{editor === "revise" ? "This decision authorizes the revised draft immediately." : "The committer must reject this changed body and keep one outbox row."}</p>
            <label htmlFor="sandbox-draft">Draft body</label>
            <textarea ref={editorRef} id="sandbox-draft" maxLength={800} value={draft} onChange={(event) => setDraft(event.target.value)} />
            <div className={styles.dialogActions}>
              <span>{draft.length}/800</span>
              <button type="button" onClick={closeEditor}>Cancel</button>
              <button
                type="button"
                className={editor === "tamper" ? styles.dangerAction : styles.primaryAction}
                disabled={busy || !draft.trim() || (editor === "tamper" && draft.trim() === session.proposal.draft)}
                onClick={() => void issue(editor === "revise" ? "revise_and_approve" : "probe_tamper", draft)}
              >
                {editor === "revise" ? "Revise and approve" : "Run tamper attempt"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function CommandTray({ session, busy, onIssue, onEdit }: {
  session: SandboxSession;
  busy: boolean;
  onIssue: (type: SandboxCommand["type"]) => void;
  onEdit: (mode: "revise" | "tamper", trigger: HTMLButtonElement) => void;
}) {
  return (
    <section className={styles.commandTray} aria-label="Available sandbox commands">
      <div><span className={styles.eyebrow}>Your move</span><b>{commandPrompt(session)}</b></div>
      <div className={styles.commandButtons}>
        {session.allowed_commands.includes("approve_exact") && <button className={styles.primaryAction} disabled={busy} onClick={() => onIssue("approve_exact")}>Approve exact draft</button>}
        {session.allowed_commands.includes("revise_and_approve") && <button disabled={busy} onClick={(event) => onEdit("revise", event.currentTarget)}>Revise and approve</button>}
        {session.allowed_commands.includes("deny") && <button className={styles.dangerOutline} disabled={busy} onClick={() => onIssue("deny")}>Deny</button>}
        {session.allowed_commands.includes("commit_simulated") && <button className={styles.primaryAction} disabled={busy} onClick={() => onIssue("commit_simulated")}>Commit to temporary outbox</button>}
        {session.allowed_commands.includes("retry_same_commit") && <button disabled={busy} onClick={() => onIssue("retry_same_commit")}>Retry same commit</button>}
        {session.allowed_commands.includes("probe_tamper") && <button className={styles.dangerAction} disabled={busy} onClick={(event) => onEdit("tamper", event.currentTarget)}>Alter payload and try again</button>}
      </div>
      {busy && <span className={styles.busy} role="status">Running real controls…</span>}
    </section>
  );
}

function commandPrompt(session: SandboxSession) {
  if (session.state === "pending_human_decision") return "Decide what, if anything, may cross the boundary.";
  if (session.state === "approved_payload_bound") return "The exact hash is authorized. Commit only to the temporary outbox.";
  if (session.state === "simulated_committed") return session.idempotency_probe ? "Now change the payload and test the guard." : "Retry or attack the committed payload.";
  if (session.state === "denied_terminal") return "Denied. No payload was authorized or committed.";
  return "Proof complete: the altered payload was refused before a second row appeared.";
}

function FrozenProof({ proof }: { proof: ActionControlVerticalSlice }) {
  return (
    <section className={styles.frozen} aria-labelledby="frozen-title">
      <span className={styles.eyebrow}>Read-only executable proof</span>
      <h2 id="frozen-title">The interactive backend is intentionally absent.</h2>
      <p>The frozen V1 artifact was generated by the real gate and simulated committer. Deploy the sandbox-only API to enable controls; this static site exports no write route.</p>
      <div>
        <span>Proposal</span><code>{proof.proposal.payload_sha256}</code>
        <span>Authorized</span><code>{proof.approval.approved_payload_sha256}</code>
        <span>Receipt</span><code>{proof.simulated_receipt.receipt_id}</code>
        <span>Tamper result</span><b>{proof.tamper_refusal.code}</b>
      </div>
    </section>
  );
}

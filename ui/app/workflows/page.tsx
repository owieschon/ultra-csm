"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  api,
  WorkflowAuthoringIssue,
  WorkflowAuthoringReadinessReport,
  WorkflowReadiness,
} from "@/lib/api";

const OBLIGATION_LABELS: Record<string, string> = {
  happy_path: "happy path",
  suppression_or_missing_data_path: "suppression",
  execution_envelope_invariants: "envelope",
  action_gate_path: "ActionGate",
  api_trigger_persistence_ledger: "API + ledger",
  ui_projection_contract: "UI contract",
};

export default function WorkflowReadinessPage() {
  const [report, setReport] = useState<WorkflowAuthoringReadinessReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .workflowAuthoringReadiness()
      .then((r) => setReport(r.report))
      .catch((e) => setError(e instanceof Error ? e.message : "failed to load"));
  }, []);

  const workflows = useMemo(
    () =>
      Object.values(report?.workflows ?? {}).sort((a, b) =>
        a.workflow_id.localeCompare(b.workflow_id)
      ),
    [report]
  );
  const readyCount = workflows.filter((workflow) => workflow.ready).length;
  const issueCount =
    workflows.reduce((sum, workflow) => sum + workflow.issues.length, 0) +
    (report?.registry_issues.length ?? 0);

  return (
    <div className="detail-scroll readiness-page">
      <div className="readiness-shell">
        <div className="readiness-top">
          <div>
            <div className="packet-kicker">Workflow authoring</div>
            <h1>Readiness console</h1>
          </div>
          <Link className="navlink" href="/">
            Back to workbench
          </Link>
        </div>

        {error && (
          <div className="launch-alert">
            <span>{error}</span>
          </div>
        )}

        {!error && report === null && (
          <div className="placeholder-view">Loading workflow readiness…</div>
        )}

        {report && (
          <>
            <div className={`readiness-summary ${report.ready ? "ready" : "blocked"}`}>
              <div>
                <span className={report.ready ? "readiness-dot ok" : "readiness-dot danger"} />
                <strong>{report.ready ? "All registered workflows are ready" : "Workflow readiness needs review"}</strong>
              </div>
              <em>
                {readyCount}/{workflows.length} workflows ready · {issueCount} issue{issueCount === 1 ? "" : "s"}
              </em>
            </div>

            {report.registry_issues.length > 0 && (
              <IssuePanel title="Registry issues" issues={report.registry_issues} />
            )}

            <div className="readiness-grid">
              {workflows.map((workflow) => (
                <WorkflowCard key={workflow.workflow_id} workflow={workflow} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function WorkflowCard({ workflow }: { workflow: WorkflowReadiness }) {
  const obligations = workflow.declared_test_obligations;
  return (
    <section className={`readiness-card ${workflow.ready ? "ready" : "blocked"}`}>
      <div className="readiness-card-head">
        <div>
          <span className="packet-kicker">{workflow.ready ? "ready" : "blocked"}</span>
          <h2>{workflow.workflow_id.replace(/_/g, " ")}</h2>
        </div>
        <span className={workflow.ready ? "chip-det launch-ok" : "chip-det launch-stop"}>
          {workflow.issues.length} issue{workflow.issues.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="readiness-obligations">
        {obligations.map((obligation) => (
          <span key={obligation}>
            {OBLIGATION_LABELS[obligation] ?? obligation.replace(/_/g, " ")}
          </span>
        ))}
      </div>

      {workflow.issues.length === 0 ? (
        <div className="readiness-empty">
          Trigger, evidence, ActionGate, audit, UI, and tests are declared.
        </div>
      ) : (
        <IssuePanel title="Issues" issues={workflow.issues} compact />
      )}
    </section>
  );
}

function IssuePanel({
  title,
  issues,
  compact = false,
}: {
  title: string;
  issues: WorkflowAuthoringIssue[];
  compact?: boolean;
}) {
  return (
    <div className={compact ? "readiness-issues compact" : "readiness-issues"}>
      <div className="packet-kicker">{title}</div>
      {issues.map((issue) => (
        <div className="readiness-issue" key={`${issue.workflow_id}:${issue.check_name}`}>
          <span className={issue.severity === "error" ? "danger" : "warn"}>
            {issue.severity}
          </span>
          <strong>{issue.check_name.replace(/_/g, " ")}</strong>
          <em>{issue.detail}</em>
        </div>
      ))}
    </div>
  );
}

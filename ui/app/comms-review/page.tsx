"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, isReadOnlyDemo, PendingMapping } from "@/lib/api";

// Minimal pending-mappings review surface (Owen's own scoping: no fancy
// UI needed). Lists what the two live-pull endpoints currently see and
// lets a CSM confirm a candidate -- the only write action this page
// offers. A live call on page load is deliberate here (see the API
// endpoints' own docstrings): this is a manual, occasional review
// action, not the high-frequency brief path every other connector in
// this app reads from a seeded store instead.
export default function CommsReviewPage() {
  const [slack, setSlack] = useState<PendingMapping[] | null>(null);
  const [notion, setNotion] = useState<PendingMapping[] | null>(null);
  const [slackError, setSlackError] = useState<string | null>(null);
  const [notionError, setNotionError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState<Set<string>>(new Set());

  useEffect(() => {
    api
      .pendingSlackMappings()
      .then((r) => setSlack(r.pending))
      .catch((e) => setSlackError(e instanceof Error ? e.message : "failed to load"));
    api
      .pendingNotionMappings()
      .then((r) => setNotion(r.pending))
      .catch((e) => setNotionError(e instanceof Error ? e.message : "failed to load"));
  }, []);

  async function confirm(
    sourceType: "notion_meeting" | "slack_channel",
    externalId: string,
    accountId: string
  ) {
    if (isReadOnlyDemo) return;
    const key = `${sourceType}:${externalId}`;
    setConfirming(key);
    try {
      await api.confirmCommsMapping(sourceType, externalId, accountId);
      setConfirmed((prev) => new Set(prev).add(key));
    } finally {
      setConfirming(null);
    }
  }

  function renderSection(
    title: string,
    sourceType: "notion_meeting" | "slack_channel",
    items: PendingMapping[] | null,
    error: string | null,
    emptyCopy: string
  ) {
    return (
      <section className="sec" aria-labelledby={`${sourceType}-heading`}>
        <div className="sec-h">
          <h2 className="t" id={`${sourceType}-heading`}>{title}</h2>
        </div>
        {error && (
          <div className="evid-row" role="alert">
            <span className="eval" style={{ color: "var(--danger)" }}>
              {error}
            </span>
          </div>
        )}
        {!error && items === null && (
          <div className="evid-row">
            <span className="eval" style={{ color: "var(--fg-3)" }}>
              loading…
            </span>
          </div>
        )}
        {items?.length === 0 && (
          <div className="evidence-empty">
            <div className="evidence-empty-title">✓ Nothing pending</div>
            <div className="evidence-empty-copy">{emptyCopy}</div>
          </div>
        )}
        {items?.map((item) => (
          <div className="drawer" key={item.external_id}>
            <div className="drawer-h">
              <span className="dn">{item.title}</span>
              <span className="ds">{item.candidates.length} candidate{item.candidates.length === 1 ? "" : "s"}</span>
            </div>
            <div className="drawer-b" style={{ maxHeight: "none" }}>
              {item.candidates.length === 0 && (
                <div className="evid-row">
                  <span className="eval" style={{ color: "var(--fg-3)" }}>
                    no automatic candidates -- confirm manually if you know the account
                  </span>
                </div>
              )}
              {item.candidates.map((c) => {
                const key = `${sourceType}:${item.external_id}`;
                const isConfirmed = confirmed.has(key);
                return (
                  <div className="evid-row" key={c.account_id}>
                    <span className="esys">{c.signal}</span>
                    <span className="eval">
                      {c.reason} (confidence {c.confidence.toFixed(2)})
                    </span>
                    <button
                      type="button"
                      className="btn approve"
                      style={{ padding: "4px 10px", fontSize: 12 }}
                      disabled={isReadOnlyDemo || isConfirmed || confirming === key}
                      onClick={() => confirm(sourceType, item.external_id, c.account_id)}
                    >
                      {isReadOnlyDemo ? "read-only" : isConfirmed ? "confirmed" : confirming === key ? "confirming…" : "confirm"}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </section>
    );
  }

  return (
    <main className="detail-scroll evidence-review">
      <Link className="navlink evidence-back" href="/">
        ← Back to the book
      </Link>
      <header className="identity evidence-heading">
        <div>
          <h1 className="id-name">Evidence mapping</h1>
          <p className="evidence-intro">
            Resolve ambiguous communication sources before they can influence an account decision.
            When the agent pulls a Slack channel or a call transcript it can&apos;t
            match to exactly one account, it stops and queues the mapping here —
            unmapped evidence never reaches a score or a draft.
          </p>
        </div>
      </header>
      {renderSection(
        "Slack channels",
        "slack_channel",
        slack,
        slackError,
        "Every connected Slack channel is mapped to an account. A channel the agent can't place would appear here with its candidate accounts and a confidence score."
      )}
      {renderSection(
        "Notion call transcripts",
        "notion_meeting",
        notion,
        notionError,
        "Every pulled call transcript is mapped. A transcript mentioning several accounts would stop here for you to confirm which one it belongs to."
      )}
    </main>
  );
}

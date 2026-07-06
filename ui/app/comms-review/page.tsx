"use client";

import { useEffect, useState } from "react";
import { api, PendingMapping } from "@/lib/api";

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
    error: string | null
  ) {
    return (
      <div className="sec">
        <div className="sec-h">
          <span className="t">{title}</span>
        </div>
        {error && (
          <div className="evid-row">
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
          <div className="evid-row">
            <span className="eval" style={{ color: "var(--fg-3)" }}>
              nothing pending
            </span>
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
                      className="btn approve"
                      style={{ padding: "4px 10px", fontSize: 12 }}
                      disabled={isConfirmed || confirming === key}
                      onClick={() => confirm(sourceType, item.external_id, c.account_id)}
                    >
                      {isConfirmed ? "confirmed" : confirming === key ? "confirming…" : "confirm"}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="detail-scroll" style={{ padding: "22px 28px 48px", maxWidth: 900 }}>
      <div className="identity" style={{ borderBottom: "none" }}>
        <div className="id-name">Comms mapping review</div>
      </div>
      {renderSection("Slack channels", "slack_channel", slack, slackError)}
      {renderSection("Notion call transcripts", "notion_meeting", notion, notionError)}
    </div>
  );
}

import styles from "@/app/action-control/action-control.module.css";
import type { SandboxSession } from "@/lib/actionControlApi";

function shortHash(hash: string | null | undefined) {
  return hash ? `${hash.slice(0, 10)}…${hash.slice(-8)}` : "waiting";
}

export function PayloadSeal({ session }: { session: SandboxSession }) {
  const proposed = session.proposal.payload_sha256;
  const approved = session.decision?.approved_payload_sha256;
  const committed = session.committed_receipt?.payload_sha256;
  const attempted = session.tamper_refusal?.attempted_payload_sha256;
  const segments = [
    { label: "Proposed", hash: proposed, state: "base" },
    { label: "Authorized", hash: approved, state: approved ? "locked" : "waiting" },
    { label: "Committed", hash: committed, state: committed ? "locked" : "waiting" },
    ...(attempted ? [{ label: "Altered attempt", hash: attempted, state: "broken" }] : []),
  ];

  return (
    <section className={styles.seal} aria-labelledby="payload-seal-title">
      <div className={styles.sectionHeading}>
        <div>
          <span className={styles.eyebrow}>Payload custody</span>
          <h2 id="payload-seal-title">One draft. One authorized hash.</h2>
        </div>
        <span className={styles.sealState}>
          {session.tamper_refusal
            ? "altered attempt refused"
            : session.committed_receipt
              ? "simulated receipt verified"
              : session.decision?.approved_payload_sha256
                ? "authorization sealed"
                : "awaiting human decision"}
        </span>
      </div>
      <div className={styles.sealTrack}>
        {segments.map((segment) => (
          <div
            className={`${styles.sealSegment} ${styles[segment.state]}`}
            key={segment.label}
          >
            <span>{segment.label}</span>
            <code title={segment.hash ?? undefined} aria-label={`${segment.label} hash ${segment.hash ?? "waiting"}`}>
              {shortHash(segment.hash)}
            </code>
          </div>
        ))}
      </div>
      <p className={styles.sealNote}>
        The proposed, authorized, and committed segments lock only when their exact
        SHA-256 values match. An altered draft breaks the chain before the outbox.
      </p>
    </section>
  );
}

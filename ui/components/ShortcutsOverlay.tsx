"use client";

import { useEffect, useRef } from "react";

const ROWS: [string, string[]][] = [
  ["Book ⇄ Queue", ["v"]],
  ["Command palette", ["⌘", "K"]],
  ["Move through queue", ["j", "k"]],
  ["Approve exact draft", ["a"]],
  ["Edit draft", ["e"]],
  ["Deny", ["d"]],
  ["Toggle theme", ["t"]],
  ["This panel", ["?"]],
];

export function ShortcutsOverlay({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    return () => previousFocusRef.current?.focus();
  }, [open]);

  if (!open) return null;
  return (
    <div className="scrim open" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div
        className="help-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
        onKeyDown={(e) => {
          if (e.key === "Escape") onClose();
          if (e.key === "Tab") {
            e.preventDefault();
            closeRef.current?.focus();
          }
        }}
      >
        <div className="help-heading">
          <h3 id="shortcuts-title">Keyboard</h3>
          <button ref={closeRef} type="button" className="palette-close" onClick={onClose} aria-label="Close shortcuts">
            ×
          </button>
        </div>
        <div className="help-grid">
          {ROWS.map(([label, keys]) => (
            <div className="help-row" key={label}>
              <span>{label}</span>
              <span style={{ display: "flex", gap: 5 }}>
                {keys.map((k) => (
                  <kbd key={k}>{k}</kbd>
                ))}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

"use client";

const ROWS: [string, string[]][] = [
  ["Book ⇄ Queue", ["v"]],
  ["Command palette", ["⌘", "K"]],
  ["Move through queue", ["j", "k"]],
  ["Approve & send", ["a"]],
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
  if (!open) return null;
  return (
    <div className="scrim open" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="help-card">
        <h3>Keyboard</h3>
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

"use client";

import { useEffect, useRef, useState } from "react";
import { AccountSummary } from "@/lib/api";
import { label, TIER_LABELS } from "@/lib/labels";

interface Command {
  label: string;
  action: () => void;
}

export function CommandPalette({
  open,
  onClose,
  accounts,
  pendingAccountIds,
  onJumpToAccount,
  commands,
}: {
  open: boolean;
  onClose: () => void;
  accounts: AccountSummary[] | null;
  pendingAccountIds?: Set<string>;
  onJumpToAccount: (accountId: string) => void;
  commands: Command[];
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    const timer = window.setTimeout(() => {
      setQuery("");
      setActive(0);
      inputRef.current?.focus();
    }, 0);
    return () => {
      window.clearTimeout(timer);
      previousFocusRef.current?.focus();
    };
  }, [open]);

  if (!open) return null;

  const q = query.toLowerCase();
  const matchedAccounts = (accounts ?? []).filter((a) =>
    a.account_name.toLowerCase().includes(q)
  );
  const matchedCommands = commands.filter((c) =>
    c.label.toLowerCase().includes(q)
  );

  const accountMeta = (a: AccountSummary) => (
    <span className="meta" title={a.tier ?? undefined}>
      {pendingAccountIds?.has(a.account_id) && (
        <span className="meta-needs">needs you · </span>
      )}
      {label(TIER_LABELS, a.tier)}
    </span>
  );

  const items: { render: React.ReactNode; act: () => void }[] = [
    ...matchedAccounts.map((a) => ({
      render: (
        <>
          <b>{a.account_name}</b>
          {accountMeta(a)}
        </>
      ),
      act: () => onJumpToAccount(a.account_id),
    })),
    ...matchedCommands.map((c) => ({
      render: <b>{c.label}</b>,
      act: c.action,
    })),
  ];

  function runActive() {
    const item = items[active];
    if (item) {
      item.act();
      onClose();
    }
  }

  function handleDialogKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }
    if (e.key !== "Tab") return;
    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (!focusable?.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  return (
    <div className="scrim open" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={dialogRef}
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-labelledby="command-palette-title"
        onKeyDown={handleDialogKeyDown}
      >
        <h2 id="command-palette-title" className="sr-only">Search accounts and commands</h2>
        <div className="pal-in">
          <input
            ref={inputRef}
            role="combobox"
            aria-label="Search accounts and commands"
            aria-expanded="true"
            aria-autocomplete="list"
            aria-controls="command-palette-results"
            aria-activedescendant={items[active] ? `command-palette-option-${active}` : undefined}
            placeholder="Jump to an account, or run a command…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose();
              else if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((i) => Math.min(i + 1, items.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((i) => Math.max(i - 1, 0));
              } else if (e.key === "Enter") runActive();
            }}
          />
          <span className="esc">esc</span>
          <button type="button" className="palette-close" onClick={onClose} aria-label="Close command palette">
            ×
          </button>
        </div>
        <div className="pal-list" id="command-palette-results" role="listbox">
          {matchedAccounts.length > 0 && <div className="pal-grp">Accounts</div>}
          {matchedAccounts.map((a, i) => (
            <button
              type="button"
              role="option"
              aria-selected={active === i}
              id={`command-palette-option-${i}`}
              key={a.account_id}
              className={`pal-item${active === i ? " active" : ""}`}
              onClick={() => {
                onJumpToAccount(a.account_id);
                onClose();
              }}
            >
              <b>{a.account_name}</b>
              {accountMeta(a)}
            </button>
          ))}
          {matchedCommands.length > 0 && <div className="pal-grp">Commands</div>}
          {matchedCommands.map((c, i) => (
            <button
              type="button"
              role="option"
              aria-selected={active === matchedAccounts.length + i}
              id={`command-palette-option-${matchedAccounts.length + i}`}
              key={c.label}
              className={`pal-item${active === matchedAccounts.length + i ? " active" : ""}`}
              onClick={() => {
                c.action();
                onClose();
              }}
            >
              <b>{c.label}</b>
            </button>
          ))}
          {items.length === 0 && <div className="pal-empty">No matches</div>}
        </div>
      </div>
    </div>
  );
}

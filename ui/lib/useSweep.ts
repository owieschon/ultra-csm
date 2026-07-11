"use client";

import { useEffect, useState } from "react";
import { api, WorkItem } from "@/lib/api";

export interface SweepData {
  work_items: WorkItem[];
  escalations: Record<string, unknown>[];
  swept_accounts: string[];
}

// A sweep (POST /sweep) creates real ActionGate proposals as a side effect —
// calling it once per view (Book AND Queue) would double-propose the same
// triggers. Lifted here so page.tsx fetches once per (day, refreshToken) and
// both views share the result.
export function useSweep(
  day: number | undefined,
  refreshToken: number,
  enabled = true
) {
  const [sweep, setSweep] = useState<SweepData | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!enabled) return;
    api
      .sweep(day)
      .then((r) => {
        setSweep({
          work_items: r.work_items,
          escalations: r.escalations,
          swept_accounts: r.swept_accounts,
        });
        setError(null);
      })
      .catch((e) => setError(e));
  }, [day, refreshToken, enabled]);

  return { sweep, error };
}

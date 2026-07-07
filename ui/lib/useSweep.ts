"use client";

import { useEffect, useState } from "react";
import { api, CSMWorkPacket, WorkItem } from "@/lib/api";

export interface SweepData {
  work_items: WorkItem[];
  escalations: Record<string, unknown>[];
  swept_accounts: string[];
  coverage_packets: CSMWorkPacket[];
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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    setError(null);
    api
      .sweep(day)
      .then((r) =>
        setSweep({
          work_items: r.work_items,
          escalations: r.escalations,
          swept_accounts: r.swept_accounts,
          coverage_packets: r.coverage_packets,
        })
      )
      .catch((e) => setError(String(e)));
  }, [day, refreshToken, enabled]);

  return { sweep, error };
}

"""Reap orphaned ephemeral-Postgres datadirs under `build/tmp/` before `make clean`.

A directory is only reaped when it matches the `pgdata.*` naming pattern
AND its recorded postmaster PID is not a live process -- see
`ultra_csm.platform.reap_stale_clusters` for the full detection contract.
A live cluster (in active use by a concurrent run) is never touched.
"""

from __future__ import annotations

from ultra_csm.platform import reap_stale_clusters


def main() -> int:
    reaped = reap_stale_clusters()
    if not reaped:
        print("reaper: no stale ephemeral-Postgres clusters found")
        return 0
    print(f"reaper: reaped {len(reaped)} stale cluster(s):")
    for cluster in reaped:
        pid_note = f"postmaster pid {cluster.postmaster_pid}" if cluster.postmaster_pid else "no postmaster.pid"
        print(f"  - {cluster.datadir} ({pid_note})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

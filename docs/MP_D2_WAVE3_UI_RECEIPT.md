# MP-D2 Wave 3 UI Receipt

## Scope

Wave 3 makes the existing operator workbench consume `CSMWorkPacket`.

Added:

- TypeScript packet contract in `ui/lib/api.ts`
- QueueDetail "Decision packet" section:
  - primary next step
  - honest diagnostic hypothesis label and confidence
  - job/lane/cadence/actor
  - governance boundary
  - bucket trace
  - provenance-tiered evidence chain
  - artifact validation status
- ActionRail backend CTA rendering:
  - CTAs come from `work_packet.allowed_ctas`
  - approval action is additionally guarded by the backend
    `request_gate_approval` CTA
- QueueLanes packet hints:
  - account name from packet when present
  - lane chip from packet
- Loopback CORS expansion for stacked local worktree verification:
  `localhost`/`127.0.0.1` ports `3000`-`3002`
- Responsive workbench rule at phone width:
  - hides the rail
  - preserves queue/detail access
  - removes horizontal overflow in the packet view

## Visual QA

Local branch servers:

- API: `ULTRA_CSM_DEMO_NOAUTH=1 PYTHONPATH=src:. python3 -m uvicorn ultra_csm.api:app --host 127.0.0.1 --port 8001`
- UI: `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8001 npx next dev --hostname 127.0.0.1 --port 3002`

Desktop Playwright/Chrome smoke:

- loaded `/ui/`
- opened Queue
- selected first item
- verified packet renders in QueueDetail and CTAs render in ActionRail

Mobile-width smoke at `430x900`:

- packet renders
- horizontal overflow: `false`

## Gates

- `make PYTHON=python3 ui-check`
  - `npm ci`
  - `npm run lint`: 0 errors, existing hook warnings only
  - `npm run build`: Next build passed
- `python3 -m pytest tests/test_ui_contract.py tests/test_work_packets.py tests/test_work_packet_eval.py -q`
  -> `20 passed`
- `python3 -m ruff check src eval tests scripts`
  -> `All checks passed!`

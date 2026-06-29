# Ultra CSM Observability

Status: active observability landing page.

Observability is a port around the proof, not an authority path. Offline evals
remain deterministic and credential-free.

The kept package exposes:

- `NoOpTracer` and `NoOpMeter` for the scored default path.
- `RecordingTracer` and `RecordingMeter` for deterministic tests and fake-client
  Slot B verification.
- Span/meter protocols that live adapters can implement later without changing
  Agent 1 logic.

Agent 1 uses observability around Slot B live calls only when a caller injects
recording or live implementations. The deterministic scorecard does not depend on
wall-clock timing, network exporters, or credentials.

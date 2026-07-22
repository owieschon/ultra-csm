# Connector discovery and mapping

Use this page to verify connector request shapes, exercise simulated onboarding, and
freeze a reviewed source mapping without mistaking dry-run output for live proof.

## Check request shapes without network calls

```sh
ULTRA_CSM_ROCKETLANE_API_KEY=dummy \
  PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli connectors smoke \
  rocketlane_onboarding --dry-run
```

```sh
ULTRA_CSM_ATTIO_ACCESS_TOKEN=dummy \
  PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli connectors explore \
  attio_crm --dry-run
```

These commands validate configured request shapes only. They do not prove that
credentials work, that a tenant exposes the expected fields, or that records map
correctly.

## Exercise simulated onboarding

```sh
make attio-simulated-onboarding-csm
make gainsight-simulated-onboarding-csm
make product-telemetry-simulated-onboarding-csm
make salesforce-simulated-onboarding-csm
```

Each target writes an artifact under `eval/` from fixture data. Unknown fields remain
unknown: tenant-specific Gainsight scorecard and adoption fields require tenant metadata,
and telemetry values require a sample payload rather than attribute introspection alone.

## Confirm a mapping

Schema exploration proposes a mapping. Standard fields may map deterministically;
ambiguous custom fields and value-direction fields require an explicit confirmation.

```sh
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli connectors confirm \
  proposal.json confirmations.json --output config/source-map.json
```

Verify the fail-closed loader and command path with:

```sh
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_connector_explorer.py -q
```

Use real credentials only for a tenant you control, omit `--dry-run`, and treat the
result as that tenant's readiness receipt. The repository's simulated artifacts are not
live-tenant proof.

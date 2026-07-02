# Quickstart

Start from a fresh clone of this repository, then run the local fixture/sim path from
the repo root. No live tenant credentials are required for this path.

## Set Up

```sh
make setup
```

## Run The Offline Demo Gates

```sh
make demo
```

This runs the deterministic CSM scorecard and offline regression. It proves fixture/sim
behavior only.

## Inspect The Synthetic Book

```sh
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli demo-book --json
```

```sh
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli demo-sweep --day 60 --deep --json
```

## Exercise Connector Readiness Without Network Calls

```sh
ULTRA_CSM_ROCKETLANE_API_KEY=dummy \
  PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli connectors smoke rocketlane_onboarding --dry-run
```

```sh
ULTRA_CSM_ATTIO_ACCESS_TOKEN=dummy \
  PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli connectors explore attio_crm --dry-run
```

Dry-run connector commands verify configured request shapes only. Replace the dummy env
vars with real connector credentials and omit `--dry-run` when you are ready to test your
own tenant; the repository does not claim live-tenant proof.

## Render Current Status

```sh
PYTHONPATH=src:. .venv/bin/python scripts/render_status.py
```

`STATUS.md` is generated from local artifacts. If it reports a missing readiness artifact,
that means no live source-readiness run has been captured in this checkout.

## Source Mapping Confirmation

Schema exploration already produces a mapping proposal. Deterministic standard fields map
automatically; ambiguous custom fields and value-direction fields must be confirmed before
they can become frozen runtime config. Confirmed mappings are frozen with:

```sh
PYTHONPATH=src:. .venv/bin/python -m ultra_csm.cli connectors confirm \
  proposal.json confirmations.json --output config/source-map.json
```

The fail-closed loader and command path are covered by:

```sh
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_connector_explorer.py -q
```

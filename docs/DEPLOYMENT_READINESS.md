# Deployment Readiness

<!-- sourcebound:purpose -->
Auto-rendered by `make deployment-readiness` (`scripts/render_deployment_readiness.py`) from committed battery/week-1/perturbation/drift artifacts. Never hand-edited -- every cell below cites the artifact it was read from.
<!-- sourcebound:end purpose -->

## The claim

> "Agents are tested from cold start across four distributionally distinct tenants and their perturbation families, over books spanning enterprise-touch to self-serve scale, with measured onboarding cost, scripted-feedback persistence, adversarial-content safety with cross-account canaries, tier-appropriate action economics, and drift resilience -- with zero ad-hoc per-tenant rules in code."

## Tenant coverage

| Tenant | Account count | Vendor stack |
| --- | --- | --- |
| fleetops | 180 (7 high / 28 mid / 145 tech-touch of which 110 are pure tail) | Salesforce-shaped CRM + Rocketlane + Gmail/GCal + Gainsight-ish CS platform |
| fieldstone | 12 (2 high / 4 mid / 6 tech-touch) | HubSpot-shaped CRM (associations), no CS platform |
| crateworks | 10 (1 high / 3 mid / 6 tech-touch) | flat CSV/homegrown CRM, no CS platform, no PSA |
| loopway | 400 (4 high / 20 mid / 376 tech-touch) | Attio-shaped CRM + Intercom-ish chat, no CS platform |

## Battery results

| Tenant | Battery | Cases | hard_ok | Evidence |
| --- | --- | --- | --- | --- |
| fleetops | narrative | 8 | true | `eval/narrative_battery.json` |
| fleetops | content | 5 | true | `eval/content_battery.json` |
| fleetops | canary | 6 | true | `eval/canary_battery.json` |
| fleetops | quantity | 3 | true | `eval/quantity_battery.json` |
| fleetops | transcript | 4 | true | `eval/transcript_battery.json` |
| fleetops | tier-policy | 4 | true | `eval/tier_policy_battery.json` |
| fieldstone | fieldstone | 6 | true | `eval/fieldstone_battery.json` |
| crateworks | crateworks | 6 | true | `eval/crateworks_battery.json` |
| loopway | loopway | 9 | true | `eval/loopway_battery.json` |
| all | perturbation | 6 | true | `eval/perturbation_battery.json` |
| fleetops | drift | 5 | true | `eval/drift_battery.json` |

## Onboarding cost (cold-start, across four vendor dialects)

| Tenant | Vendor shape | Questions asked | week-1 `ok` | Evidence |
| --- | --- | --- | --- | --- |
| fleetops | Salesforce-shaped | 5 | true | `eval/week1_report_fleetops.json` |
| fieldstone | HubSpot-shaped | 3 | true | `eval/week1_report_fieldstone.json` |
| crateworks | flat CSV / homegrown | 6 | true | `eval/week1_report_crateworks.json` |
| loopway | Attio-shaped | 4 | true | `eval/week1_report_loopway.json` |

Onboarding question count is a function of schema-shape diversity, not account count or vendor identity -- confirmed across all four dialects above (fleetops 180 accounts / fieldstone 12 / crateworks 10 / loopway 400, no monotonic relationship between account count and question count).

## Perturbation resilience

| Cell | ok | Evidence |
| --- | --- | --- |
| latency-uniform-no-new-flags | true | `eval/perturbation_battery.json` |
| latency-recent-window-flags-real-stretch | true | `eval/perturbation_battery.json` |
| volume-down-degrades-honestly | true | `eval/perturbation_battery.json` |
| hygiene-drop-no-crash | true | `eval/perturbation_battery.json` |
| schema-rename-asks-or-refuses | true | `eval/perturbation_battery.json` |
| arr-shift-moves-tier-and-forbidden-motions | true | `eval/perturbation_battery.json` |

## Drift resilience

| Check | ok | Evidence |
| --- | --- | --- |
| schema-field-rename-before-at-after | true | `eval/drift_battery.json` |
| junk-contacts-present-after-day150 | true | `eval/drift_battery.json` |
| width-signals-unaffected-by-junk-import | true | `eval/drift_battery.json` |
| narrative-battery-still-green-post-drift | true | `eval/drift_battery.json` |
| content-invariance-isolation | true | `eval/drift_battery.json` |

## Zero ad-hoc per-tenant rules

Every tenant's tier-appropriate action economics (motion → CSM action type, tier-forbidden-motions) resolves through the SAME `eval/tier_policy_battery.py` resolver and the SAME `knowledge/tenants/<slug>/playbooks.json` schema Foundations defined in Wave 0 -- no tenant has a bespoke, hard-coded action-selection code path. Evidence: `eval/tier_policy_battery.json` (fleetops), each tenant's own battery re-uses the identical `ultra_csm.value_model.resolve_tenant_tier` + `ultra_csm.knowledge.load_playbooks` pair.

## Summary

- All tenant + cross-cutting batteries `hard_ok`: **true**
- All four tenants' week-1 protocol `ok`: **true**

# MP-B Handoff Spike Spec

## Substrate

- Tenant: `fleetops_handoff`, reusing FleetOps synthetic-book account slugs and existing CRM case fixtures.
- Account source: `src/ultra_csm/data_plane/synthetic_book.py`.
- Case source: `src/ultra_csm/data_plane/data_simulator.py` via `src/ultra_csm/data_plane/narrative_shared.py`.
- Case id convention: `det_id("case", account_id, f"deep-d{open_day}-{topic}")`.
- Schema source: `eval/gold/expected_actions_schema.md`.

## Part A: Blind Account States

1. `B0-01` — `pinehill-transport`, checkpoint day 20. One open high-priority CRM case: "Integration with legacy dispatch system failing"; status `Escalated`; opened day 0. No second same-topic case has opened yet.

2. `B0-02` — `pinehill-transport`, checkpoint day 50. Two high-priority legacy-dispatch integration CRM cases are present: the day-0 case is resolved after a long resolution window, and the day-30 timeout case is still `Escalated`.

3. `B0-03` — `pinehill-transport`, checkpoint day 90. Three legacy-dispatch integration CRM cases are present: day 0 connection failure, day 30 timeout errors, and day 80 event-loss/dropped-dispatch-events case; the day-80 case remains active.

4. `B0-04` — `trailhead-logistics`, checkpoint day 60. One low-priority CRM case is present: "Feature request: custom compliance report template"; it has resolved.

5. `B0-05` — `trailhead-logistics`, checkpoint day 130. Two low-priority CRM cases are present: "Feature request: custom compliance report template" and "Request for API webhook for new asset alerts"; the second case remains active.

6. `B0-06` — `trailhead-logistics`, checkpoint day 180. The same two low-priority feature-request CRM cases are present, and both have resolved.

7. `B0-07` — `ironridge-fleet`, checkpoint day 42. One high-priority CRM case is present: "Integration webhook returning 500 errors intermittently"; it resolved in two days. The bible frames this account as a red herring with flat-normal surrounding signals.

8. `B0-08` — `cedar-valley`, checkpoint day 18. One low-priority CRM case is present: "Requesting updated MSA redline for renewal paperwork"; it is still in progress. The bible frames this as renewal paperwork friction.

9. `B0-09` — `cypress-field`, checkpoint day 6. One high-priority CRM case is present: "Repeated GPS accuracy issues in rural areas"; it is still in progress.

10. `B0-10` — `cypress-field`, checkpoint day 15. Four active CRM cases are present: three GPS-accuracy cases across day 0, day 7, and day 14, plus one day-7 API-timeout case.

11. `B0-11` — `harborview-fleet`, checkpoint day 20. Two high-priority ERP integration CRM cases are present: "Integration with new ERP system not working as expected" and "ERP sync dropping line items intermittently"; both remain active.

12. `B0-12` — `hawkstone-industries`, checkpoint day 210. Three active CRM cases opened on day 205 after a platform update: two reporting/dashboard discrepancy cases and one compliance-report export failure.

13. `B0-13` — `mesa-industrial`, checkpoint day 160. One low-priority CRM case is present: "Quarterly compliance report format change request"; it remains active.

14. `B0-14` — `bison-transport`, checkpoint day 60. One medium-priority CRM case is present: "Route optimization suggesting inefficient paths"; it remains active.

15. `B0-15` — `stonebridge-fleet`, checkpoint day 70. One medium-priority CRM case is present: "Fleet dashboard not showing real-time positions"; it remains active.

16. `B0-16` — `cascade-field`, checkpoint day 45. One low-priority CRM case is present: "How to set up maintenance alert thresholds"; it resolved in five days.

17. `B0-17` — `sagebrush-transport`, checkpoint day 30. Two high-priority CRM cases are present: "Frustrated with slow reporting performance" and "Dashboard load times unacceptable"; the first is escalated and the second remains in progress.

18. `B0-18` — `clearwater-field-ops`, checkpoint day 10. One low-priority CRM case is present: "Question about mobile app setup for technicians"; it resolved in eight days.

## Part B: Proposed Oracle Rows

Owner blind labels were received in `/Users/owieschon/.codex/attachments/08763bba-6157-44ea-9608-aee2c80ad13c/pasted-text.txt`.

| Review id | Account | Day | Mode | Required signal | Motion in | Target in | Evidence must include | Forbidden motions | Abstain correct |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| B0-01 | `pinehill-transport` | 20 | `gap` | `active_technical_failure` | `escalation` | `engineering` | `7b7fe426-01f6-529e-a65b-3240e6ddc058` | `content_route` | `false` |
| B0-02 | `pinehill-transport` | 50 | `gap` | `recurring_technical_case_pattern` | `escalation` | `engineering` | `7b7fe426-01f6-529e-a65b-3240e6ddc058`, `90c96b52-a603-51b0-aa5a-024f9d5d90fc` | `content_route` | `false` |
| B0-03 | `pinehill-transport` | 90 | `gap` | `recurring_technical_case_pattern` | `escalation` | `engineering` | `7b7fe426-01f6-529e-a65b-3240e6ddc058`, `90c96b52-a603-51b0-aa5a-024f9d5d90fc`, `43a814d9-314b-522a-bda5-4ccfe507d55c` | `content_route` | `false` |
| B0-04 | `trailhead-logistics` | 60 | `gap` | `feature_request_cluster` | `content_route` | `product` | `6ee1311a-6031-57ad-a6b4-a5ae8ed32418` | `escalation` | `false` |
| B0-05 | `trailhead-logistics` | 130 | `gap` | `feature_request_cluster` | `content_route` | `product` | `6ee1311a-6031-57ad-a6b4-a5ae8ed32418`, `badfdd75-9630-5572-9bfe-953363e95fd9` | `escalation` | `false` |
| B0-06 | `trailhead-logistics` | 180 | `gap` | `feature_request_cluster` | `content_route` | `product` | `6ee1311a-6031-57ad-a6b4-a5ae8ed32418`, `badfdd75-9630-5572-9bfe-953363e95fd9` | `escalation` | `false` |
| B0-07 | `ironridge-fleet` | 42 | `none` | `null` | empty | empty | empty | `escalation`, `content_route` | `true` |
| B0-08 | `cedar-valley` | 18 | `none` | `null` | empty | empty | empty | `escalation`, `content_route` | `true` |
| B0-09 | `cypress-field` | 6 | `gap` | `single_contestable_accuracy_case` | `escalation`, `content_route` | `engineering`, `product` | `d066c552-18b5-5457-8426-654cf525d314` | empty | `false` |
| B0-10 | `cypress-field` | 15 | `gap` | `recurring_technical_case_pattern` | `escalation` | `engineering` | `d066c552-18b5-5457-8426-654cf525d314`, `b4946066-537d-52f8-b223-22d4c5874de7`, `7f490468-511b-5747-961c-ee4795297d2e` | `content_route` | `false` |
| B0-11 | `harborview-fleet` | 20 | `gap` | `recurring_technical_case_pattern` | `escalation` | `engineering` | `582bfa06-a2b5-508d-81e2-270faa09248f`, `3a369f50-cbad-5668-9d66-e1e04eac0c80` | `content_route` | `false` |
| B0-12 | `hawkstone-industries` | 210 | `gap` | `recurring_technical_case_pattern` | `escalation` | `engineering` | `a3f4e940-d444-510d-9ec1-cdcb8bdfb778`, `031b3a70-6d52-5693-81d7-f8dbc6bd5fcb` | `content_route` | `false` |
| B0-13 | `mesa-industrial` | 160 | `gap` | `single_product_capability_request` | `content_route` | `product` | `93e389f0-edb1-5adf-99dc-337a00e202be` | `escalation` | `false` |
| B0-14 | `bison-transport` | 60 | `gap` | `single_contestable_quality_case` | `escalation`, `content_route` | `engineering`, `product` | `41fdb309-e0e5-5081-868a-b54fabf760ae` | empty | `false` |
| B0-15 | `stonebridge-fleet` | 70 | `gap` | `active_realtime_position_defect` | `escalation` | `engineering` | `afe231fa-83a5-538d-a616-9532e5c533e4` | `content_route` | `false` |
| B0-16 | `cascade-field` | 45 | `none` | `null` | empty | empty | empty | `escalation`, `content_route` | `true` |
| B0-17 | `sagebrush-transport` | 30 | `gap` | `recurring_technical_case_pattern` | `escalation` | `engineering` | `4343309d-2b19-5293-933f-6ec6648b4957`, `4d41a9c8-639e-5757-b215-6210dbf9834a` | `content_route` | `false` |
| B0-18 | `clearwater-field-ops` | 10 | `none` | `null` | empty | empty | empty | `escalation`, `content_route` | `true` |

## Boundary Handling

- `B0-04` and `B0-06` follow the owner's product label; the product-vs-abstain residual is recorded for the report.
- `B0-09` and `B0-14` are widened target rows: either `engineering` or `product` is defensible, while abstention is still scored incorrect.
- `B0-11` remains engineering, with a watched soft spot: if real case text shows a connector request rather than breakage, revisit the route.
- `B0-15` was tightened to engineering-only after the same-model ambiguity probe also landed engineering.
- `B0-07` remains an abstain row because the high-priority webhook failure was resolved in two days and surrounding signals are flat.

## OA-B1 Confirmation

Owner confirmed: "Confirmed: the Part B rows encode the routing oracle."

## OA-B2 Disposition

No independent human second labeler was supplied. A same-model blind ambiguity probe was run by the owner as a correlated ambiguity check, not as inter-rater reliability. It found 16/18 rows consistent with the oracle after widened-row handling, with hard divergence only on `B0-04` and `B0-06`. The spike report must disclose single-oracle provenance and may cite the same-model pass only as an ambiguity probe.

## Packet Schema Note

The internal bridge packet carries `abstained: bool` and `reason: str` as first-class fields. This mirrors the existing Slot-A `unknown` fail-closed classification pattern and the reconciliation agent's confidence cap: uncertainty is represented structurally rather than as a new customer-facing action type. Full schema unification is a follow-on; this spike keeps the packet additive.

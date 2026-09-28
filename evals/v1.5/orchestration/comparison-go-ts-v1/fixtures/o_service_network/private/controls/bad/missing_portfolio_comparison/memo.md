# Regional service-network decision, 30 June 2026

I recommend retaining both east and west facilities for the next review period. The single-facility rows are cheaper only because they omit work assigned to the other region. The frozen orders do not establish that customers or technicians can move between regions. Revisit the option after validating travel times, cross-training and demand with observed operations.

Recommendation: east+west

Criterion: Retain coverage for all observed assigned work while capacity remains feasible; accept the higher recorded monthly facility cost pending a fuller operating study.

Uncertainty: These synthetic orders cannot establish transferable regional demand, travel time, or future SLA performance.

| Metric pointer | Value | Source IDs |
| --- | ---: | --- |
| /selection/orders | 12 | orders-v1 |
| /selection/cancelled | 2 | events-v1 |
| /selection/completed | 8 | events-v1 |
| /backlog | 2 | orders-v1, events-v1 |
| /sla/eligible | 8 | orders-v1, events-v1, sla-v1 |
| /sla/on_time | 3 | orders-v1, events-v1, sla-v1 |
| /sla/attainment | 0.3750 | orders-v1, events-v1, sla-v1 |
| /sla/credit_cents | 5800 | orders-v1, events-v1, sla-v1 |
| /sla/unknown_credit_jobs | 1 | orders-v1, events-v1, sla-v1 |
| /part_cost/known_cents | 25100 | events-v1, rates-v1 |
| /part_cost/unknown_part_cost_jobs | 1 | events-v1 |
| /portfolios/east/monthly_cost_cents | 190000 | capacity-v1 |
| /portfolios/east/completed_jobs | 5 | orders-v1, events-v1 |
| /portfolios/east/available_minutes | 800 | capacity-v1 |
| /portfolios/east/used_minutes | 525 | orders-v1, events-v1 |
| /portfolios/east/feasible | true | capacity-v1, orders-v1, events-v1 |
| /portfolios/west/monthly_cost_cents | 150000 | capacity-v1 |
| /portfolios/west/completed_jobs | 3 | orders-v1, events-v1 |
| /portfolios/west/available_minutes | 600 | capacity-v1 |
| /portfolios/west/feasible | true | capacity-v1, orders-v1, events-v1 |
| /portfolios/east+west/monthly_cost_cents | 385000 | capacity-v1, shared-v1 |
| /portfolios/east+west/completed_jobs | 8 | orders-v1, events-v1 |
| /portfolios/east+west/available_minutes | 1400 | capacity-v1 |
| /portfolios/east+west/used_minutes | 765 | orders-v1, events-v1 |
| /portfolios/east+west/feasible | true | capacity-v1, orders-v1, events-v1 |
| /sensitivity/relay_plus_10_part_cost_cents | 26820 | events-v1, rates-v1 |

The east-only portfolio preserves east assignments and the west-only portfolio preserves west assignments; neither represents full regional coverage. The joint portfolio has observed capacity headroom, though this dataset is too small and synthetic to support a demand forecast. The relay sensitivity changes a supplier input only; it leaves SLA, labor and fixed costs unchanged.

## Operating plan

Keep the current two-site schedule for one measurement period. Reconcile corrections weekly by recorded revision and inspect every missing charge or part quantity before invoice or credit decisions. Track completion time against the policy effective when each order opened. Review the two outstanding jobs with dispatch and record whether they are truly actionable.

## Risks and assumptions

| Type | Item | Effect on decision |
| --- | --- | --- |
| Risk | Missing invoice amounts and part quantities | Credit and part-cost totals can rise after reconciliation. |
| Assumption | Frozen site assignments remain local | Single-site scenarios omit another region's assigned work. |
| Validation | Travel and cross-training data are not present | Check before any closure or transfer decision. |

The order set is a frozen snapshot, not a market sample. Capacity is a monthly allocation and travel time is absent. Missing charges and quantities remain unknown. Credits are calculated on known charges only and may rise after reconciliation. A lower supplier rate revision is effective by completion date; the sensitivity is a scenario, not a signed price. This uncertainty prevents a closure decision until coverage and transfer feasibility are validated.

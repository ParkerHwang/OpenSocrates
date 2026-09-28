# Regional repair-network decision (synthetic, current source room)

Recommendation: east+west+north

Criterion: Preserve substantially more observed assigned work than the cheaper eligible pairs, while retaining baseline capacity feasibility; accept the larger lower-bound period cost only with a west-June capacity contingency and a separate review of omitted southern work.

Uncertainty: The source room is synthetic; unknown southern labor, missing part lines and credits make costs lower bounds, and recorded assignments do not prove that excluded work can move between sites or predict future demand.

The ranking in the evidence below is conditional on the declared coverage threshold and known costs. The cheaper eligible pair options cover fewer of the assigned completed jobs. Any option containing south has unresolved capacity feasibility because one selected completed job lacks work minutes. The west-June sensitivity removes eligibility from the recommended network, so dispatch must establish additional west capacity or use the eligible east+north contingency before adopting the recommendation.

| Metric pointer | Value | Source IDs |
| --- | ---: | --- |
| /selection/orders | 160 | orders-v2 |
| /selection/corrected | 40 | events-initial-v2, events-corrections-v2 |
| /selection/future_ignored | 10 | events-corrections-v2, manifest-v2 |
| /selection/cancelled | 17 | orders-v2, events-initial-v2, events-corrections-v2 |
| /selection/completed | 117 | orders-v2, events-initial-v2, events-corrections-v2 |
| /backlog | 26 | orders-v2, events-initial-v2, events-corrections-v2 |
| /sla/eligible | 117 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2 |
| /sla/on_time | 64 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2 |
| /sla/attainment | 0.5470 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2 |
| /sla/unknown_credit_jobs | 2 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2 |
| /sla/zero_charge_completed_jobs | 4 | orders-v2, events-initial-v2, events-corrections-v2 |
| /cost/known_part_cents | 596600 | orders-v2, events-initial-v2, events-corrections-v2, rates-v2 |
| /cost/unknown_part_lines | 14 | events-initial-v2, events-corrections-v2, rates-v2 |
| /cost/unknown_part_jobs | 14 | orders-v2, events-initial-v2, events-corrections-v2, rates-v2 |
| /cost/known_labor_cents | 1584588 | rates-v2 |
| /cost/unknown_labor_jobs | 1 | orders-v2, events-initial-v2, events-corrections-v2 |
| /cost/known_credit_cents | 77911 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2 |
| /capacity/south/2026-05/unknown_work_jobs | 1 | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2 |
| /capacity/west/2026-06/available_minutes | 1372 | capacity-v2 |
| /capacity/west/2026-06/used_known_minutes | 1234 | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2 |
| /sensitivity/relay_plus_10_known_part_cents | 610250 | orders-v2, events-initial-v2, events-corrections-v2, rates-v2 |
| /sensitivity/west_june_available_after_15pct | 1166 | capacity-v2 |
| /sensitivity/changed_decision_eligibility | ["east+west","east+west+north"] | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+north/covered_completed_jobs | 72 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/east+north/coverage_ratio | 0.6154 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/east+north/known_variable_cents | 1464146 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, portfolios-v2 |
| /portfolios/east+north/fixed_shared_cents | 1528000 | capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+north/period_cost_lower_bound_cents | 2992146 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+north/capacity_feasible | true | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2 |
| /portfolios/east+north/decision_eligible | true | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+north+south/covered_completed_jobs | 84 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/east+north+south/coverage_ratio | 0.7179 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/east+north+south/known_variable_cents | 1623262 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, portfolios-v2 |
| /portfolios/east+north+south/fixed_shared_cents | 2324000 | capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+north+south/period_cost_lower_bound_cents | 3947262 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+north+south/capacity_feasible | false | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2 |
| /portfolios/east+north+south/decision_eligible | false | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+south/covered_completed_jobs | 55 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/east+south/coverage_ratio | 0.4701 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/east+south/known_variable_cents | 1110183 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, portfolios-v2 |
| /portfolios/east+south/fixed_shared_cents | 1560000 | capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+south/period_cost_lower_bound_cents | 2670183 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+south/capacity_feasible | false | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2 |
| /portfolios/east+south/decision_eligible | false | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+west/covered_completed_jobs | 76 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/east+west/coverage_ratio | 0.6496 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/east+west/known_variable_cents | 1586904 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, portfolios-v2 |
| /portfolios/east+west/fixed_shared_cents | 1720000 | capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+west/period_cost_lower_bound_cents | 3306904 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+west/capacity_feasible | true | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2 |
| /portfolios/east+west/decision_eligible | true | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+west+north/covered_completed_jobs | 105 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/east+west+north/coverage_ratio | 0.8974 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/east+west+north/known_variable_cents | 2099983 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, portfolios-v2 |
| /portfolios/east+west+north/fixed_shared_cents | 2560000 | capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+west+north/period_cost_lower_bound_cents | 4659983 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+west+north/capacity_feasible | true | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2 |
| /portfolios/east+west+north/decision_eligible | true | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+west+north+south/covered_completed_jobs | 117 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/east+west+north+south/coverage_ratio | 1.0000 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/east+west+north+south/known_variable_cents | 2259099 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, portfolios-v2 |
| /portfolios/east+west+north+south/fixed_shared_cents | 3452000 | capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+west+north+south/period_cost_lower_bound_cents | 5711099 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+west+north+south/capacity_feasible | false | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2 |
| /portfolios/east+west+north+south/decision_eligible | false | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+west+south/covered_completed_jobs | 88 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/east+west+south/coverage_ratio | 0.7521 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/east+west+south/known_variable_cents | 1746020 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, portfolios-v2 |
| /portfolios/east+west+south/fixed_shared_cents | 2536000 | capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+west+south/period_cost_lower_bound_cents | 4282020 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/east+west+south/capacity_feasible | false | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2 |
| /portfolios/east+west+south/decision_eligible | false | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2, manifest-v2 |
| /portfolios/north+south/covered_completed_jobs | 41 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/north+south/coverage_ratio | 0.3504 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/north+south/known_variable_cents | 672195 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, portfolios-v2 |
| /portfolios/north+south/fixed_shared_cents | 1156000 | capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/north+south/period_cost_lower_bound_cents | 1828195 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/north+south/capacity_feasible | false | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2 |
| /portfolios/north+south/decision_eligible | false | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2, manifest-v2 |
| /portfolios/west+north/covered_completed_jobs | 62 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/west+north/coverage_ratio | 0.5299 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/west+north/known_variable_cents | 1148916 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, portfolios-v2 |
| /portfolios/west+north/fixed_shared_cents | 1432000 | capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/west+north/period_cost_lower_bound_cents | 2580916 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/west+north/capacity_feasible | true | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2 |
| /portfolios/west+north/decision_eligible | false | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2, manifest-v2 |
| /portfolios/west+south/covered_completed_jobs | 45 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/west+south/coverage_ratio | 0.3846 | orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2 |
| /portfolios/west+south/known_variable_cents | 794953 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, portfolios-v2 |
| /portfolios/west+south/fixed_shared_cents | 1296000 | capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/west+south/period_cost_lower_bound_cents | 2090953 | orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, shared-v2, portfolios-v2, manifest-v2 |
| /portfolios/west+south/capacity_feasible | false | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2 |
| /portfolios/west+south/decision_eligible | false | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2, manifest-v2 |

## Operating plan

Reconcile every correction at event grain before monthly reporting. Obtain the missing southern work duration, then rerun capacity and option eligibility. Reconcile unknown part quantities/rates and missing charges before treating any cost lower bound as a budget. Confirm west-June staffing or documented spillover capacity and rerun the local sensitivity before a network change. Track eligible SLA by creation-time policy, not by the latest policy value. Keep the current assigned-service footprint until transfer times and customer impact are measured.

## Risks and assumptions

| Type | Issue | Decision implication |
| --- | --- | --- |
| Risk | Southern completed work has unknown duration. | Capacity feasibility for options including south remains unresolved. |
| Risk | Some parts or late-job charges are unknown. | Cost figures are lower bounds and can rise after correction. |
| Assumption | Work stays at its recorded facility. | Lower-cost options omit assigned work; transfer is not established. |
| Validation | West-June capacity is narrow. | Recheck staffing before accepting the recommended option. |
| Validation | The source room is synthetic. | Observe demand and travel before any permanent site decision. |

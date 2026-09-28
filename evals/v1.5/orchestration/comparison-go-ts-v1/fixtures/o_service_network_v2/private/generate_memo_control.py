#!/usr/bin/env python3
"""Author the private positive memo control from verified metric JSON."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "private/controls/good/metrics.json"
OUT = ROOT / "private/controls/good/memo.md"


def pointer(data: dict, name: str):
    value = data
    for key in name.lstrip("/").split("/"):
        value = value[key]
    return value


def display(value) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return json.dumps(value, separators=(",", ":"))
    return str(value)


def main() -> None:
    data = json.loads(METRICS.read_text())
    lines = [
        "# Regional repair-network decision (synthetic, current source room)",
        "",
        "Recommendation: east+west+north",
        "",
        "Criterion: Preserve substantially more observed assigned work than the cheaper eligible pairs, while retaining baseline capacity feasibility; accept the larger lower-bound period cost only with a west-June capacity contingency and a separate review of omitted southern work.",
        "",
        "Uncertainty: The source room is synthetic; unknown southern labor, missing part lines and credits make costs lower bounds, and recorded assignments do not prove that excluded work can move between sites or predict future demand.",
        "",
        "The ranking in the evidence below is conditional on the declared coverage threshold and known costs. The cheaper eligible pair options cover fewer of the assigned completed jobs. Any option containing south has unresolved capacity feasibility because one selected completed job lacks work minutes. The west-June sensitivity removes eligibility from the recommended network, so dispatch must establish additional west capacity or use the eligible east+north contingency before adopting the recommendation.",
        "",
        "| Metric pointer | Value | Source IDs |",
        "| --- | ---: | --- |",
    ]
    provenance = {
        "/selection/orders": "orders-v2",
        "/selection/corrected": "events-initial-v2, events-corrections-v2",
        "/selection/future_ignored": "events-corrections-v2, manifest-v2",
        "/selection/cancelled": "orders-v2, events-initial-v2, events-corrections-v2",
        "/selection/completed": "orders-v2, events-initial-v2, events-corrections-v2",
        "/backlog": "orders-v2, events-initial-v2, events-corrections-v2",
        "/sla/eligible": "orders-v2, events-initial-v2, events-corrections-v2, sla-v2",
        "/sla/on_time": "orders-v2, events-initial-v2, events-corrections-v2, sla-v2",
        "/sla/attainment": "orders-v2, events-initial-v2, events-corrections-v2, sla-v2",
        "/sla/unknown_credit_jobs": "orders-v2, events-initial-v2, events-corrections-v2, sla-v2",
        "/sla/zero_charge_completed_jobs": "orders-v2, events-initial-v2, events-corrections-v2",
        "/cost/known_part_cents": "orders-v2, events-initial-v2, events-corrections-v2, rates-v2",
        "/cost/unknown_part_lines": "events-initial-v2, events-corrections-v2, rates-v2",
        "/cost/unknown_part_jobs": "orders-v2, events-initial-v2, events-corrections-v2, rates-v2",
        "/cost/known_labor_cents": "orders-v2, events-initial-v2, events-corrections-v2, capacity-v2",
        "/cost/unknown_labor_jobs": "orders-v2, events-initial-v2, events-corrections-v2",
        "/cost/known_credit_cents": "orders-v2, events-initial-v2, events-corrections-v2, sla-v2",
        "/capacity/south/2026-05/unknown_work_jobs": "orders-v2, events-initial-v2, events-corrections-v2, capacity-v2",
        "/capacity/west/2026-06/available_minutes": "capacity-v2",
        "/capacity/west/2026-06/used_known_minutes": "orders-v2, events-initial-v2, events-corrections-v2, capacity-v2",
        "/sensitivity/relay_plus_10_known_part_cents": "orders-v2, events-initial-v2, events-corrections-v2, rates-v2",
        "/sensitivity/west_june_available_after_15pct": "capacity-v2",
        "/sensitivity/changed_decision_eligibility": "orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2, manifest-v2",
    }
    first = list(provenance)
    for name in first:
        lines.append(f"| {name} | {display(pointer(data, name))} | {provenance[name]} |")
    portfolio_sources = {
        "covered_completed_jobs": "orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2",
        "coverage_ratio": "orders-v2, events-initial-v2, events-corrections-v2, portfolios-v2",
        "known_variable_cents": "orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, portfolios-v2",
        "fixed_shared_cents": "capacity-v2, shared-v2, portfolios-v2, manifest-v2",
        "period_cost_lower_bound_cents": "orders-v2, events-initial-v2, events-corrections-v2, sla-v2, rates-v2, capacity-v2, shared-v2, portfolios-v2, manifest-v2",
        "capacity_feasible": "orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2",
        "decision_eligible": "orders-v2, events-initial-v2, events-corrections-v2, capacity-v2, portfolios-v2, manifest-v2",
    }
    for name in data["portfolios"]:
        for field, sources in portfolio_sources.items():
            key = f"/portfolios/{name}/{field}"
            lines.append(f"| {key} | {display(pointer(data, key))} | {sources} |")
    lines += [
        "",
        "## Operating plan",
        "",
        "Reconcile every correction at event grain before monthly reporting. Obtain the missing southern work duration, then rerun capacity and option eligibility. Reconcile unknown part quantities/rates and missing charges before treating any cost lower bound as a budget. Confirm west-June staffing or documented spillover capacity and rerun the local sensitivity before a network change. Track eligible SLA by creation-time policy, not by the latest policy value. Keep the current assigned-service footprint until transfer times and customer impact are measured.",
        "",
        "## Risks and assumptions",
        "",
        "| Type | Issue | Decision implication |",
        "| --- | --- | --- |",
        "| Risk | Southern completed work has unknown duration. | Capacity feasibility for options including south remains unresolved. |",
        "| Risk | Some parts or late-job charges are unknown. | Cost figures are lower bounds and can rise after correction. |",
        "| Assumption | Work stays at its recorded facility. | Lower-cost options omit assigned work; transfer is not established. |",
        "| Validation | West-June capacity is narrow. | Recheck staffing before accepting the recommended option. |",
        "| Validation | The source room is synthetic. | Observe demand and travel before any permanent site decision. |",
        "",
    ]
    OUT.write_text("\n".join(lines))


if __name__ == "__main__":
    main()

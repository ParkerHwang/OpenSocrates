"""Independent private Python answer key for the larger synthetic O v2 room."""
from __future__ import annotations

import hashlib
import itertools
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path


def read(data: Path, filename: str):
    return json.loads((data / filename).read_text())


def instant(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def money(numerator: int, denominator: int) -> int:
    return int((Decimal(numerator) / Decimal(denominator)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def four(numerator: int, denominator: int) -> str | None:
    if denominator == 0:
        return None
    return str((Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def dated(rows: list[dict], identity_key: str, identity: str, at: str) -> dict | None:
    valid = [row for row in rows if row[identity_key] == identity and instant(row["effective_at"]) <= instant(at)]
    return sorted(valid, key=lambda row: (instant(row["effective_at"]), row["revision"]))[-1] if valid else None


def expected(data: Path) -> tuple[dict, list[dict]]:
    manifest = read(data, "manifest.json")
    orders = read(data, "orders.json")
    stream = read(data, "events_initial.json") + read(data, "events_corrections.json")
    policies = read(data, "sla_policies.json")
    rates = read(data, "supplier_rates.json")
    capacity = read(data, "capacity.json")
    shared = read(data, "shared_costs.json")
    options = read(data, "portfolios.json")
    register = [{"id": "manifest-v2", "path": "manifest.json", "sha256": hashlib.sha256((data / "manifest.json").read_bytes()).hexdigest()}] + [
        {"id": item["id"], "path": item["path"], "sha256": hashlib.sha256((data / item["path"]).read_bytes()).hexdigest()}
        for item in manifest["sources"]
    ]
    assert len({item["order_id"] for item in orders}) == len(orders)
    assert len({item["event_id"] for item in stream}) == len(stream)
    order_by_id = {item["order_id"]: item for item in orders}
    grouped = defaultdict(list)
    future = 0
    for item in stream:
        assert item["order_id"] in order_by_id
        if instant(item["recorded_at"]) > instant(manifest["decision_at"]):
            future += 1
        else:
            grouped[item["order_id"]].append(item)
    selected = {
        order_id: max(events, key=lambda item: (instant(item["recorded_at"]), item["revision"], item["event_id"]))
        for order_id, events in grouped.items()
    }
    assert set(selected) == set(order_by_id)
    capacity_by_site_month = {(item["facility"], item["month"]): item for item in capacity}
    months = manifest["period_months"]
    assert len(capacity_by_site_month) == 4 * len(months)
    pair_cost = {frozenset((item["facility_a"], item["facility_b"])): item["monthly_cents"] for item in shared}
    assert len(pair_cost) == 6
    used = defaultdict(int)
    unknown_work = defaultdict(int)
    jobs = []
    cancelled = backlog = completed = eligible = on_time = known_credit = unknown_credit = zero_charge = 0
    known_parts = unknown_lines = known_labor = unknown_labor = 0
    unknown_part_job_ids = set()
    relay_sensitivity = 0
    for order in orders:
        event = selected[order["order_id"]]
        if event["status"] == "cancelled":
            cancelled += 1
            continue
        if event["status"] in ("open", "scheduled"):
            backlog += 1
            continue
        assert event["status"] == "completed" and event["completed_at"] is not None
        completed += 1
        completion = event["completed_at"]
        month = completion[:7]
        assert month in months
        facility = order["facility"]
        cap = capacity_by_site_month[(facility, month)]
        if event["charge_cents"] == 0:
            zero_charge += 1
        credit = 0
        eligible += 1
        policy = dated(policies, "priority", order["priority"], order["created_at"])
        assert policy is not None
        due = instant(order["created_at"]) + timedelta(hours=policy["target_hours"])
        if instant(completion) <= due:
            on_time += 1
        elif event["charge_cents"] is None:
            unknown_credit += 1
        else:
            credit = money(event["charge_cents"] * policy["credit_bps"], 10000)
            known_credit += credit
        labor = 0
        if event["work_minutes"] is None:
            unknown_labor += 1
            unknown_work[(facility, month)] += 1
        else:
            used[(facility, month)] += event["work_minutes"]
            labor = money(event["work_minutes"] * cap["loaded_hourly_cents"], 60)
            known_labor += labor
        parts_total = 0
        for line in event["parts"]:
            qty = line["qty"]
            if qty is None:
                unknown_lines += 1
                unknown_part_job_ids.add(order["order_id"])
                continue
            assert qty >= 0
            if qty == 0:
                continue
            rate = dated(rates, "part", line["part"], completion)
            if rate is None:
                unknown_lines += 1
                unknown_part_job_ids.add(order["order_id"])
                continue
            parts_total += qty * rate["unit_cost_cents"]
            unit = rate["unit_cost_cents"]
            if line["part"] == "relay" and instant(rate["effective_at"]) >= instant("2026-04-01T00:00:00Z"):
                unit = money(unit * 110, 100)
            relay_sensitivity += qty * unit
        known_parts += parts_total
        jobs.append({"facility": facility, "known_variable_cents": credit + labor + parts_total})
    capacity_result = {}
    for site in ("east", "west", "north", "south"):
        capacity_result[site] = {}
        for month in months:
            row = capacity_by_site_month[(site, month)]
            capacity_result[site][month] = {"available_minutes": row["available_minutes"], "used_known_minutes": used[(site, month)], "unknown_work_jobs": unknown_work[(site, month)]}
    threshold = Decimal(manifest["coverage_threshold"])

    def portfolio(members: list[str], changed_west_june: bool = False) -> dict:
        subset = set(members)
        covered = [job for job in jobs if job["facility"] in subset]
        coverage = four(len(covered), completed)
        feasible = True
        for site in members:
            for month in months:
                row = capacity_by_site_month[(site, month)]
                available = row["available_minutes"]
                if changed_west_june and site == "west" and month == "2026-06":
                    available = int((Decimal(available) * Decimal("0.85")).to_integral_value(rounding=ROUND_FLOOR))
                if unknown_work[(site, month)] or used[(site, month)] > available:
                    feasible = False
        fixed_shared = sum(capacity_by_site_month[(site, month)]["fixed_monthly_cents"] for site in members for month in months)
        fixed_shared += len(months) * sum(pair_cost[frozenset(pair)] for pair in itertools.combinations(members, 2))
        variable = sum(job["known_variable_cents"] for job in covered)
        return {"covered_completed_jobs": len(covered), "coverage_ratio": coverage, "known_variable_cents": variable, "fixed_shared_cents": fixed_shared, "period_cost_lower_bound_cents": fixed_shared + variable, "capacity_feasible": feasible, "decision_eligible": feasible and Decimal(coverage) >= threshold}

    portfolio_result = {}
    changed_capacity = []
    changed_eligible = []
    for option in options:
        name, members = option["id"], option["facilities"]
        assert name == "+".join(members)
        baseline = portfolio(members)
        scenario = portfolio(members, changed_west_june=True)
        portfolio_result[name] = baseline
        if baseline["capacity_feasible"] != scenario["capacity_feasible"]:
            changed_capacity.append(name)
        if baseline["decision_eligible"] != scenario["decision_eligible"]:
            changed_eligible.append(name)
    ranking = sorted((name for name, value in portfolio_result.items() if value["decision_eligible"]), key=lambda name: (portfolio_result[name]["period_cost_lower_bound_cents"], name))
    west_june = capacity_by_site_month[("west", "2026-06")]["available_minutes"]
    result = {
        "selection": {"orders": len(orders), "selected_events": len(selected), "future_ignored": future, "corrected": sum(event["revision"] > 1 for event in selected.values()), "cancelled": cancelled, "completed": completed},
        "backlog": backlog,
        "sla": {"eligible": eligible, "on_time": on_time, "late": eligible - on_time, "attainment": four(on_time, eligible), "known_credit_cents": known_credit, "unknown_credit_jobs": unknown_credit, "zero_charge_completed_jobs": zero_charge},
        "cost": {"known_part_cents": known_parts, "unknown_part_lines": unknown_lines, "unknown_part_jobs": len(unknown_part_job_ids), "known_labor_cents": known_labor, "unknown_labor_jobs": unknown_labor, "known_credit_cents": known_credit, "unknown_credit_jobs": unknown_credit},
        "capacity": capacity_result,
        "portfolios": portfolio_result,
        "eligible_ranking": ranking,
        "sensitivity": {"baseline_known_part_cents": known_parts, "relay_plus_10_known_part_cents": relay_sensitivity, "west_june_available_baseline": west_june, "west_june_available_after_15pct": int((Decimal(west_june) * Decimal("0.85")).to_integral_value(rounding=ROUND_FLOOR)), "changed_capacity_feasibility": sorted(changed_capacity), "changed_decision_eligibility": sorted(changed_eligible)},
    }
    return result, register

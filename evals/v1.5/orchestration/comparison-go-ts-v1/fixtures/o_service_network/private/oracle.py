"""Independent, data-driven external answer key for the synthetic service room.

Never copy this module into a subject input, source ID or candidate directory.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


def load(data: Path, filename: str):
    return json.loads((data / filename).read_text())


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def rounded(numerator: int, denominator: int) -> int:
    return int((Decimal(numerator) / denominator).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def choose_dated(rows: list[dict], key: str, identity: str, at: str) -> dict | None:
    options = [row for row in rows if row[key] == identity and instant(row["effective_at"]) <= instant(at)]
    return max(options, key=lambda row: (instant(row["effective_at"]), row["revision"])) if options else None


def expected(data: Path) -> tuple[dict, list[dict]]:
    manifest = load(data, "manifest.json")
    orders = load(data, "orders.json")
    events = load(data, "events.json")
    policies = load(data, "sla_policies.json")
    rates = load(data, "supplier_rates.json")
    capacities = load(data, "capacity.json")
    shared = load(data, "shared_costs.json")
    source_register = [
        {"id": source["id"], "path": source["path"], "sha256": hashlib.sha256((data / source["path"]).read_bytes()).hexdigest()}
        for source in manifest["sources"]
    ]
    assert len({event["event_id"] for event in events}) == len(events)
    cutoff = instant(manifest["decision_at"])
    groups: dict[str, list[dict]] = defaultdict(list)
    future_ignored = 0
    for event in events:
        if instant(event["recorded_at"]) > cutoff:
            future_ignored += 1
        else:
            groups[event["order_id"]].append(event)
    chosen = {
        key: sorted(group, key=lambda row: (instant(row["recorded_at"]), row["revision"], row["event_id"]))[-1]
        for key, group in groups.items()
    }
    available = {row["facility"]: row["available_minutes"] for row in capacities}
    fixed = {row["facility"]: row["fixed_monthly_cents"] for row in capacities}
    used = {key: 0 for key in available}
    jobs = {key: 0 for key in available}
    cancelled = completed = backlog = eligible = on_time = credit = missing_credit = known_parts = missing_parts = 0
    sensitivity_parts = 0
    for order in orders:
        event = chosen[order["order_id"]]
        status = event["status"]
        if status == "cancelled":
            cancelled += 1
            continue
        if status in {"open", "scheduled"}:
            backlog += 1
            continue
        assert status == "completed"
        completed += 1
        jobs[order["facility"]] += 1
        if event["work_minutes"] is not None:
            used[order["facility"]] += event["work_minutes"]
        if event["completed_at"] is not None:
            eligible += 1
            policy = choose_dated(policies, "priority", order["priority"], order["created_at"])
            assert policy is not None
            deadline = instant(order["created_at"]) + timedelta(hours=policy["target_hours"])
            if instant(event["completed_at"]) <= deadline:
                on_time += 1
            elif event["charge_cents"] is None:
                missing_credit += 1
            else:
                credit += rounded(event["charge_cents"] * policy["credit_bps"], 10000)
        if event["part"] is None or event["part_qty"] is None or event["completed_at"] is None:
            missing_parts += 1
        else:
            rate = choose_dated(rates, "part", event["part"], event["completed_at"])
            if rate is None:
                missing_parts += 1
            else:
                known_parts += event["part_qty"] * rate["unit_cost_cents"]
                newer_relay = event["part"] == "relay" and instant(rate["effective_at"]) >= instant("2026-04-01T00:00:00Z")
                adjusted = rounded(rate["unit_cost_cents"] * 110, 100) if newer_relay else rate["unit_cost_cents"]
                sensitivity_parts += event["part_qty"] * adjusted
    portfolios = {}
    for members in (("east",), ("west",), ("east", "west")):
        name = "+".join(members)
        capacity = sum(available[x] for x in members)
        workload = sum(used[x] for x in members)
        portfolios[name] = {
            "available_minutes": capacity,
            "used_minutes": workload,
            "completed_jobs": sum(jobs[x] for x in members),
            "monthly_cost_cents": sum(fixed[x] for x in members) + (shared["dispatch_monthly_cents"] if len(members) > 1 else 0),
            "feasible": capacity >= workload,
        }
    metrics = {
        "selection": {"orders": len(orders), "selected_events": len(chosen), "future_ignored": future_ignored, "cancelled": cancelled, "completed": completed},
        "backlog": backlog,
        "sla": {"eligible": eligible, "on_time": on_time, "late": eligible - on_time, "attainment": str((Decimal(on_time) / eligible).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)) if eligible else None, "credit_cents": credit, "unknown_credit_jobs": missing_credit},
        "capacity": {name: {"available_minutes": minutes, "used_minutes": used[name]} for name, minutes in available.items()},
        "part_cost": {"known_cents": known_parts, "unknown_part_cost_jobs": missing_parts},
        "portfolios": portfolios,
        "sensitivity": {"baseline_part_cost_cents": known_parts, "relay_plus_10_part_cost_cents": sensitivity_parts},
    }
    return metrics, source_register

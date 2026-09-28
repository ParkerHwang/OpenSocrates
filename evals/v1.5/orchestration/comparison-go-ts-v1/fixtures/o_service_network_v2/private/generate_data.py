#!/usr/bin/env python3
"""Deterministic synthetic data-room authoring; never stage this generator to roles."""
from __future__ import annotations

import json
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public/data"
UTC = timezone.utc


def stamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def rows(name: str, values: list[dict]) -> None:
    content = "[\n" + ",\n".join(json.dumps(item, separators=(",", ":"), ensure_ascii=False) for item in values) + "\n]\n"
    (DATA / name).write_text(content)


def document(name: str, value: dict) -> None:
    (DATA / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def part_lines(index: int, corrected: bool = False) -> list[dict]:
    names = ("relay", "seal", "pump")
    shift = 1 if corrected else 0
    lines = [{"part": names[(index + shift) % 3], "qty": (index + shift) % 4}]
    if index % 5 == 0:
        lines.append({"part": names[(index + 1 + shift) % 3], "qty": (index + 2) % 3})
    if index % 17 == 0:
        lines.append({"part": "obsolete", "qty": 1})
    if index % 19 == 0:
        lines[0]["qty"] = None
    return lines


def completed_fields(index: int, created: datetime, warranty: bool, corrected: bool = False) -> dict:
    duration = 6 + (index * 7) % 84 + (4 if corrected else 0)
    completed = created + timedelta(hours=duration)
    charge = 0 if warranty else (None if index % 29 == 0 else 12000 + (index * 191) % 28000)
    if corrected and charge is not None and not warranty:
        charge += 350
    return {"status": "completed", "completed_at": stamp(completed), "work_minutes": 45 + (index * 13) % 210 + (10 if corrected else 0), "charge_cents": charge, "parts": part_lines(index, corrected)}


def main() -> None:
    rng = random.Random(20260928)
    facilities = ["east"] * 58 + ["west"] * 44 + ["north"] * 36 + ["south"] * 22
    rng.shuffle(facilities)
    orders, initial, corrections = [], [], []
    by_order = {}
    for index in range(1, 161):
        month = 3 + ((index * 7) % 4)
        created = datetime(2026, month, 1 + ((index * 11) % 20), 8 + (index % 9), tzinfo=UTC)
        order_id = f"WO-{index:04d}"
        warranty = index % 9 == 0
        facility = facilities[index - 1]
        order = {"order_id": order_id, "created_at": stamp(created), "priority": "urgent" if index % 3 == 0 else "standard", "facility": facility, "warranty": warranty}
        orders.append(order)
        if index % 13 == 0:
            fields = {"status": "cancelled", "completed_at": None, "work_minutes": None, "charge_cents": None, "parts": []}
        elif index % 9 == 0:
            fields = {"status": "scheduled", "completed_at": None, "work_minutes": None, "charge_cents": None, "parts": []}
        elif index % 7 == 0:
            fields = {"status": "open", "completed_at": None, "work_minutes": None, "charge_cents": None, "parts": []}
        else:
            fields = completed_fields(index, created, warranty)
        recorded = datetime.fromisoformat(fields["completed_at"].replace("Z", "+00:00")) + timedelta(hours=1) if fields["completed_at"] else created + timedelta(hours=2)
        base = {"event_id": f"EV-I-{index:04d}", "order_id": order_id, "recorded_at": stamp(recorded), "revision": 1, **fields}
        initial.append(base)
        chosen = base
        if index % 4 == 0:
            if index % 16 == 0 and fields["status"] == "completed":
                corrected = {"status": "cancelled", "completed_at": None, "work_minutes": None, "charge_cents": None, "parts": []}
            else:
                corrected = completed_fields(index, created, warranty, corrected=True)
            correction_time = datetime(2026, 7, 1 + (index % 11), 12, tzinfo=UTC)
            update = {"event_id": f"EV-C-{index:04d}", "order_id": order_id, "recorded_at": stamp(correction_time), "revision": 2, **corrected}
            corrections.append(update)
            chosen = update
            if index % 20 == 0:
                tie = dict(update)
                tie["event_id"] = f"EV-T-{index:04d}"
                tie["revision"] = 3
                if tie["status"] == "completed" and tie["charge_cents"] is not None and not warranty:
                    tie["charge_cents"] += 250
                corrections.append(tie)
                chosen = tie
                if index == 20:
                    same_revision = dict(tie)
                    same_revision["event_id"] = "EV-U-0020"
                    same_revision["work_minutes"] += 17
                    corrections.append(same_revision)
                    chosen = same_revision
        if index % 15 == 0:
            future = {"event_id": f"EV-F-{index:04d}", "order_id": order_id, "recorded_at": "2026-07-16T09:00:00Z", "revision": 9, "status": "cancelled", "completed_at": None, "work_minutes": None, "charge_cents": None, "parts": []}
            corrections.append(future)
        by_order[order_id] = chosen
    # One completed May order crosses into June. The selected event is recorded
    # after that completion, so labor capacity and supplier joins use June.
    crossing = by_order["WO-0038"]
    assert crossing["status"] == "completed" and crossing["revision"] == 1
    crossing_created = datetime.fromisoformat(orders[37]["created_at"].replace("Z", "+00:00"))
    crossing_completed = crossing_created + timedelta(days=13)
    assert crossing_created.strftime("%Y-%m") == "2026-05" and crossing_completed.strftime("%Y-%m") == "2026-06"
    crossing["completed_at"] = stamp(crossing_completed)
    crossing["recorded_at"] = stamp(crossing_completed + timedelta(hours=1))
    # One genuinely completed southern job has unknown labor minutes. This
    # keeps its charge/parts/SLA known while making southern capacity uncertain.
    for order in orders:
        selected_event = by_order[order["order_id"]]
        if order["facility"] == "south" and selected_event["status"] == "completed":
            selected_event["work_minutes"] = None
            break
    rng.shuffle(initial)
    rng.shuffle(corrections)
    rows("orders.json", orders)
    rows("events_initial.json", initial)
    rows("events_corrections.json", corrections)
    policies = [
        {"priority": "urgent", "effective_at": "2026-01-01T00:00:00Z", "revision": 1, "target_hours": 36, "credit_bps": 800},
        {"priority": "urgent", "effective_at": "2026-04-01T00:00:00Z", "revision": 2, "target_hours": 24, "credit_bps": 1200},
        {"priority": "urgent", "effective_at": "2026-04-01T00:00:00Z", "revision": 3, "target_hours": 22, "credit_bps": 1100},
        {"priority": "urgent", "effective_at": "2026-05-15T00:00:00Z", "revision": 4, "target_hours": 18, "credit_bps": 900},
        {"priority": "urgent", "effective_at": "2026-06-01T00:00:00Z", "revision": 5, "target_hours": 20, "credit_bps": 700},
        {"priority": "standard", "effective_at": "2026-01-01T00:00:00Z", "revision": 1, "target_hours": 72, "credit_bps": 500},
        {"priority": "standard", "effective_at": "2026-04-01T00:00:00Z", "revision": 2, "target_hours": 48, "credit_bps": 400},
        {"priority": "standard", "effective_at": "2026-06-01T00:00:00Z", "revision": 3, "target_hours": 60, "credit_bps": 300},
    ]
    rows("sla_policies.json", policies)
    rates = [
        {"part": "relay", "effective_at": "2026-01-01T00:00:00Z", "revision": 1, "unit_cost_cents": 3500},
        {"part": "relay", "effective_at": "2026-04-01T00:00:00Z", "revision": 2, "unit_cost_cents": 2800},
        {"part": "relay", "effective_at": "2026-05-01T00:00:00Z", "revision": 3, "unit_cost_cents": 3200},
        {"part": "relay", "effective_at": "2026-05-01T00:00:00Z", "revision": 4, "unit_cost_cents": 3100},
        {"part": "relay", "effective_at": "2026-06-01T00:00:00Z", "revision": 5, "unit_cost_cents": 2900},
        {"part": "seal", "effective_at": "2026-01-01T00:00:00Z", "revision": 1, "unit_cost_cents": 900},
        {"part": "seal", "effective_at": "2026-05-01T00:00:00Z", "revision": 2, "unit_cost_cents": 750},
        {"part": "seal", "effective_at": "2026-06-01T00:00:00Z", "revision": 3, "unit_cost_cents": 800},
        {"part": "pump", "effective_at": "2026-01-01T00:00:00Z", "revision": 1, "unit_cost_cents": 5200},
        {"part": "pump", "effective_at": "2026-04-01T00:00:00Z", "revision": 2, "unit_cost_cents": 5000},
        {"part": "pump", "effective_at": "2026-06-01T00:00:00Z", "revision": 3, "unit_cost_cents": 4700},
    ]
    rows("supplier_rates.json", rates)
    months = ("2026-03", "2026-04", "2026-05", "2026-06")
    used = defaultdict(int)
    for order in orders:
        event = by_order[order["order_id"]]
        if event["status"] == "completed" and event["completed_at"]:
            if event["work_minutes"] is not None:
                used[(order["facility"], event["completed_at"][:7])] += event["work_minutes"]
    fixed = {"east": 210000, "west": 175000, "north": 145000, "south": 125000}
    hourly = {"east": 6000, "west": 5400, "north": 4800, "south": 4600}
    capacities = []
    for facility in ("east", "west", "north", "south"):
        for month in months:
            minutes = used[(facility, month)]
            if facility == "west" and month == "2026-06":
                available = (minutes * 10 + 8) // 9
            else:
                available = minutes + max(300, minutes // 3)
            capacities.append({"facility": facility, "month": month, "available_minutes": available, "loaded_hourly_cents": hourly[facility], "fixed_monthly_cents": fixed[facility]})
    rows("capacity.json", capacities)
    shared = [
        {"facility_a": "east", "facility_b": "west", "monthly_cents": 45000},
        {"facility_a": "east", "facility_b": "north", "monthly_cents": 27000},
        {"facility_a": "east", "facility_b": "south", "monthly_cents": 55000},
        {"facility_a": "west", "facility_b": "north", "monthly_cents": 38000},
        {"facility_a": "west", "facility_b": "south", "monthly_cents": 24000},
        {"facility_a": "north", "facility_b": "south", "monthly_cents": 19000},
    ]
    rows("shared_costs.json", shared)
    options = [
        {"id": "east+west", "facilities": ["east", "west"]},
        {"id": "east+north", "facilities": ["east", "north"]},
        {"id": "east+south", "facilities": ["east", "south"]},
        {"id": "west+north", "facilities": ["west", "north"]},
        {"id": "west+south", "facilities": ["west", "south"]},
        {"id": "north+south", "facilities": ["north", "south"]},
        {"id": "east+west+north", "facilities": ["east", "west", "north"]},
        {"id": "east+west+south", "facilities": ["east", "west", "south"]},
        {"id": "east+north+south", "facilities": ["east", "north", "south"]},
        {"id": "east+west+north+south", "facilities": ["east", "west", "north", "south"]},
    ]
    rows("portfolios.json", options)
    document("manifest.json", {"schema": "synthetic-service-room/2.0.0", "decision_at": "2026-07-15T23:59:59Z", "period_months": list(months), "coverage_threshold": "0.6000", "sources": [
        {"id": "orders-v2", "path": "orders.json"}, {"id": "events-initial-v2", "path": "events_initial.json"}, {"id": "events-corrections-v2", "path": "events_corrections.json"}, {"id": "sla-v2", "path": "sla_policies.json"}, {"id": "rates-v2", "path": "supplier_rates.json"}, {"id": "capacity-v2", "path": "capacity.json"}, {"id": "shared-v2", "path": "shared_costs.json"}, {"id": "portfolios-v2", "path": "portfolios.json"}
    ]})


if __name__ == "__main__":
    main()

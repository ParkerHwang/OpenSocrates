"""Frozen numerical reference and artifact inspection; no candidate repairs."""

from __future__ import annotations
import argparse
from collections import defaultdict
import csv
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
D = Decimal
CENT = D("0.01")
FIELDS = (
    "shipped_orders",
    "shipped_units",
    "gross_sales_eur",
    "refunds_eur",
    "net_sales_eur",
    "net_cogs_eur",
    "fulfillment_eur",
    "contribution_eur",
    "returned_units",
)


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def latest(records, key):
    result = {}
    for row in records:
        if row[key] not in result or int(row["revision"]) > int(result[row[key]]["revision"]):
            result[row[key]] = row
    return result


def expected(room=HERE / "source-room"):
    fx = defaultdict(list)
    for row in rows(room / "ecb-history.csv"):
        if row["Date"].startswith("2025-"):
            for currency in ("PLN", "CZK"):
                if row[currency] not in ("", "N/A"):
                    fx[(currency, row["Date"][:7])].append(D(row[currency]))
    rates = {k: sum(v) / len(v) for k, v in fx.items()}
    orders = latest(
        [
            r
            for f in ("orders-part1.csv", "orders-part2.csv", "order-corrections.csv")
            for r in rows(room / f)
        ],
        "order_id",
    )
    valid = {
        k: r
        for k, r in orders.items()
        if r["status"] == "shipped"
        and r["is_test"] == "false"
        and r["shipped_at"].startswith("2025-")
    }
    returns = defaultdict(list)
    for r in latest(rows(room / "returns.csv"), "return_id").values():
        if r["order_id"] in valid and r["received_at"] <= "2026-01-31":
            returns[r["order_id"]].append(r)
    costs = rows(room / "unit-costs.csv")
    monthly = defaultdict(lambda: {f: D(0) for f in FIELDS})
    for oid, r in valid.items():
        month = r["shipped_at"][:7]
        rate = D(1) if r["currency"] == "EUR" else rates[(r["currency"], month)]
        qty = int(r["quantity"])
        ret = returns[oid]
        cost = D(
            max(
                (c for c in costs if c["sku"] == r["sku"] and c["valid_from"] <= r["shipped_at"]),
                key=lambda c: c["valid_from"],
            )["unit_cost_eur"]
        )
        gross = ((D(qty) * D(r["unit_price_local"]) - D(r["discount_local"])) / rate).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        refund = (sum((D(x["refund_local"]) for x in ret), D(0)) / rate).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        netcost = (D(qty - sum(int(x["restocked_quantity"]) for x in ret)) * cost).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        fulfill = D(r["fulfillment_eur"]).quantize(CENT)
        value = dict(
            shipped_orders=1,
            shipped_units=qty,
            gross_sales_eur=gross,
            refunds_eur=refund,
            net_sales_eur=gross - refund,
            net_cogs_eur=netcost,
            fulfillment_eur=fulfill,
            contribution_eur=gross - refund - netcost - fulfill,
            returned_units=sum(int(x["quantity"]) for x in ret),
        )
        for k, v in value.items():
            monthly[(r["country"], month)][k] += v
    annual = defaultdict(lambda: {f: D(0) for f in FIELDS})
    for (country, _), r in monthly.items():
        for k, v in r.items():
            annual[country][k] += v

    def metric(keys, values):
        return dict(
            **keys,
            **{k: float(v) for k, v in values.items()},
            margin=float(values["contribution_eur"] / values["net_sales_eur"])
            if values["net_sales_eur"]
            else None,
        )

    context = {}
    for filename, key in [
        ("population.json", "population"),
        ("gdp-per-capita.json", "gdp_per_capita_usd"),
    ]:
        for r in json.loads((room / filename).read_text())[1]:
            identity = (r["countryiso3code"], int(r["date"]))
            context.setdefault(identity, dict(country=identity[0], year=identity[1]))[key] = r[
                "value"
            ]
    scenarios = []
    for option in rows(room / "hub-options.csv"):
        a = annual[option["country"]]
        c = a["contribution_eur"]
        u = a["shipped_units"]
        s = D(option["saving_eur_per_unit"])
        f = D(option["annual_fixed_eur"])
        cap = D(option["capex_eur"])
        for name, uplift in [
            ("low", D(".10")),
            ("base", D(".25")),
            ("high", D(".40")),
            ("stress", D(".25")),
        ]:
            shock = D(".03") * a["gross_sales_eur"] + (
                D(".10") * a["net_sales_eur"] if option["country"] in ("POL", "CZE") else 0
            )
            inc = (
                (c - shock) * (1 + uplift) - c + u * (1 + uplift) * s - f
                if name == "stress"
                else c * uplift + u * (1 + uplift) * s - f
            )
            scenarios.append(
                dict(
                    country=option["country"],
                    scenario=name,
                    incremental_contribution_eur=float(inc.quantize(CENT, rounding=ROUND_HALF_UP)),
                    capex_eur=float(cap),
                    fte=int(option["fte"]),
                    payback_years=float(cap / inc) if inc > 0 else None,
                )
            )
    return dict(
        monthly=[metric(dict(country=c, month=m), v) for (c, m), v in sorted(monthly.items())],
        countries=[metric(dict(country=c), v) for c, v in sorted(annual.items())],
        fx_monthly=[
            dict(currency=c, month=m, local_per_eur=float(v)) for (c, m), v in sorted(rates.items())
        ],
        market_context=list(context.values()),
        hub_scenarios=scenarios,
    )


def check(work):
    result = {
        "groups": [],
        "scope": "deterministic artifact/numerical checks; not semantic consulting judgment",
    }

    def group(name, ok, details=None):
        result["groups"].append(dict(name=name, pass_=bool(ok), details=details))

    target = work / "deliverables/metrics.json"
    if not target.is_file():
        group("metrics_available", False, "deliverables/metrics.json missing")
        return finish(result)
    try:
        actual = json.loads(target.read_text())
    except Exception as e:
        group("metrics_available", False, str(e))
        return finish(result)
    group("metrics_available", True)
    reference = expected()
    spec = [
        ("monthly", ("country", "month")),
        ("countries", ("country",)),
        ("fx_monthly", ("currency", "month")),
        ("market_context", ("country", "year")),
        ("hub_scenarios", ("country", "scenario")),
    ]
    for section, keys in spec:
        records = actual.get(section)
        if not isinstance(records, list):
            group(section + "_shape", False, "expected array")
            continue
        try:
            lookup = {tuple(str(r[k]) for k in keys): r for r in records}
        except Exception as e:
            group(section + "_shape", False, str(e))
            continue
        want = {tuple(str(r[k]) for k in keys): r for r in reference[section]}
        group(
            section + "_shape",
            set(lookup) == set(want) and len(lookup) == len(records),
            {"expected": len(want), "actual": len(records)},
        )
        failures = []
        for identity, row in want.items():
            for field, value in row.items():
                if field in keys:
                    continue
                got = lookup.get(identity, {}).get(field)
                tolerance = (
                    0.05
                    if field.endswith("_eur")
                    else 0.00001
                    if field == "local_per_eur"
                    else 0.001
                    if field in ("margin", "payback_years")
                    else 0.5
                    if field == "gdp_per_capita_usd"
                    else 0
                )
                okay = (
                    got is None
                    if value is None
                    else isinstance(got, (float, int))
                    and not isinstance(got, bool)
                    and abs(got - value) <= tolerance
                )
                if not okay:
                    failures.append(
                        dict(key=list(identity), field=field, expected=value, actual=got)
                    )
        group(section + "_values", not failures, failures)
    recommendation = actual.get("recommendation", {})
    opts = {r["country"]: r for r in rows(HERE / "source-room/hub-options.csv")}
    selected = recommendation.get("countries")
    valid = (
        isinstance(selected, list)
        and len(selected) == len(set(selected))
        and len(selected) <= 2
        and all(c in opts for c in selected)
    )
    if valid:
        cap = sum(int(opts[c]["capex_eur"]) for c in selected)
        fte = sum(int(opts[c]["fte"]) for c in selected)
        valid = (
            cap <= 450000
            and fte <= 7
            and recommendation.get("capex_eur") == cap
            and recommendation.get("fte") == fte
        )
    group("recommendation_feasibility", valid, "choice quality reviewed separately")
    group("quality_disclosure_present", bool(actual.get("quality")))
    files = [
        p
        for p in work.rglob("*")
        if p.is_file() and not any(n in p.parts for n in (".git", "node_modules", ".venv"))
    ]
    xlsx = [p for p in files if p.suffix == ".xlsx"]
    reports = [p for p in files if p.suffix in (".pdf", ".docx")]
    decks = [p for p in files if p.suffix in (".pptx", ".pdf")]
    group("xlsx_available", bool(xlsx))
    group("report_available", bool(reports))
    group("board_document_available", bool(decks) and len(set(reports + decks)) >= 2)
    archive_errors = []
    for p in files:
        if p.suffix in (".xlsx", ".pptx", ".docx"):
            try:
                with zipfile.ZipFile(p) as z:
                    if z.testzip():
                        archive_errors.append(str(p.relative_to(work)))
            except Exception:
                archive_errors.append(str(p.relative_to(work)))
    group("office_archives_open", not archive_errors, archive_errors)
    return finish(result)


def finish(result):
    result["passed"] = sum(g["pass_"] for g in result["groups"])
    result["total"] = len(result["groups"])
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("workspace", type=Path, nargs="?")
    p.add_argument("--expected", action="store_true")
    a = p.parse_args()
    print(json.dumps(expected() if a.expected else check(a.workspace), indent=2))

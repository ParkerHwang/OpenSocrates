"""Rebuild Meridian Parts calculations and deterministic exchange outputs."""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "evidence" / "source_room"
OUT = ROOT / "analysis" / "output"
DEL = ROOT / "deliverables"
CENT = Decimal("0.01")
ZERO = Decimal("0")
COUNTRIES = ["DEU", "FRA", "NLD", "POL", "CZE", "ESP"]
EURO = {"DEU", "FRA", "NLD", "ESP"}
CURRENCY = {"DEU": "EUR", "FRA": "EUR", "NLD": "EUR", "ESP": "EUR", "POL": "PLN", "CZE": "CZK"}
NAME = {"DEU": "Germany", "FRA": "France", "NLD": "Netherlands", "POL": "Poland", "CZE": "Czechia", "ESP": "Spain"}
SCENARIOS = {"low": Decimal("0.10"), "base": Decimal("0.25"), "high": Decimal("0.40")}
CUTOFF = date(2026, 1, 31)


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: json_scalar(v) for k, v in row.items()})


def json_scalar(v):
    if isinstance(v, Decimal):
        return float(v)
    if v is None:
        return ""
    if isinstance(v, (dict, list, tuple)):
        return json.dumps(v, default=lambda x: float(x) if isinstance(x, Decimal) else str(x), ensure_ascii=False)
    return v


def dec(v, default=None):
    if v is None or str(v).strip() == "":
        return default
    return Decimal(str(v).strip())


def as_int(v, default=None):
    x = dec(v, None)
    return default if x is None else int(x)


def money(v):
    return Decimal(v).quantize(CENT, rounding=ROUND_HALF_UP)


def fmt(v):
    return None if v is None else format(v, "f")


def parse_bool(v):
    if v is None or str(v).strip() == "":
        return None
    val = str(v).strip().lower()
    if val in {"true", "1", "yes", "y"}:
        return True
    if val in {"false", "0", "no", "n"}:
        return False
    return None


def clean_row(row):
    return {k: (v if v is not None else "") for k, v in row.items() if not k.startswith("_")}


def pick_revisions(rows, id_key, raw_count_name, anomalies):
    """Collapse exact duplicates, reject unresolved same-revision conflicts, select max revision."""
    if not rows:
        return [], {"raw_rows": 0, "identical_duplicates_removed": 0, "selected_ids": 0, "superseded_rows": 0}
    columns = [k for k in rows[0] if not k.startswith("_")]
    exact_seen = set()
    unique = []
    duplicate_count = 0
    for row in rows:
        key = tuple(row.get(k, "") for k in columns)
        if key in exact_seen:
            duplicate_count += 1
            continue
        exact_seen.add(key)
        unique.append(row)
    grouped = defaultdict(list)
    for row in unique:
        grouped[row[id_key]].append(row)
    selected = []
    superseded = 0
    conflicts = []
    for record_id, group in grouped.items():
        revs = [as_int(r.get("revision"), -1) for r in group]
        max_rev = max(revs)
        winners = [r for r, rev in zip(group, revs) if rev == max_rev]
        signatures = {tuple(r.get(k, "") for k in columns if k not in {id_key, "revision"}) for r in winners}
        if len(signatures) != 1:
            conflicts.append({"id": record_id, "revision": max_rev, "rows": [clean_row(r) for r in winners]})
        else:
            selected.append(winners[0])
        superseded += len(group) - len(winners)
    if conflicts:
        anomalies.append({
            "severity": "blocking",
            "issue": f"Conflicting rows at the maximum {id_key} revision",
            "count": len(conflicts),
            "handling": "No winner chosen; rebuild stops rather than silently selecting one.",
            "examples": conflicts[:10],
        })
        raise ValueError(f"Unresolved same-revision conflicts for {len(conflicts)} {id_key} values")
    return selected, {
        "raw_rows": len(rows),
        "identical_duplicates_removed": duplicate_count,
        "selected_ids": len(selected),
        "superseded_rows": superseded,
    }


def round_float(v, places=6):
    return round(float(v), places)


def list_to_json(rows):
    """Convert internal Decimal values for JSON while keeping monetary values as numeric EUR."""
    result = []
    for row in rows:
        item = {}
        for k, v in row.items():
            if isinstance(v, Decimal):
                item[k] = None if v.is_nan() else float(v)
            elif isinstance(v, (date, datetime)):
                item[k] = v.isoformat()
            else:
                item[k] = v
        result.append(item)
    return result


def get_order_cost(sku, shipped_date, costs):
    eligible = [r for r in costs if r["sku"] == sku and date.fromisoformat(r["valid_from"]) <= shipped_date]
    if not eligible:
        return None
    row = max(eligible, key=lambda x: x["valid_from"])
    return dec(row["unit_cost_eur"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    DEL.mkdir(parents=True, exist_ok=True)
    anomalies = []
    manifest = json.loads((SRC / "download_manifest.json").read_text())
    manifest_by_file = {r["file"]: r for r in manifest["files"]}
    source_meta = json.loads((SRC / "source-register.json").read_text())

    # Orders: all pages and correction file enter the same revision selection.
    order_rows = []
    for name in ["orders-part1.csv", "orders-part2.csv", "order-corrections.csv"]:
        for row in read_csv(SRC / name):
            row["_source"] = name
            order_rows.append(row)
    orders, order_revision_audit = pick_revisions(order_rows, "order_id", "order_rows", anomalies)

    # Returns are revised by return_id, then joined only through the exact order key.
    returns_in = read_csv(SRC / "returns.csv")
    returns, return_revision_audit = pick_revisions(returns_in, "return_id", "return_rows", anomalies)
    order_lookup = {r["order_id"]: r for r in orders}

    raw_costs = read_csv(SRC / "unit-costs.csv")
    unit_costs = [dict(r) for r in raw_costs]
    for c in unit_costs:
        c["unit_cost_eur"] = dec(c["unit_cost_eur"])
        c["valid_from"] = c["valid_from"]

    # ECB month means: arithmetic means over available business-day observations.
    ecb_rows = read_csv(SRC / "ecb-history.csv")
    fx = {}
    fx_counts = {}
    for currency in ["PLN", "CZK"]:
        for month_num in range(1, 13):
            month = f"2025-{month_num:02d}"
            observations = [dec(r[currency]) for r in ecb_rows if r["Date"].startswith(month) and dec(r.get(currency)) is not None]
            if not observations:
                anomalies.append({"severity": "blocking", "issue": "Missing monthly ECB observations", "currency": currency, "month": month, "handling": "No substitute rate applied."})
                raise ValueError(f"No ECB rate for {currency} {month}")
            fx[(currency, month)] = sum(observations, ZERO) / Decimal(len(observations))
            fx_counts[(currency, month)] = len(observations)

    # Return eligibility and aggregation by original order (currency/month come from sale).
    return_audit = Counter()
    order_return_qty = defaultdict(int)
    order_restock_qty = defaultdict(int)
    order_refund_local = defaultdict(lambda: ZERO)
    included_returns = []
    for ret in returns:
        received = date.fromisoformat(ret["received_at"]) if ret.get("received_at") else None
        if received is None:
            return_audit["missing_received_at"] += 1
            continue
        if received > CUTOFF:
            return_audit["after_cutoff"] += 1
            continue
        oid = ret.get("order_id", "")
        if oid not in order_lookup:
            return_audit["orphan_order_id"] += 1
            continue
        order = order_lookup[oid]
        shipped_date = date.fromisoformat(order["shipped_at"]) if order.get("shipped_at") else None
        is_eligible = (
            order.get("status", "").strip().lower() == "shipped"
            and parse_bool(order.get("is_test")) is False
            and shipped_date is not None
            and shipped_date.year == 2025
        )
        if not is_eligible:
            return_audit["linked_order_not_eligible_2025"] += 1
            continue
        qty = as_int(ret.get("quantity"))
        restocked = as_int(ret.get("restocked_quantity"))
        refund = dec(ret.get("refund_local"))
        if qty is None or restocked is None or refund is None:
            return_audit["missing_return_value"] += 1
            continue
        if qty < 0 or restocked < 0 or restocked > qty or refund < 0:
            anomalies.append({"severity": "blocking", "issue": "Invalid eligible return values", "return_id": ret.get("return_id"), "handling": "Quarantined from figures pending client resolution."})
            return_audit["invalid_eligible_return"] += 1
            continue
        included_returns.append(ret)
        order_return_qty[oid] += qty
        order_restock_qty[oid] += restocked
        order_refund_local[oid] += refund
        return_audit["included_return_ids"] += 1
        return_audit["included_returned_units"] += qty
    for oid, qty in order_return_qty.items():
        order = order_lookup[oid]
        sold = as_int(order.get("quantity"))
        if sold is not None and qty > sold:
            anomalies.append({"severity": "review", "issue": "Cumulative returned units exceed sold units", "order_id": oid, "sold_units": sold, "returned_units": qty, "handling": "Included as recorded pending operational validation."})
    for oid, qty in order_restock_qty.items():
        sold = as_int(order_lookup[oid].get("quantity"))
        if sold is not None and qty > sold:
            anomalies.append({"severity": "blocking", "issue": "Cumulative restocked units exceed sold units", "order_id": oid, "sold_units": sold, "restocked_units": qty, "handling": "No COGS recovery beyond reported restocked quantity was accepted; source requires client correction."})
            raise ValueError(f"Restocked quantity exceeds sold units for {oid}")

    eligible_orders = []
    exclusions = Counter()
    order_exclusions = []
    missing_counts = Counter()
    for order in orders:
        oid = order.get("order_id", "")
        status = order.get("status", "").strip().lower()
        test = parse_bool(order.get("is_test"))
        shipped = date.fromisoformat(order["shipped_at"]) if order.get("shipped_at") else None
        if status != "shipped":
            reason = "status_not_shipped"
        elif test is not False:
            reason = "test_flag_true" if test is True else "missing_or_invalid_test_flag"
        elif shipped is None:
            reason = "missing_shipped_at"
        elif shipped.year != 2025:
            reason = "shipped_outside_2025"
        else:
            reason = None
        if reason:
            exclusions[reason] += 1
            order_exclusions.append({"order_id": oid, "revision": order.get("revision"), "reason": reason, "status": status, "is_test": test, "shipped_at": order.get("shipped_at")})
            continue
        required = ["country", "sku", "quantity", "unit_price_local", "discount_local", "currency", "fulfillment_eur"]
        missing = [k for k in required if order.get(k) is None or str(order.get(k)).strip() == ""]
        if missing:
            for k in missing:
                missing_counts[k] += 1
            exclusions["missing_calculation_field"] += 1
            order_exclusions.append({"order_id": oid, "revision": order.get("revision"), "reason": "missing_calculation_field", "fields": ";".join(missing)})
            continue
        if order["country"] not in COUNTRIES:
            exclusions["country_outside_scope"] += 1
            order_exclusions.append({"order_id": oid, "revision": order.get("revision"), "reason": "country_outside_scope"})
            continue
        if order["currency"] != CURRENCY[order["country"]]:
            anomalies.append({"severity": "blocking", "issue": "Country/currency mismatch", "order_id": oid, "country": order["country"], "currency": order["currency"], "expected_currency": CURRENCY[order["country"]], "handling": "Excluded; no inferred currency used."})
            exclusions["country_currency_mismatch"] += 1
            order_exclusions.append({"order_id": oid, "revision": order.get("revision"), "reason": "country_currency_mismatch"})
            continue
        qty = as_int(order.get("quantity"))
        unit_price = dec(order.get("unit_price_local"))
        discount = dec(order.get("discount_local"))
        fulfillment = dec(order.get("fulfillment_eur"))
        if qty is None or qty < 0 or unit_price is None or discount is None or fulfillment is None or unit_price < 0 or discount < 0 or fulfillment < 0:
            anomalies.append({"severity": "blocking", "issue": "Invalid eligible order calculation value", "order_id": oid, "handling": "Excluded pending client correction."})
            exclusions["invalid_calculation_value"] += 1
            order_exclusions.append({"order_id": oid, "revision": order.get("revision"), "reason": "invalid_calculation_value"})
            continue
        unit_cost = get_order_cost(order["sku"], shipped, unit_costs)
        if unit_cost is None:
            anomalies.append({"severity": "blocking", "issue": "No effective unit-cost row for eligible order", "order_id": oid, "sku": order["sku"], "shipped_at": shipped.isoformat(), "handling": "Excluded pending cost source."})
            exclusions["missing_unit_cost"] += 1
            order_exclusions.append({"order_id": oid, "revision": order.get("revision"), "reason": "missing_unit_cost"})
            continue
        eligible_orders.append({"raw": order, "id": oid, "country": order["country"], "month": shipped.strftime("%Y-%m"), "date": shipped, "sku": order["sku"], "quantity": qty, "currency": order["currency"], "unit_price_local": unit_price, "discount_local": discount, "fulfillment_eur_raw": fulfillment, "unit_cost_eur": unit_cost})

    # Component rounding occurs per order; sum refund credit values by order first.
    order_components = []
    metrics_fields = ["shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units"]
    monthly_vals = defaultdict(lambda: {k: 0 if k in {"shipped_orders", "shipped_units", "returned_units"} else ZERO for k in metrics_fields})
    country_vals = defaultdict(lambda: {k: 0 if k in {"shipped_orders", "shipped_units", "returned_units"} else ZERO for k in metrics_fields})
    for o in eligible_orders:
        rate = Decimal("1") if o["currency"] == "EUR" else fx[(o["currency"], o["month"])]
        gross_local = o["quantity"] * o["unit_price_local"] - o["discount_local"]
        gross_eur = money(gross_local / rate)
        refund_eur = money(order_refund_local[o["id"]] / rate)
        gross_cogs_eur = money(Decimal(o["quantity"]) * o["unit_cost_eur"])
        recovered_cogs_eur = money(Decimal(order_restock_qty[o["id"]]) * o["unit_cost_eur"])
        net_cogs_eur = gross_cogs_eur - recovered_cogs_eur
        fulfillment_eur = money(o["fulfillment_eur_raw"])
        net_sales_eur = gross_eur - refund_eur
        contribution_eur = net_sales_eur - net_cogs_eur - fulfillment_eur
        comp = {
            "order_id": o["id"], "order_revision": int(o["raw"]["revision"]), "country": o["country"], "shipped_at": o["date"].isoformat(), "month": o["month"], "sku": o["sku"], "currency": o["currency"],
            "fx_local_per_eur": rate, "quantity": o["quantity"], "unit_cost_eur": o["unit_cost_eur"],
            "unit_price_local": o["unit_price_local"], "discount_local": o["discount_local"], "fulfillment_eur_raw": o["fulfillment_eur_raw"],
            "gross_local": gross_local, "refund_local": order_refund_local[o["id"]],
            "gross_sales_eur": gross_eur, "refunds_eur": refund_eur,
            "gross_cogs_eur": gross_cogs_eur, "recovered_cogs_eur": recovered_cogs_eur,
            "net_cogs_eur": net_cogs_eur, "fulfillment_eur": fulfillment_eur,
            "net_sales_eur": net_sales_eur, "contribution_eur": contribution_eur,
            "returned_units": order_return_qty[o["id"]], "restocked_units": order_restock_qty[o["id"]],
        }
        order_components.append(comp)
        for bucket in (monthly_vals[(o["country"], o["month"])], country_vals[o["country"]]):
            bucket["shipped_orders"] += 1
            bucket["shipped_units"] += o["quantity"]
            bucket["gross_sales_eur"] += gross_eur
            bucket["refunds_eur"] += refund_eur
            bucket["net_sales_eur"] += net_sales_eur
            bucket["net_cogs_eur"] += net_cogs_eur
            bucket["fulfillment_eur"] += fulfillment_eur
            bucket["contribution_eur"] += contribution_eur
            bucket["returned_units"] += order_return_qty[o["id"]]

    monthly = []
    for country in COUNTRIES:
        for m in range(1, 13):
            month = f"2025-{m:02d}"
            vals = monthly_vals[(country, month)]
            row = {"country": country, "month": month, **vals}
            row["margin"] = None if vals["net_sales_eur"] == ZERO else float(vals["contribution_eur"] / vals["net_sales_eur"])
            monthly.append(row)
    countries = []
    for country in COUNTRIES:
        vals = country_vals[country]
        row = {"country": country, **vals}
        row["margin"] = None if vals["net_sales_eur"] == ZERO else float(vals["contribution_eur"] / vals["net_sales_eur"])
        countries.append(row)
    for country in COUNTRIES:
        for field in metrics_fields:
            msum = sum((r[field] for r in monthly if r["country"] == country), 0 if field in {"shipped_orders", "shipped_units", "returned_units"} else ZERO)
            if msum != country_vals[country][field]:
                anomalies.append({"severity": "blocking", "issue": "Monthly-to-country reconciliation failure", "country": country, "field": field, "monthly_sum": fmt(msum), "country_total": fmt(country_vals[country][field])})
                raise AssertionError(f"Reconciliation failure {country} {field}")

    # World Bank archived official snapshots; retain all years and nulls.
    pop_json = json.loads((SRC / "population.json").read_text())
    gdp_json = json.loads((SRC / "gdp-per-capita.json").read_text())
    def wb_rows(blob):
        return {(r["countryiso3code"], int(r["date"])): r["value"] for r in blob[1]}
    pops = wb_rows(pop_json)
    gdps = wb_rows(gdp_json)
    market_context = []
    for country in COUNTRIES:
        for year in [2022, 2023, 2024]:
            pop = pops.get((country, year))
            gdp = gdps.get((country, year))
            market_context.append({"country": country, "year": year, "population": pop, "gdp_per_capita_usd": gdp})
    pop_change = {}
    for country in COUNTRIES:
        p22, p24 = pops.get((country, 2022)), pops.get((country, 2024))
        pop_change[country] = None if p22 is None or p24 is None or p22 == 0 else (p24 / p22 - 1) * 100

    # Option formula exactly follows the supplied policy; pair arithmetic is additive.
    option_rows = read_csv(SRC / "hub-options.csv")
    options = {r["country"]: {"country": r["country"], "capex_eur": int(r["capex_eur"]), "fte": int(r["fte"]), "annual_fixed_eur": dec(r["annual_fixed_eur"]), "saving_eur_per_unit": dec(r["saving_eur_per_unit"])} for r in option_rows}
    country_by_id = {r["country"]: r for r in countries}
    hub_scenarios = []
    metrics_lookup = {}
    for country in COUNTRIES:
        base = country_by_id[country]
        C = base["contribution_eur"]
        U = Decimal(base["shipped_units"])
        G = base["gross_sales_eur"]
        N = base["net_sales_eur"]
        opt = options[country]
        stress_c = C - Decimal("0.03") * G - (Decimal("0.10") * N if CURRENCY[country] in {"PLN", "CZK"} else ZERO)
        for scenario, uplift in list(SCENARIOS.items()) + [("stress", Decimal("0.25"))]:
            if scenario == "stress":
                incremental = stress_c * Decimal("1.25") - C + U * Decimal("1.25") * opt["saving_eur_per_unit"] - opt["annual_fixed_eur"]
            else:
                incremental = C * uplift + U * (Decimal("1") + uplift) * opt["saving_eur_per_unit"] - opt["annual_fixed_eur"]
            incremental = money(incremental)
            payback = None if incremental <= 0 else Decimal(opt["capex_eur"]) / incremental
            row = {"country": country, "scenario": scenario, "incremental_contribution_eur": incremental, "capex_eur": opt["capex_eur"], "annual_fixed_eur": opt["annual_fixed_eur"], "saving_eur_per_unit": opt["saving_eur_per_unit"], "fte": opt["fte"], "payback_years": payback}
            hub_scenarios.append(row)
            metrics_lookup[(country, scenario)] = row

    single_alternatives = []
    for country in COUNTRIES:
        opt = options[country]
        single_alternatives.append({"label": NAME[country], "countries": [country], "feasible": True, "capex_eur": opt["capex_eur"], "annual_fixed_eur": opt["annual_fixed_eur"], "fte": opt["fte"], "scenarios": {s: metrics_lookup[(country, s)]["incremental_contribution_eur"] for s in ["low", "base", "high", "stress"]}, "paybacks": {s: metrics_lookup[(country, s)]["payback_years"] for s in ["low", "base", "high", "stress"]}})
    pair_scenarios = []
    all_pairs = []
    for a, b in itertools.combinations(COUNTRIES, 2):
        cs = [a, b]
        capex = sum(options[c]["capex_eur"] for c in cs)
        fte = sum(options[c]["fte"] for c in cs)
        feasible = capex <= 450000 and fte <= 7
        reasons = []
        if capex > 450000:
            reasons.append("capex_budget")
        if fte > 7:
            reasons.append("fte_limit")
        record = {"label": f"{a}+{b}", "countries": cs, "feasible": feasible, "capex_eur": capex, "fte": fte, "infeasible_reasons": reasons}
        for scenario in ["low", "base", "high", "stress"]:
            total = sum((metrics_lookup[(c, scenario)]["incremental_contribution_eur"] for c in cs), ZERO)
            payback = None if total <= 0 else Decimal(capex) / total
            record[scenario] = {"incremental_contribution_eur": money(total), "payback_years": payback}
            if feasible:
                pair_scenarios.append({"countries": cs, "scenario": scenario, "incremental_contribution_eur": money(total), "capex_eur": capex, "annual_fixed_eur": sum((options[c]["annual_fixed_eur"] for c in cs), ZERO), "fte": fte, "payback_years": payback})
        all_pairs.append(record)

    feasible_alternatives = [
        {"label": x["label"], "countries": x["countries"], "capex_eur": x["capex_eur"], "annual_fixed_eur": x["annual_fixed_eur"], "fte": x["fte"], **x["scenarios"], "base_payback_years": x["paybacks"]["base"]}
        for x in single_alternatives
    ]
    for pair in all_pairs:
        if pair["feasible"]:
            feasible_alternatives.append({"label": pair["label"], "countries": pair["countries"], "capex_eur": pair["capex_eur"], "annual_fixed_eur": sum((options[c]["annual_fixed_eur"] for c in pair["countries"]), ZERO), "fte": pair["fte"], **{s: pair[s]["incremental_contribution_eur"] for s in ["low", "base", "high", "stress"]}, "base_payback_years": pair["base"]["payback_years"]})
    feasible_alternatives.append({"label": "Defer", "countries": [], "capex_eur": 0, "annual_fixed_eur": ZERO, "fte": 0, "low": ZERO, "base": ZERO, "high": ZERO, "stress": ZERO, "base_payback_years": None})
    feasible_alternatives.sort(key=lambda x: (x["base"], x["low"], -x["capex_eur"]), reverse=True)
    best_base = feasible_alternatives[0]
    best_robust = max(feasible_alternatives, key=lambda x: (min(x["low"], x["base"], x["high"], x["stress"]), x["base"]))
    runner_up = feasible_alternatives[1] if len(feasible_alternatives) > 1 else None

    # Sensitivity outputs preserve the client scenario range and expose decision thresholds.
    # This linear extension below the policy's 10% low case is labelled as model extrapolation.
    coefficients = {}
    for alt in feasible_alternatives:
        a, b0 = ZERO, ZERO
        for country in alt["countries"]:
            baseline = country_by_id[country]
            option = options[country]
            saving_volume = Decimal(baseline["shipped_units"]) * option["saving_eur_per_unit"]
            a += baseline["contribution_eur"] + saving_volume
            b0 += saving_volume - option["annual_fixed_eur"]
        coefficients[alt["label"]] = (a, b0)

    def winner_at_u(u):
        evaluated = []
        for alt in feasible_alternatives:
            value = ZERO
            for country in alt["countries"]:
                baseline = country_by_id[country]
                option = options[country]
                value += money(baseline["contribution_eur"] * u + Decimal(baseline["shipped_units"]) * (Decimal("1") + u) * option["saving_eur_per_unit"] - option["annual_fixed_eur"])
            evaluated.append((value, alt["label"]))
        return max(evaluated)[1]

    roots = set()
    for left, right in itertools.combinations(coefficients.items(), 2):
        (a1, b1), (a2, b2) = left[1], right[1]
        if a1 != a2:
            root = (b2 - b1) / (a1 - a2)
            if ZERO < root < Decimal("0.40"):
                roots.add(root)
    volume_switches = []
    epsilon = Decimal("0.000001")
    for root in sorted(roots):
        before = winner_at_u(max(ZERO, root - epsilon))
        after = winner_at_u(root + epsilon)
        if before != after:
            volume_switches.append({"uplift_pct": root * Decimal("100"), "from": before, "to": after, "provenance": "computed from the linear policy formula holding shipment baseline, savings, fixed cost, FX, refunds, capex and staffing at supplied point assumptions; values below 10% extend outside the policy's tested low case"})

    point_winners = []
    for scenario, uplift in SCENARIOS.items():
        option = max(feasible_alternatives, key=lambda x: x[scenario])
        point_winners.append({"scenario": scenario, "volume_uplift_pct": uplift * Decimal("100"), "winner": option["label"], "incremental_contribution_eur": option[scenario]})
    stress_winner = max((r for r in feasible_alternatives if r["countries"]), key=lambda x: x["stress"])
    assumed_stress_floor = Decimal("50000")
    floor_qualified = [r for r in feasible_alternatives if r["countries"] and r["stress"] >= assumed_stress_floor]
    floor_winner = max(floor_qualified, key=lambda x: x["base"])
    selected_stress = next(r["stress"] for r in feasible_alternatives if r["label"] == best_base["label"])
    sensitivity_analysis = {
        "status": "provisional",
        "baseline": {
            "primary_metric": "annual incremental contribution after recurring hub fixed cost (EUR)",
            "decision_rule": "Highest base-case contribution among feasible individual/pair options and defer; capex and staffing ceilings remain hard constraints; pair synergies assumed zero.",
            "winner": best_base["label"],
            "volume_uplift_pct": Decimal("25"),
            "incremental_contribution_eur": best_base["base"],
            "capex_eur": best_base["capex_eur"],
            "annual_fixed_eur": best_base["annual_fixed_eur"],
            "fte": best_base["fte"],
            "base_payback_years": best_base["base_payback_years"],
        },
        "tested_ranges": [
            {"input": "volume_uplift", "low_pct": Decimal("10"), "base_pct": Decimal("25"), "high_pct": Decimal("40"), "status": "assumed client scenarios; not measured or probabilistic", "provenance": "scenario-policy.md"},
            {"input": "joint_return_fx_stress", "volume_uplift_pct": Decimal("25"), "additional_refunds_pct_of_gross_sales": Decimal("3"), "PLN_CZK_net_sales_depreciation_pct": Decimal("10"), "status": "assumed client-defined structured joint stress; not a forecast probability", "provenance": "scenario-policy.md"},
            {"input": "minimum_stress_floor_eur", "illustrative_threshold_eur": assumed_stress_floor, "status": "analyst illustration only; no board threshold supplied", "provenance": "explicitly hypothetical decision preference"},
            {"input": "saving_per_unit_fixed_cost_capex", "range": None, "status": "not perturbed; synthetic source supplies point assumptions only, so no defensible range was available"},
        ],
        "perturbation_results": [
            {"variation": f"{r['scenario']} volume case", "tested_uplift_pct": r["volume_uplift_pct"], "winner": r["winner"], "annual_incremental_contribution_eur": r["incremental_contribution_eur"], "status": "computed from client scenario formula"}
            for r in point_winners
        ] + [
            {"variation": "defined joint return/FX stress", "tested_uplift_pct": Decimal("25"), "winner_by_stress_contribution": stress_winner["label"], "stress_incremental_contribution_eur": stress_winner["stress"], "CZE_ESP_stress_eur": next(r["stress"] for r in feasible_alternatives if r["label"] == "CZE+ESP"), "status": "computed joint stress; no probability assigned"},
            {"variation": "illustrative EUR50k stress floor, otherwise rank by base", "threshold_eur": assumed_stress_floor, "winner": floor_winner["label"], "annual_incremental_contribution_eur": floor_winner["base"], "status": "computed conditional result; preference threshold is hypothetical"},
        ],
        "switching_values": volume_switches + [
            {"input": "minimum acceptable stress contribution", "switch_above_eur": selected_stress, "switch_to": floor_winner["label"], "highest_qualifying_stress_eur": floor_winner["stress"], "status": "computed for a hard floor; when the floor exceeds the CZE+ESP stress result and is no higher than NLD+ESP stress, NLD+ESP leads among funded options"},
        ],
        "robust_or_fragile_conclusion": "CZE+ESP remains the highest-base feasible option at the specified 10%, 25% and 40% volume points, with positive low and defined-stress results. The recommendation is conditional on choosing base contribution as the primary objective: a stress floor above EUR32,179.71 changes it to NLD+ESP up to that pair's EUR107,630.13 stress ceiling. Volume breakpoints below 10% are linear-model extrapolations, not source-backed demand estimates.",
        "research_priority": [
            "Validate actual order volume and order/return joins using real operational exports before any lease or hiring commitment.",
            "Measure hub-attributable order uplift and fulfillment savings against a central-hub baseline; the 10%/25%/40% uplifts and per-unit savings are assumptions.",
            "Obtain defensible ranges for local fixed cost, labor, site capex and per-unit savings; these point inputs were not varied.",
            "Measure refund values, restocked recovery and FX exposure; the joint stress is a policy scenario, not an empirical distribution.",
        ],
        "flip_condition": f"If measured volume uplift falls below approximately {volume_switches[0]['uplift_pct']:.2f}% with other supplied point assumptions held fixed, defer becomes the highest-contribution option; between approximately {volume_switches[0]['uplift_pct']:.2f}% and {volume_switches[1]['uplift_pct']:.2f}%, a Czechia-only option leads, and above that the CZE+ESP pair leads. If the board instead requires a minimum stress contribution above {selected_stress:.2f} EUR and no higher than {floor_winner['stress']:.2f} EUR, select NLD+ESP; this floor is an illustrative preference, not a client rule.",
    }

    # Single-option scenario arithmetic depends on uncaptured hub causality and uplift assumptions.
    recommendation = {
        "countries": best_base["countries"],
        "capex_eur": best_base["capex_eur"],
        "fte": best_base["fte"],
        "rationale": (
            f"On the client-specified 25% volume-uplift case and additive/no-synergy option arithmetic, {best_base['label']} "
            f"has the highest feasible annual incremental contribution ({fmt(best_base['base'])} EUR) after recurring fixed cost. "
            f"The next-best feasible alternative is {runner_up['label'] if runner_up else 'none'} ({fmt(runner_up['base']) if runner_up else 'n/a'} EUR). "
            "This is conditional scenario arithmetic, not measured causal hub benefit; authorize only staged spend against the 90-day gates."
        ),
        "basis": "computed from synthetic client shipments and client-assumed savings, fixed cost, capex, staffing and uplift; no hub pilot or causal evidence",
        "base_incremental_contribution_eur": best_base["base"],
        "low_incremental_contribution_eur": best_base["low"],
        "high_incremental_contribution_eur": best_base["high"],
        "stress_incremental_contribution_eur": best_base["stress"],
        "strongest_alternative": runner_up,
        "robust_floor_alternative": best_robust["label"],
        "flip_condition": sensitivity_analysis["flip_condition"],
    }

    # Audit counts and explicit quality register.
    order_states = Counter()
    for r in orders:
        status = r.get("status", "").strip().lower()
        test = parse_bool(r.get("is_test"))
        shipped = date.fromisoformat(r["shipped_at"]) if r.get("shipped_at") else None
        if status == "shipped" and test is False and shipped and shipped.year == 2025:
            order_states["eligible_shipped_2025_before_value_validation"] += 1
        if shipped and shipped.year == 2026:
            order_states["shipped_in_2026_excluded"] += 1
        if status in {"cancelled", "canceled"}:
            order_states["cancelled"] += 1
        if test is True:
            order_states["test_flag_true"] += 1
        if status not in {"shipped", "cancelled", "canceled"}:
            order_states["other_status"] += 1
    return_audit["latest_return_ids"] = len(returns)
    return_audit["superseded_rows"] = return_revision_audit["superseded_rows"]
    return_audit["identical_duplicates_removed"] = return_revision_audit["identical_duplicates_removed"]

    def handled(issue, count, handling, severity="handled"):
        if count:
            anomalies.append({"severity": severity, "issue": issue, "count": count, "handling": handling})

    handled("Exact repeated order rows across extracts/corrections", order_revision_audit["identical_duplicates_removed"], "Collapsed as one record before order_id revision selection.")
    handled("Lower order revisions superseded", order_revision_audit["superseded_rows"], "Highest numeric revision selected; the later row replaced the whole earlier row.")
    handled("Cancelled or non-shipped orders", exclusions.get("status_not_shipped", 0), "Excluded from 2025 shipped revenue and units.")
    handled("Test orders", exclusions.get("test_flag_true", 0), "Excluded from 2025 shipped revenue and units.")
    handled("Orders shipped outside 2025", exclusions.get("shipped_outside_2025", 0), "Excluded from the 2025 base, including 2026-01 shipments.")
    handled("Zero-price/free shipments", sum(1 for o in eligible_orders if o["quantity"] * o["unit_price_local"] - o["discount_local"] == ZERO), "Included as valid shipped orders and units; zero sales value retained.")
    handled("Exact repeated return rows", return_revision_audit["identical_duplicates_removed"], "Collapsed by exact row equality before return_id revision selection.")
    handled("Lower return revisions superseded", return_revision_audit["superseded_rows"], "Highest numeric revision selected per return_id.")
    handled("Returns received after inclusive cutoff", return_audit["after_cutoff"], "Excluded because received_at is later than 2026-01-31.")
    handled("Orphan returns", return_audit["orphan_order_id"], "Quarantined; no approximate or guessed order match was made.", "review")

    quality = {
        "cutoff_inclusive": CUTOFF.isoformat(),
        "order_revision_audit": order_revision_audit,
        "order_eligibility_counts": dict(order_states),
        "order_exclusions": dict(exclusions),
        "order_missing_value_counts_among_eligible_candidates": dict(missing_counts),
        "selected_orders_calculated": len(eligible_orders),
        "return_revision_audit": return_revision_audit,
        "returns_handling_counts": dict(return_audit),
        "unit_cost_effective_date_rule": "latest valid_from on or before original shipped_at; local file rows preserved",
        "included_valid_zero_price_shipments": sum(1 for o in eligible_orders if o["quantity"] * o["unit_price_local"] - o["discount_local"] == ZERO),
        "exact_order_revision_conflicts": 0,
        "monthly_country_reconciliation": "passed for counts and all monetary totals in every country",
        "anomalies": anomalies,
        "limitations": [
            "Client transaction, return, cost, hub, savings, fixed-cost and volume-uplift inputs are synthetic, not observed customer or operations evidence.",
            "ECB reference rates are archived analytical translations, not actual settlement rates; same original-sale-month rate is used for gross and refunds.",
            "Returns are only those received by 2026-01-31; later claims can revise the 2025 view.",
            "Hub scenario output is a simple annual contribution comparison without causal validation, synergy, tax, discounting, working capital, or terminal value.",
            "World Bank historical archive vintage is 2026-07-13 last updated and may include revisions made after the reference years."
        ]
    }

    fx_monthly = [{"currency": curr, "month": f"2025-{m:02d}", "local_per_eur": fx[(curr, f"2025-{m:02d}")]} for curr in ["PLN", "CZK"] for m in range(1, 13)]
    results = {
        "monthly": monthly,
        "countries": countries,
        "fx_monthly": fx_monthly,
        "market_context": market_context,
        "hub_scenarios": hub_scenarios,
        "recommendation": recommendation,
        "quality": quality,
        "sensitivity_analysis": sensitivity_analysis,
        "combination_scenarios": pair_scenarios,
        "all_pairs": all_pairs,
        "option_comparison": feasible_alternatives,
        "country_population_change_2022_2024_pct": pop_change,
        "market_context_metadata": {
            "population_unit": "persons",
            "gdp_per_capita_unit": "current US dollars per person (not PPP or constant-price)",
            "years": [2022, 2023, 2024],
            "world_bank_lastupdated": pop_json[0].get("lastupdated"),
            "population_url": source_meta["public"][0]["original_url"],
            "gdp_url": source_meta["public"][1]["original_url"],
        },
        "fx_metadata": {"units": "local currency units per EUR; ECB reference-rate quote as published", "mean": "arithmetic mean of available published business-day values in each 2025 calendar month", "observation_counts": {f"{cur}:{mon}": cnt for (cur, mon), cnt in fx_counts.items()}},
        "accounting_metadata": {
            "sales_window": "shipped_at during 2025",
            "return_cutoff_inclusive": CUTOFF.isoformat(),
            "gross_sales_definition": "quantity × local unit price − local discount, translated and rounded per order",
            "refunds_definition": "included explicit refund amounts summed per order, translated at original sale-month rate and rounded per order",
            "net_cogs_definition": "per-order gross COGS minus cost recovered for physically restocked units",
            "contribution_definition": "gross sales − refunds − net COGS − nonrefundable fulfillment; hub fixed costs excluded from historical contribution",
            "rounding": "individual EUR monetary components per order to cents using ROUND_HALF_UP before aggregation",
            "margin": "contribution / net sales; null when net sales is zero",
        }
    }

    # JSON uses numerical EUR and explicit null margins/paybacks.
    json_results = {
        "monthly": list_to_json(monthly),
        "countries": list_to_json(countries),
        "fx_monthly": list_to_json(fx_monthly),
        "market_context": market_context,
        "hub_scenarios": list_to_json(hub_scenarios),
        "combination_scenarios": list_to_json(pair_scenarios),
        "recommendation": list_to_json([recommendation])[0],
        "sensitivity_analysis": sensitivity_analysis,
        "option_comparison": list_to_json(feasible_alternatives),
        "country_population_change_2022_2024_pct": pop_change,
        "market_context_metadata": results["market_context_metadata"],
        "fx_metadata": results["fx_metadata"],
        "accounting_metadata": results["accounting_metadata"],
        "quality": quality,
    }
    (DEL / "metrics.json").write_text(json.dumps(json_results, indent=2, ensure_ascii=False, allow_nan=False, default=lambda x: float(x) if isinstance(x, Decimal) else str(x)) + "\n")
    write_csv(OUT / "monthly.csv", monthly)
    write_csv(OUT / "countries.csv", countries)
    write_csv(OUT / "fx_monthly.csv", fx_monthly)
    write_csv(OUT / "market_context.csv", market_context)
    write_csv(OUT / "order_components.csv", order_components)
    write_csv(OUT / "order_exclusions.csv", order_exclusions)
    write_csv(OUT / "hub_scenarios.csv", hub_scenarios)
    write_csv(OUT / "combination_scenarios.csv", pair_scenarios)
    write_csv(OUT / "all_pairs.csv", all_pairs)
    write_csv(OUT / "option_comparison.csv", feasible_alternatives)
    write_csv(OUT / "sensitivity_ranges.csv", sensitivity_analysis["tested_ranges"])
    write_csv(OUT / "sensitivity_perturbations.csv", sensitivity_analysis["perturbation_results"])
    write_csv(OUT / "sensitivity_switching_values.csv", sensitivity_analysis["switching_values"])

    # Source register: room collection provenance plus the curator's official URLs/vintage.
    public_meta = {Path(x["file"]).name: x for x in source_meta.get("public", [])}
    descriptions = {
        "data-dictionary.md": ("Client accounting and grain rules", "N/A", "2025 sales; returns through 2026-01-31", "synthetic client instructions"),
        "scenario-policy.md": ("Hub option scenario formulas and constraints", "EUR, units, %, FTE", "annual scenarios applied to 2025 baseline", "synthetic client assumptions"),
        "orders-part1.csv": ("Order extract page 1", "local currency, units, EUR fulfillment", "orders dated in extract; filter shipped 2025", "synthetic client export"),
        "orders-part2.csv": ("Order extract page 2", "local currency, units, EUR fulfillment", "orders dated in extract; filter shipped 2025", "synthetic client export"),
        "order-corrections.csv": ("Order corrections; highest numeric revision replaces whole prior row", "local currency, units, EUR fulfillment", "orders dated in extract; filter shipped 2025", "synthetic client correction file"),
        "returns.csv": ("Return ledger; highest numeric revision per return_id", "local currency, units", "received through 2026-01-31 inclusive", "synthetic client export"),
        "unit-costs.csv": ("Effective-dated unit cost by SKU", "EUR per unit", "valid_from dates in file", "synthetic client assumptions"),
        "hub-options.csv": ("Per-country hub capex, staffing, annual fixed cost and unit savings", "EUR, FTE, EUR per unit", "annual", "synthetic client assumptions"),
        "population.json": ("World Bank population, total (SP.POP.TOTL)", "persons", "2022-2024", "official public snapshot"),
        "gdp-per-capita.json": ("World Bank GDP per capita (current US$) (NY.GDP.PCAP.CD)", "current US$ per person", "2022-2024", "official public snapshot"),
        "ecb-history.zip": ("ECB euro foreign exchange reference rates historical archive", "local currency units per EUR", "archive through 2026-09-25; calculations use 2025", "official public snapshot"),
        "ecb-history.csv": ("Lossless extraction of ECB historical ZIP", "local currency units per EUR", "archive through 2026-09-25; calculations use 2025", "official public snapshot, derived from ZIP"),
        "source-register.json": ("Curator register of original public source URLs, archive retrieval vintage and seed note", "metadata", "archive collected 2026-09-27", "source-room provenance metadata"),
    }
    register = []
    for fname in ["index.html"] + [r["file"] for r in manifest["files"]]:
        disk_path = SRC / fname
        entry = manifest_by_file.get(fname)
        if fname == "index.html":
            data = disk_path.read_bytes()
            retrieved = manifest["index_retrieved_utc"]
            source_url = manifest["index_url"]
            digest = hashlib.sha256(data).hexdigest()
            size = len(data)
        else:
            retrieved, source_url, digest, size = entry["retrieved_utc"], entry["source_url"], entry["sha256"], entry["bytes"]
        desc, units, period, status = descriptions.get(fname, ("Source-room file", "as documented in source", "as supplied", "synthetic client input"))
        pm = public_meta.get(fname, {})
        archive_pm = pm
        if not pm.get("retrieved_utc") and pm.get("derived_from"):
            archive_pm = public_meta.get(pm.get("derived_from"), pm)
        register.append({
            "file": fname,
            "description": desc,
            "source_room_url": source_url,
            "original_source_url": pm.get("original_url", public_meta.get(pm.get("derived_from", ""), {}).get("original_url", "")),
            "retrieved_from_room_utc": retrieved,
            "original_archive_retrieved_utc": archive_pm.get("retrieved_utc", ""),
            "sha256": digest,
            "bytes": size,
            "units": units,
            "period": period,
            "status": status,
            "revision_vintage": source_meta.get("vintage_note", "") if fname in {"population.json", "gdp-per-capita.json"} else ("ECB archive snapshot retrieved 2026-09-27; latest series observations include later dates; 2025 values are archival actuals" if fname.startswith("ecb-history") else ""),
        })
    (DEL / "source_register.json").write_text(json.dumps(register, indent=2, ensure_ascii=False) + "\n")
    write_csv(DEL / "source_register.csv", register)
    (OUT / "quality.json").write_text(json.dumps(quality, indent=2, ensure_ascii=False) + "\n")

    # Compact build log for transparent review.
    print("Orders selected/reconciled:", len(orders), "final order_ids from", len(order_rows), "raw rows;", order_revision_audit)
    print("Returns selected:", len(returns), "; handling:", dict(return_audit))
    print("Included eligible shipments:", len(eligible_orders), "; exclusions:", dict(exclusions))
    print("Countries:")
    for r in countries:
        print(r["country"], "orders", r["shipped_orders"], "units", r["shipped_units"], "gross", fmt(r["gross_sales_eur"]), "refunds", fmt(r["refunds_eur"]), "net", fmt(r["net_sales_eur"]), "contribution", fmt(r["contribution_eur"]), "margin", r["margin"])
    print("Best base alternative:", best_base["label"], fmt(best_base["base"]), "EUR; capex", best_base["capex_eur"], "FTE", best_base["fte"])
    print("Recommendation robust floor:", best_robust["label"])
    print("Feasible pair count:", sum(1 for p in all_pairs if p["feasible"]), "of", len(all_pairs))


if __name__ == "__main__":
    main()

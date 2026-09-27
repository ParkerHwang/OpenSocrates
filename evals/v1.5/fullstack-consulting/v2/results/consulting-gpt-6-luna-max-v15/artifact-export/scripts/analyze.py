"""Reproduce Meridian's 2025 shipment, return, FX and hub scenarios.

Inputs are the frozen files in evidence/source_room. Monetary conversion uses
Decimal and ROUND_HALF_UP at the order-component boundary required by the brief.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from itertools import combinations
from pathlib import Path
import csv
import hashlib
import json
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "evidence" / "source_room"
OUT = ROOT / "analysis"
DELIVER = ROOT / "deliverables"
COUNTRIES = ["DEU", "FRA", "NLD", "POL", "CZE", "ESP"]
FX_CODES = ["PLN", "CZK"]
SCENARIOS = {"low": Decimal("0.10"), "base": Decimal("0.25"), "high": Decimal("0.40")}
CUTOFF = date(2026, 1, 31)
CENT = Decimal("0.01")


def money(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def cents(value):
    return int((money(value) * 100).to_integral_exact())


def eur(cents_value):
    return round(cents_value / 100, 2)


def number(value):
    if value in (None, ""):
        return None
    return float(value)


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def stable_unique(rows, keys):
    seen = set()
    kept = []
    duplicates = 0
    for row in rows:
        signature = tuple(row.get(key, "") for key in keys)
        if signature in seen:
            duplicates += 1
        else:
            seen.add(signature)
            kept.append(row)
    return kept, duplicates


def resolve_latest(rows, id_key, revision_key, label):
    by_id = defaultdict(list)
    for row in rows:
        by_id[row[id_key]].append(row)
    winners = []
    revisions_by_id = {}
    multi_revision = 0
    conflicts = []
    for key, group in by_id.items():
        numeric_revs = [int(row[revision_key]) for row in group]
        top = max(numeric_revs)
        top_rows = [row for row in group if int(row[revision_key]) == top]
        payloads = {tuple(sorted((k, v) for k, v in row.items() if not k.startswith("_source"))) for row in top_rows}
        if len(payloads) != 1:
            conflicts.append(key)
            continue
        if len(set(numeric_revs)) > 1:
            multi_revision += 1
        winners.append(top_rows[0])
        revisions_by_id[key] = top
    if conflicts:
        raise ValueError(f"{label} latest-revision conflicts require manual resolution: {conflicts}")
    return winners, revisions_by_id, multi_revision


def parse_date(text):
    if not text:
        return None
    return date.fromisoformat(text)


def json_value(v):
    if isinstance(v, Decimal):
        return float(v)
    return v


def load_fx():
    path = SRC / "ecb-history.csv"
    daily = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = date.fromisoformat(row["Date"])
            if d.year != 2025:
                continue
            daily.append(row)
    sums = defaultdict(Decimal)
    counts = Counter()
    for row in daily:
        month = row["Date"][:7]
        for code in FX_CODES:
            value = row.get(code, "").strip()
            if value and value.upper() != "N/A":
                sums[(code, month)] += Decimal(value)
                counts[(code, month)] += 1
    fx = {}
    fx_rows = []
    for code in FX_CODES:
        for month in [f"2025-{m:02d}" for m in range(1, 13)]:
            count = counts[(code, month)]
            if count == 0:
                raise ValueError(f"No archived ECB business-day quotes for {code} {month}")
            mean = sums[(code, month)] / Decimal(count)
            fx[(code, month)] = mean
            fx_rows.append({"currency": code, "month": month, "local_per_eur": float(mean), "business_days": count})
    return fx, fx_rows, len(daily), {code: [counts[(code, f"2025-{m:02d}")] for m in range(1, 13)] for code in FX_CODES}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    DELIVER.mkdir(parents=True, exist_ok=True)

    order_files = ["orders-part1.csv", "orders-part2.csv", "order-corrections.csv"]
    raw_order_rows = []
    order_counts_by_file = {}
    for name in order_files:
        batch = read_csv(SRC / name)
        order_counts_by_file[name] = len(batch)
        for row in batch:
            row["_source_file"] = name
            raw_order_rows.append(row)
    data_columns = list(read_csv(SRC / order_files[0])[0].keys())
    orders_dedup, duplicate_orders = stable_unique(raw_order_rows, data_columns)
    all_latest, order_revisions, multi_rev_orders = resolve_latest(
        orders_dedup, "order_id", "revision", "order"
    )
    order_by_id = {row["order_id"]: row for row in all_latest}

    partition = Counter()
    excluded_detail = []
    eligible = []
    for row in all_latest:
        shipped = parse_date(row["shipped_at"])
        if row["status"].strip().lower() != "shipped":
            reason = "status is not shipped"
        elif row["is_test"].strip().lower() != "false":
            reason = "test transaction"
        elif shipped is None or shipped.year != 2025:
            reason = "shipped date missing or outside 2025"
        elif row["country"] not in COUNTRIES:
            reason = "country outside decision set"
        else:
            reason = "eligible 2025 shipment"
        partition[reason] += 1
        row["_selected_revision"] = order_revisions[row["order_id"]]
        row["_decision"] = reason
        if reason == "eligible 2025 shipment":
            eligible.append(row)
        else:
            excluded_detail.append({"order_id": row["order_id"], "revision": row["revision"], "decision": reason, "source_file": row["_source_file"]})
    eligible_by_id = {row["order_id"]: row for row in eligible}

    fx, fx_rows, ecb_2025_day_rows, days_per_month = load_fx()
    costs = defaultdict(list)
    for row in read_csv(SRC / "unit-costs.csv"):
        costs[row["sku"]].append((date.fromisoformat(row["valid_from"]), Decimal(row["unit_cost_eur"])))
    for sku in costs:
        costs[sku].sort()

    raw_return_rows = read_csv(SRC / "returns.csv")
    ret_dedup, duplicate_returns = stable_unique(raw_return_rows, list(raw_return_rows[0].keys()))
    latest_returns, return_revisions, multi_rev_returns = resolve_latest(ret_dedup, "return_id", "revision", "return")
    valid_returns = []
    return_decisions = []
    returns_after_cutoff = 0
    orphan_missing_order = 0
    returns_linked_ineligible = 0
    for row in latest_returns:
        received = parse_date(row["received_at"])
        if received is None or received > CUTOFF:
            decision = "received after 2026-01-31 or missing date"
            returns_after_cutoff += 1
        elif row["order_id"] not in order_by_id:
            decision = "orphan order_id absent from order extracts"
            orphan_missing_order += 1
        elif row["order_id"] not in eligible_by_id:
            decision = "linked order is not an eligible 2025 shipment"
            returns_linked_ineligible += 1
        else:
            decision = "included; linked eligible order and received by cutoff"
            valid_returns.append(row)
        return_decisions.append({"return_id": row["return_id"], "revision": row["revision"], "order_id": row["order_id"], "received_at": row["received_at"], "decision": decision})
    returns_by_order = defaultdict(list)
    for row in valid_returns:
        returns_by_order[row["order_id"]].append(row)

    order_ledger = []
    monthly_cents = defaultdict(lambda: Counter())
    country_cents = defaultdict(lambda: Counter())
    cost_missing = []
    negative_gross_orders = []
    refund_over_gross_orders = []
    restock_over_shipped_orders = []
    returned_units_over_shipped_orders = []
    zero_price_orders = []
    currency_country_mismatches = []

    for row in eligible:
        ship_date = parse_date(row["shipped_at"])
        month = ship_date.strftime("%Y-%m")
        currency = row["currency"]
        rate = Decimal(1) if currency == "EUR" else fx[(currency, month)]
        quantity = int(row["quantity"])
        unit_price = Decimal(row["unit_price_local"])
        discount = Decimal(row["discount_local"])
        gross_local = Decimal(quantity) * unit_price - discount
        if gross_local < 0:
            negative_gross_orders.append(row["order_id"])
        gross_eur = cents(gross_local / rate)
        if gross_eur == 0:
            zero_price_orders.append(row["order_id"])
        if (row["country"] in ("POL", "CZE")) != (currency in ("PLN", "CZK")) or (row["country"] == "POL" and currency != "PLN") or (row["country"] == "CZE" and currency != "CZK") or (row["country"] not in ("POL", "CZE") and currency != "EUR"):
            currency_country_mismatches.append(row["order_id"])

        matching_returns = returns_by_order.get(row["order_id"], [])
        refund_local = sum((Decimal(ret["refund_local"]) for ret in matching_returns), Decimal(0))
        returned_units = sum(int(ret["quantity"]) for ret in matching_returns)
        restocked_units = sum(int(ret["restocked_quantity"]) for ret in matching_returns)
        refunds_eur = cents(refund_local / rate)
        if refunds_eur > gross_eur:
            refund_over_gross_orders.append(row["order_id"])
        if restocked_units > quantity:
            restock_over_shipped_orders.append(row["order_id"])
        if returned_units > quantity:
            returned_units_over_shipped_orders.append(row["order_id"])

        shipped_cost_date = ship_date
        valid_unit_cost = [item for item in costs.get(row["sku"], []) if item[0] <= shipped_cost_date]
        if not valid_unit_cost:
            cost_missing.append(row["order_id"])
            raise ValueError(f"No effective unit cost for {row['order_id']}")
        unit_cost = valid_unit_cost[-1][1]
        gross_cogs = cents(Decimal(quantity) * unit_cost)
        recovered_cogs = cents(Decimal(restocked_units) * unit_cost)
        net_cogs = gross_cogs - recovered_cogs
        fulfillment = cents(Decimal(row["fulfillment_eur"]))
        contribution = gross_eur - refunds_eur - net_cogs - fulfillment
        vals = {
            "shipped_orders": 1,
            "shipped_units": quantity,
            "gross_sales_eur_cents": gross_eur,
            "refunds_eur_cents": refunds_eur,
            "net_sales_eur_cents": gross_eur - refunds_eur,
            "net_cogs_eur_cents": net_cogs,
            "fulfillment_eur_cents": fulfillment,
            "contribution_eur_cents": contribution,
            "returned_units": returned_units,
        }
        for k, v in vals.items():
            monthly_cents[(row["country"], month)][k] += v
            country_cents[row["country"]][k] += v
        order_ledger.append({
            "order_id": row["order_id"], "revision": int(row["revision"]), "country": row["country"], "shipped_at": row["shipped_at"], "month": month,
            "sku": row["sku"], "quantity": quantity, "currency": currency, "ecb_local_per_eur": float(rate), "gross_local": float(gross_local),
            "refund_local": float(refund_local), "unit_cost_eur": float(unit_cost), "restocked_units": restocked_units,
            "shipped_orders": 1, "shipped_units": quantity, "gross_sales_eur": eur(gross_eur), "refunds_eur": eur(refunds_eur),
            "net_sales_eur": eur(gross_eur - refunds_eur), "gross_cogs_eur": eur(gross_cogs), "recovered_cogs_eur": eur(recovered_cogs),
            "net_cogs_eur": eur(net_cogs), "fulfillment_eur": eur(fulfillment), "contribution_eur": eur(contribution), "returned_units": returned_units,
            "return_ids": ";".join(sorted(ret["return_id"] for ret in matching_returns)),
        })

    def to_metric_row(country, month=None):
        source = monthly_cents[(country, month)] if month else country_cents[country]
        result = {"country": country}
        if month:
            result["month"] = month
        for key in ("shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units"):
            if key in ("shipped_orders", "shipped_units", "returned_units"):
                result[key] = int(source[key])
            else:
                result[key] = eur(source[key + "_cents"])
        result["margin"] = (round(result["contribution_eur"] / result["net_sales_eur"], 8) if result["net_sales_eur"] != 0 else None)
        return result

    monthly = [to_metric_row(c, f"2025-{m:02d}") for c in COUNTRIES for m in range(1, 13)]
    countries = [to_metric_row(c) for c in COUNTRIES]

    # Preserve all archived observations, including null values and source vintage.
    wb_rows = {}
    wb_meta = {}
    for name, indicator, unit in (("population.json", "SP.POP.TOTL", "persons"), ("gdp-per-capita.json", "NY.GDP.PCAP.CD", "current US dollars per person")):
        payload = json.loads((SRC / name).read_text(encoding="utf-8"))
        meta, observations = payload
        wb_meta[indicator] = {"source_file": name, "sourceid": meta.get("sourceid"), "lastupdated": meta.get("lastupdated"), "unit": unit}
        for rec in observations:
            key = (rec["countryiso3code"], int(rec["date"]))
            wb_rows.setdefault(key, {})
            wb_rows[key]["population" if indicator == "SP.POP.TOTL" else "gdp_per_capita_usd"] = rec.get("value")
    market_context = []
    for country in COUNTRIES:
        for year in (2022, 2023, 2024):
            vals = wb_rows.get((country, year), {})
            market_context.append({"country": country, "year": year, "population": vals.get("population"), "gdp_per_capita_usd": vals.get("gdp_per_capita_usd")})

    option_rows = read_csv(SRC / "hub-options.csv")
    options = {r["country"]: {"capex_eur": int(r["capex_eur"]), "fte": int(r["fte"]), "annual_fixed_eur": Decimal(r["annual_fixed_eur"]), "saving_eur_per_unit": Decimal(r["saving_eur_per_unit"])} for r in option_rows}
    base = {r["country"]: r for r in countries}

    def scenario_value(members, scenario):
        uplift = SCENARIOS.get(scenario, Decimal("0.25"))
        total = Decimal(0)
        for c in members:
            b = base[c]
            o = options[c]
            C = Decimal(str(b["contribution_eur"]))
            U = Decimal(b["shipped_units"])
            G = Decimal(str(b["gross_sales_eur"]))
            N = Decimal(str(b["net_sales_eur"]))
            saving = o["saving_eur_per_unit"]
            fixed = o["annual_fixed_eur"]
            if scenario == "stress":
                fx_shock = Decimal("0.10") * N if c in ("POL", "CZE") else Decimal(0)
                C_stress = C - Decimal("0.03") * G - fx_shock
                annual = C_stress * Decimal("1.25") - C + U * Decimal("1.25") * saving - fixed
            else:
                annual = C * uplift + U * (Decimal(1) + uplift) * saving - fixed
            total += annual
        return total

    all_sets = [(c,) for c in COUNTRIES]
    for pair in combinations(COUNTRIES, 2):
        capex = sum(options[c]["capex_eur"] for c in pair)
        fte = sum(options[c]["fte"] for c in pair)
        if capex <= 450000 and fte <= 7:
            all_sets.append(pair)
    hub_scenarios = []
    for members in all_sets:
        countries_key = "+".join(members)
        capex = sum(options[c]["capex_eur"] for c in members)
        fte = sum(options[c]["fte"] for c in members)
        for scenario in ("low", "base", "high", "stress"):
            annual = scenario_value(members, scenario)
            payback = Decimal(capex) / annual if annual > 0 else None
            hub_scenarios.append({
                "country": countries_key, "countries": list(members), "scenario": scenario,
                "incremental_contribution_eur": round(float(annual), 2), "capex_eur": capex,
                "fte": fte, "payback_years": round(float(payback), 4) if payback is not None else None,
            })
    for scenario in ("low", "base", "high", "stress"):
        hub_scenarios.append({"country": "DEFER", "countries": [], "scenario": scenario, "incremental_contribution_eur": 0.0, "capex_eur": 0, "fte": 0, "payback_years": None})
    base_scenarios = [r for r in hub_scenarios if r["scenario"] == "base"]
    base_scenarios.sort(key=lambda r: (-r["incremental_contribution_eur"], r["capex_eur"], r["country"]))
    stress_by_key = {r["country"]: r for r in hub_scenarios if r["scenario"] == "stress"}
    stress_scenarios = sorted((r for r in hub_scenarios if r["scenario"] == "stress"), key=lambda r: (-r["incremental_contribution_eur"], r["capex_eur"], r["country"]))
    best = base_scenarios[0] if base_scenarios else None
    second = base_scenarios[1] if len(base_scenarios) > 1 else None
    if best and best["incremental_contribution_eur"] > 0:
        rec_countries = best["countries"]
        rationale = (f"Highest modeled base-case recurring incremental contribution among feasible singles and pairs: EUR {best['incremental_contribution_eur']:,.2f}/year after fixed costs, with EUR {best['capex_eur']:,.0f} year-zero capex and {best['fte']} FTE. This is scenario arithmetic on synthetic inputs, not a causal hub estimate. Stress contribution is EUR {stress_by_key[best['country']]['incremental_contribution_eur']:,.2f}/year."
                     if best else "No feasible option.")
    else:
        rec_countries = []
        rationale = "Defer all hubs because no feasible option has positive modeled base-case recurring incremental contribution."
    rec_capex = sum(options[c]["capex_eur"] for c in rec_countries)
    rec_fte = sum(options[c]["fte"] for c in rec_countries)
    recommendation = {
        "countries": rec_countries, "capex_eur": rec_capex, "fte": rec_fte, "rationale": rationale,
        "decision_rule": "Among defer/singles/feasible pairs, choose the feasible non-empty option with greatest base-case incremental annual contribution; constraints are capex <= EUR450,000, FTE <= 7, and no more than two hubs. Stress and simple payback are decision disclosures, not probability-weighted objective values.",
        "strongest_alternative": second,
        "stress_resilient_alternative": stress_scenarios[0] if stress_scenarios else None,
        "criteria_and_provenance": {
            "hard_constraints": ["capex <= EUR450,000", "staffing <= 7 FTE", "no more than two hubs"],
            "primary_comparison": "base-case annual incremental contribution after recurring fixed costs; no numeric weights applied",
            "secondary_comparisons": ["simple undiscounted payback", "low/high scenario range", "defined joint refund/FX stress", "capex and FTE use"],
            "source_of_option_ratings": "computed from synthetic client baseline and assumptions in hub-options.csv and scenario-policy.md",
            "board_risk_preference": "not supplied; base-case maximization is a transparent analyst default, not a measured board preference",
            "probabilities": "not supplied; scenarios are not probability-weighted",
        },
        "concessions_and_accepted_risks": [
            "The recommendation uses only half of the EUR450,000 capex ceiling and five of seven FTE; it gives up the higher stressed annual contribution of the NLD+ESP alternative.",
            "The defined joint stress leaves positive annual incremental contribution but lengthens simple payback to about seven years.",
            "The option uplift and savings are synthetic planning assumptions; no site-specific customer or operational validation is available in the source room.",
        ],
        "switch_conditions": ["Reopen the funding choice if validated site-specific volume uplift or realized per-unit savings do not support the modeled annual gain.", "Reopen if procurement confirms capex or recurring fixed cost above the option inputs, or if staffing is unavailable within the stated cap.", "The defined joint stress is a scenario only; a sustained refund/FX pattern worse than this stress weakens the recommendation."],
    }
    if best and second and best["countries"] != second["countries"]:
        unique_best = [c for c in best["countries"] if c not in second["countries"]]
        unique_second = [c for c in second["countries"] if c not in best["countries"]]
        if len(unique_best) == len(unique_second) == 1:
            cb, cs = unique_best[0], unique_second[0]
            other_site_increment = scenario_value((cs,), "base")
            b = base[cb]; o = options[cb]
            C = Decimal(str(b["contribution_eur"])); U = Decimal(b["shipped_units"]); saving = o["saving_eur_per_unit"]; fixed = o["annual_fixed_eur"]
            uplift_switch = (other_site_increment + fixed - U * saving) / (C + U * saving)
            target = other_site_increment
            saving_switch = (target + fixed - C * Decimal("0.25")) / (U * Decimal("1.25"))
            recommendation["base_rank_switch_example"] = {
                "replaces_country": cs, "selected_country": cb, "other_hub_shared": sorted(set(best["countries"]) & set(second["countries"])),
                "selected_site_uplift_threshold_if_alternative_site_uplift_is_25pct": round(float(uplift_switch), 6),
                "selected_site_saving_threshold_eur_per_unit_if_both_uplifts_are_25pct": round(float(saving_switch), 4),
                "interpretation": "Holding the shared hub and other assumptions constant, a selected-site uplift below this threshold or per-unit saving below this threshold would erase its modeled base-case advantage over the next base-ranked alternative.",
            }

    # Reconcile country totals to monthly sums and the combined eligible ledger.
    reconciliation = {}
    sum_fields = ["shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units"]
    for field in sum_fields:
        monthly_total = sum(row[field] for row in monthly)
        country_total = sum(row[field] for row in countries)
        ledger_total = sum(row[field] for row in order_ledger)
        tolerance = 0.004999 if isinstance(monthly_total, float) else 0
        reconciliation[field] = {"monthly_sum": round(monthly_total, 2) if isinstance(monthly_total, float) else monthly_total, "country_sum": round(country_total, 2) if isinstance(country_total, float) else country_total, "order_ledger_sum": round(ledger_total, 2) if isinstance(ledger_total, float) else ledger_total, "pass": abs(monthly_total - country_total) <= tolerance and abs(monthly_total - ledger_total) <= tolerance}
    if not all(item["pass"] for item in reconciliation.values()):
        raise AssertionError(f"Monthly/country/order ledger reconciliation failed: {reconciliation}")
    if len(monthly) != 72 or len(countries) != 6:
        raise AssertionError("Output grid incomplete")

    # Ensure source-room hashes are still identical to the first saved snapshot.
    manifest = json.loads((SRC / "collection-manifest.json").read_text())
    hash_checks = []
    for item in manifest["files"]:
        local_path = ROOT / item["file"]
        digest = hashlib.sha256(local_path.read_bytes()).hexdigest()
        hash_checks.append({"file": item["file"], "pass": digest == item["sha256"], "sha256": digest})
    if not all(x["pass"] for x in hash_checks):
        raise AssertionError("A saved source-room file differs from collection manifest")

    # Detailed source register with required provenance fields.
    source_meta = {item["file"].split("/")[-1]: item for item in manifest["files"]}
    original_register = json.loads((SRC / "source-register.json").read_text())
    public_meta = {item["file"]: item for item in original_register.get("public", [])}
    source_rows = []
    local_metadata = {
        "index.html": ("HTML source-room index", "2026-09-27", "source-room index; not analytical observations"),
        "data-dictionary.md": ("descriptive rules; no numeric unit", "2025 shipments; returns through 2026-01-31", "synthetic client documentation"),
        "ecb-history.csv": ("local currency units per EUR; daily ECB reference quote", "history through 2026-09-25; analysis uses 2025", "public official ECB archive; lossless CSV extracted from supplied ZIP"),
        "ecb-history.zip": ("daily ECB reference rates", "history through 2026-09-25; analysis uses 2025", "public official ECB snapshot"),
        "gdp-per-capita.json": ("current US dollars per person", "2022-2024", "public official World Bank archive"),
        "hub-options.csv": ("EUR capex, FTE, EUR/year recurring cost, EUR/unit saving", "client planning assumptions; no period beyond annual fixed cost", "synthetic client assumption"),
        "order-corrections.csv": ("order-level local sales, quantity, EUR fulfillment cost", "2025 and out-of-period rows as exported", "synthetic client export/corrections"),
        "orders-part1.csv": ("one order/SKU row; local currency sales; EUR fulfillment", "2025 and out-of-period rows as exported", "synthetic client export"),
        "orders-part2.csv": ("one order/SKU row; local currency sales; EUR fulfillment", "2025 and out-of-period rows as exported", "synthetic client export"),
        "population.json": ("persons", "2022-2024", "public official World Bank archive"),
        "returns.csv": ("return_id rows; physical units and refund in original local currency", "received dates through 2026; cutoff 2026-01-31", "synthetic client export"),
        "scenario-policy.md": ("EUR, units, FTE and scenario formulas", "annual scenarios; capex year zero", "synthetic client assumption"),
        "source-register.json": ("source metadata", "retrieval vintage 2026-09-27", "source-room provenance metadata"),
        "unit-costs.csv": ("EUR per unit effective-dated", "2025-01-01 onward", "synthetic client assumption"),
    }
    for item in manifest["files"]:
        basename = item["file"].split("/")[-1]
        meta = public_meta.get(basename, {})
        units, period, status = local_metadata.get(basename, ("descriptive metadata", "as supplied", "synthetic source-room metadata"))
        source_url = meta.get("original_url", item["source_url"])
        retrieved_at = meta.get("retrieved_utc", item["retrieved_at_utc"])
        vintage_note = meta.get("transformation", "")
        if basename == "ecb-history.csv":
            archive_meta = public_meta.get("ecb-history.zip", {})
            source_url = archive_meta.get("original_url", source_url)
            retrieved_at = archive_meta.get("retrieved_utc", retrieved_at)
            vintage_note = "Lossless CSV extracted from the ECB ZIP archive; source-room archive vintage and original URL are recorded."
        if not vintage_note:
            if meta:
                vintage_note = "Official archived snapshot; original metadata and source-room vintage are preserved in the supplied files."
            else:
                vintage_note = f"Frozen source-room file collected {item['retrieved_at_utc']}; client input/status is described in the source-room documentation."
        source_rows.append({
            "file": item["file"], "url": source_url, "retrieved_at_utc": retrieved_at,
            "sha256": item["sha256"], "units": units, "period": period, "status": status,
            "vintage_or_note": vintage_note,
        })
    with (OUT / "source_register.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(source_rows[0].keys()))
        w.writeheader(); w.writerows(source_rows)

    # Save auditable derived ledgers and tables.
    def write_csv(name, rows):
        if not rows:
            return
        with (OUT / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)

    write_csv("monthly.csv", monthly)
    write_csv("country_totals.csv", countries)
    write_csv("fx_monthly.csv", fx_rows)
    write_csv("market_context.csv", market_context)
    write_csv("hub_scenarios.csv", hub_scenarios)
    write_csv("order_ledger.csv", order_ledger)
    write_csv("order_exclusions.csv", excluded_detail)
    write_csv("return_decisions.csv", return_decisions)

    wb_pop_null = sum(row["population"] is None for row in market_context)
    wb_gdp_null = sum(row["gdp_per_capita_usd"] is None for row in market_context)
    country_sum = sum(row["contribution_eur"] for row in countries)
    quality = {
        "cutoff_inclusive": CUTOFF.isoformat(),
        "order_rows_by_source": order_counts_by_file,
        "order_raw_rows": len(raw_order_rows), "order_exact_duplicate_rows_removed": duplicate_orders,
        "order_distinct_revision_rows_after_dedup": len(orders_dedup), "order_distinct_ids": len(all_latest),
        "order_ids_with_multiple_revisions": multi_rev_orders, "order_ids_selected_at_revision_gt_1": sum(int(r["revision"]) > 1 for r in all_latest),
        "correction_rows": order_counts_by_file["order-corrections.csv"], "selected_rows_from_corrections": sum(r["_source_file"] == "order-corrections.csv" for r in all_latest),
        "order_latest_revision_conflicts": 0, "order_exclusion_partition": dict(partition), "eligible_2025_shipped_orders": len(eligible),
        "zero_gross_eur_shipped_orders": len(zero_price_orders), "zero_gross_eur_order_ids": zero_price_orders,
        "negative_gross_order_ids": negative_gross_orders, "refunds_exceed_gross_order_ids": refund_over_gross_orders,
        "currency_country_mismatch_order_ids": currency_country_mismatches, "unit_cost_missing_order_ids": cost_missing,
        "restocked_units_exceed_shipped_order_ids": restock_over_shipped_orders, "returned_units_exceed_shipped_order_ids": returned_units_over_shipped_orders,
        "return_raw_rows": len(raw_return_rows), "return_exact_duplicate_rows_removed": duplicate_returns,
        "return_revision_rows_after_dedup": len(ret_dedup), "return_distinct_ids": len(latest_returns),
        "return_ids_with_multiple_revisions": multi_rev_returns, "return_latest_revision_conflicts": 0,
        "returns_after_cutoff_excluded": returns_after_cutoff, "orphan_returns_missing_order_excluded": orphan_missing_order,
        "returns_linked_to_ineligible_order_excluded": returns_linked_ineligible, "returns_included": len(valid_returns),
        "return_cutoff_count_partition": {"after_cutoff": returns_after_cutoff, "orphan": orphan_missing_order, "linked_ineligible": returns_linked_ineligible, "included": len(valid_returns)},
        "world_bank_rows_expected": 18, "world_bank_rows_observed": len(market_context), "population_nulls_preserved": wb_pop_null,
        "gdp_per_capita_nulls_preserved": wb_gdp_null, "world_bank_vintage": wb_meta,
        "ecb_archive_analysis_days": ecb_2025_day_rows, "ecb_month_currency_cells": len(fx_rows), "ecb_business_days_per_month": days_per_month,
        "monthly_rows": len(monthly), "country_rows": len(countries), "country_year_contribution_total_eur": round(country_sum, 2),
        "country_year_totals": {field: sum(row[field] for row in countries) for field in sum_fields},
        "aggregate_margin": round(country_sum / sum(row["net_sales_eur"] for row in countries), 8) if sum(row["net_sales_eur"] for row in countries) else None,
        "aggregate_returned_units_rate": round(sum(row["returned_units"] for row in countries) / sum(row["shipped_units"] for row in countries), 8) if sum(row["shipped_units"] for row in countries) else None,
        "gross_cogs_eur": round(sum(r["gross_cogs_eur"] for r in order_ledger), 2),
        "recovered_cogs_eur": round(sum(r["recovered_cogs_eur"] for r in order_ledger), 2),
        "reconciliation": reconciliation, "source_hash_checks": hash_checks,
        "material_notes": [
            "Input client transactions, returns, hub options, unit costs, and scenario assumptions are synthetic; public World Bank and ECB observations are archived snapshots, not live-retrieved estimates.",
            "The local ECB quote is units of local currency per EUR. Both order sales and refunds use the original shipment month mean. EUR is fixed at 1 by convention.",
            "Returns are counted once per selected return_id revision, after exact duplicate removal, cutoff check, and an exact order_id join. Orphans are retained in the quarantine decision ledger.",
            "Booked net sales follow gross sales less received refunds through cutoff. Cash collection/settlement records are absent; contribution further subtracts net COGS and nonrefundable fulfillment.",
            "Simple payback is capex divided by positive annual incremental contribution, with no discounting, ramp, taxes, residual value, or timing effects.",
        ],
    }
    metrics = {
        "monthly": monthly, "countries": countries,
        "fx_monthly": [{k: r[k] for k in ("currency", "month", "local_per_eur")} for r in fx_rows],
        "market_context": market_context, "hub_scenarios": hub_scenarios,
        "recommendation": recommendation, "quality": quality,
        "assumptions": {"scenario_formula_source": "scenario-policy.md", "scenario_uplifts": {k: float(v) for k, v in SCENARIOS.items()}, "capex_budget_eur": 450000, "fte_budget": 7, "maximum_hubs": 2, "feasible_option_count_including_singles": len(all_sets), "feasible_pair_count": len(all_sets)-len(COUNTRIES), "infeasible_pairs": ["+".join(pair) for pair in combinations(COUNTRIES, 2) if sum(options[c]["capex_eur"] for c in pair) > 450000 or sum(options[c]["fte"] for c in pair) > 7]},
        "country_baseline": [{"country": c, "contribution_eur": base[c]["contribution_eur"], "gross_sales_eur": base[c]["gross_sales_eur"], "net_sales_eur": base[c]["net_sales_eur"], "units": base[c]["shipped_units"], "returns_rate_units": round(base[c]["returned_units"] / base[c]["shipped_units"], 6) if base[c]["shipped_units"] else None, **{k: (float(v) if isinstance(v, Decimal) else v) for k,v in options[c].items()}} for c in COUNTRIES],
        "hub_option_ranking_base": base_scenarios,
    }
    (DELIVER / "metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (OUT / "run_summary.json").write_text(json.dumps({"eligible_orders": len(eligible), "country_totals": countries, "recommendation": recommendation, "quality": quality}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "eligible_orders": len(eligible),
        "monthly_rows": len(monthly),
        "country_year_totals": quality["country_year_totals"],
        "top_base_options": [{k: row[k] for k in ("country", "incremental_contribution_eur", "capex_eur", "fte", "payback_years")} for row in base_scenarios[:5]],
        "recommendation": {k: recommendation[k] for k in ("countries", "capex_eur", "fte", "rationale")},
        "quality_counts": {k: quality[k] for k in ("order_raw_rows", "order_exact_duplicate_rows_removed", "order_ids_with_multiple_revisions", "eligible_2025_shipped_orders", "zero_gross_eur_shipped_orders", "return_exact_duplicate_rows_removed", "returns_included", "orphan_returns_missing_order_excluded", "returns_after_cutoff_excluded")},
        "reconciliations_pass": all(v["pass"] for v in reconciliation.values()),
    }, indent=2))


if __name__ == "__main__":
    main()

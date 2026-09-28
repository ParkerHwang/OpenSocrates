"""Independent checks for saved source provenance, calculations and artifacts."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import zipfile
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from openpyxl import load_workbook
from PIL import Image
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "evidence" / "source_room"
DEL = ROOT / "deliverables"
OUT = ROOT / "analysis" / "output"
CENT = Decimal("0.01")
ZERO = Decimal("0")
CHECKS = 0


def csv_rows(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def money(x):
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def check(condition, message):
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(message)


def main():
    metrics = json.loads((DEL / "metrics.json").read_text())
    manifest = json.loads((SRC / "download_manifest.json").read_text())
    source_register = json.loads((DEL / "source_register.json").read_text())

    required_arrays = {
        "monthly": 72,
        "countries": 6,
        "fx_monthly": 24,
        "market_context": 18,
        "hub_scenarios": 24,
        "combination_scenarios": 44,
    }
    for key, expected_len in required_arrays.items():
        check(isinstance(metrics.get(key), list) and len(metrics[key]) == expected_len, f"metrics.{key} has {expected_len} rows")
    fields = {"country", "shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units", "margin"}
    check(all(fields <= set(r) and "month" in r for r in metrics["monthly"]), "monthly required schema present")
    check(all(fields <= set(r) and "month" not in r for r in metrics["countries"]), "country required schema present")
    check(all({"currency", "month", "local_per_eur"} <= set(r) for r in metrics["fx_monthly"]), "FX required schema present")
    check({"countries", "capex_eur", "fte", "rationale"} <= set(metrics["recommendation"]), "recommendation fields present")
    sensitivity = metrics["sensitivity_analysis"]
    check({"baseline", "tested_ranges", "perturbation_results", "switching_values", "robust_or_fragile_conclusion", "research_priority", "flip_condition"} <= set(sensitivity), "public sensitivity output contract present")
    check(metrics["recommendation"]["flip_condition"] == sensitivity["flip_condition"], "recommendation and sensitivity flip condition agree")
    check([r["winner"] for r in sensitivity["perturbation_results"][:3]] == ["CZE+ESP"] * 3, "CZE + ESP remains base leader at 10%, 25% and 40% uplift")
    volume_flips = sensitivity["switching_values"][:2]
    check(volume_flips[0]["from"] == "Defer" and volume_flips[0]["to"] == "Czechia" and abs(volume_flips[0]["uplift_pct"] - 2.6188) < 0.001, "first volume switch is deferral to Czechia at about 2.62%")
    check(volume_flips[1]["from"] == "Czechia" and volume_flips[1]["to"] == "CZE+ESP" and abs(volume_flips[1]["uplift_pct"] - 2.8482) < 0.001, "second volume switch is Czechia to CZE + ESP at about 2.85%")
    check("below 10%" in volume_flips[0]["provenance"], "sub-10% switch values are labelled as extrapolation")
    check(sensitivity["switching_values"][2]["switch_to"] == "NLD+ESP", "stress floor switching alternative is NLD + ESP")

    # Raw-file collection manifest: byte length and SHA-256 are verifiable.
    source_by_file = {r["file"]: r for r in source_register}
    check(len(source_register) == 14, "source register includes index and every source-room file")
    for row in manifest["files"]:
        payload = (SRC / row["file"]).read_bytes()
        check(len(payload) == row["bytes"] and hashlib.sha256(payload).hexdigest() == row["sha256"], f"saved source hash/size match manifest: {row['file']}")
        check(row["file"] in source_by_file, f"source register covers {row['file']}")
    wb_sources = [r for r in source_register if r["file"] in {"population.json", "gdp-per-capita.json", "ecb-history.zip", "ecb-history.csv"}]
    check(all(r["original_source_url"].startswith("https://") and r["original_archive_retrieved_utc"] and r["sha256"] for r in wb_sources), "archived official source URLs, vintages and hashes are registered")

    # Check ECB CSV is exactly the saved member of the original-source ZIP.
    with zipfile.ZipFile(SRC / "ecb-history.zip") as zf:
        check(zf.testzip() is None, "ECB archive ZIP CRC check passes")
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        check(bool(csv_names), "ECB archive contains a CSV member")
        ecb_member = zf.read(csv_names[0])
    check(ecb_member == (SRC / "ecb-history.csv").read_bytes(), "ECB CSV is a byte-identical lossless ZIP extraction")

    # Recompute monthly reference means from saved daily ECB values.
    ecb = csv_rows(SRC / "ecb-history.csv")
    for currency in ["PLN", "CZK"]:
        for month in [f"2025-{m:02d}" for m in range(1, 13)]:
            daily = [Decimal(r[currency]) for r in ecb if r["Date"].startswith(month) and r.get(currency, "").strip()]
            calculated = sum(daily, ZERO) / Decimal(len(daily))
            saved = next(r["local_per_eur"] for r in metrics["fx_monthly"] if r["currency"] == currency and r["month"] == month)
            check(abs(calculated - Decimal(str(saved))) < Decimal("1e-12"), f"ECB monthly mean matches source for {currency} {month} ({len(daily)} observations)")

    # Monthly to country reconciliation and component identities.
    int_fields = {"shipped_orders", "shipped_units", "returned_units"}
    money_fields = fields - int_fields - {"country", "margin"}
    for country in [r["country"] for r in metrics["countries"]]:
        annual = next(r for r in metrics["countries"] if r["country"] == country)
        months = [r for r in metrics["monthly"] if r["country"] == country]
        check(len(months) == 12, f"{country} has all 12 monthly rows")
        for field in int_fields | money_fields:
            summed = sum((Decimal(str(r[field])) for r in months), ZERO)
            annual_value = Decimal(str(annual[field]))
            check(summed == annual_value, f"{country} monthly totals reconcile for {field}")
        check(money(annual["gross_sales_eur"] - annual["refunds_eur"]) == money(annual["net_sales_eur"]), f"{country} net sales = gross - refunds")
        check(money(annual["net_sales_eur"] - annual["net_cogs_eur"] - annual["fulfillment_eur"]) == money(annual["contribution_eur"]), f"{country} contribution bridge reconciles")
        expected_margin = None if annual["net_sales_eur"] == 0 else annual["contribution_eur"] / annual["net_sales_eur"]
        check((annual["margin"] is None and expected_margin is None) or abs(annual["margin"] - expected_margin) < 1e-12, f"{country} margin uses contribution/net sales")

    quality = metrics["quality"]
    check(quality["order_revision_audit"] == {"raw_rows": 1328, "identical_duplicates_removed": 13, "selected_ids": 1297, "superseded_rows": 18}, "order pages and corrections reconcile through highest-revision rule")
    check(quality["selected_orders_calculated"] == 1254, "all eligible shipped 2025 orders are valued")
    check(quality["included_valid_zero_price_shipments"] == 12, "valid zero-price shipments are retained")
    check(quality["returns_handling_counts"]["orphan_order_id"] == 1 and quality["returns_handling_counts"]["after_cutoff"] == 1, "orphan and late returns are visible in quality counts")
    check(quality["order_missing_value_counts_among_eligible_candidates"] == {}, "no calculation fields are missing on eligible shipments")
    check(quality["monthly_country_reconciliation"].startswith("passed"), "monthly/country reconciliation is recorded")
    check(any("Orphan returns" in a["issue"] for a in quality["anomalies"]), "quality anomalies explicitly disclose orphan-return quarantine")

    # Validate each saved per-order component against selected raw rows and effective costs.
    raw_orders = []
    for name in ["orders-part1.csv", "orders-part2.csv", "order-corrections.csv"]:
        raw_orders.extend(csv_rows(SRC / name))
    by_order = defaultdict(list)
    for row in raw_orders:
        by_order[row["order_id"]].append(row)
    latest_order = {oid: max(rows, key=lambda r: int(r["revision"])) for oid, rows in by_order.items()}
    effective_costs = csv_rows(SRC / "unit-costs.csv")
    order_ledger = csv_rows(OUT / "order_components.csv")
    eligible_ids = {r["order_id"] for r in order_ledger}
    for r in order_ledger:
        raw = latest_order[r["order_id"]]
        shipped = raw["shipped_at"]
        applicable = [c for c in effective_costs if c["sku"] == raw["sku"] and c["valid_from"] <= shipped]
        expected_unit_cost = Decimal(max(applicable, key=lambda c: c["valid_from"])["unit_cost_eur"])
        qty = Decimal(raw["quantity"])
        rate = Decimal("1") if raw["currency"] == "EUR" else Decimal(str(next(f["local_per_eur"] for f in metrics["fx_monthly"] if f["currency"] == raw["currency"] and f["month"] == shipped[:7])))
        gross_local = qty * Decimal(raw["unit_price_local"]) - Decimal(raw["discount_local"])
        check(int(r["order_revision"]) == int(raw["revision"]), f"{r['order_id']} uses the selected highest order revision")
        check(r["shipped_at"] == shipped and r["sku"] == raw["sku"], f"{r['order_id']} preserves shipment date and SKU")
        check(Decimal(str(r["unit_cost_eur"])) == expected_unit_cost, f"{r['order_id']} uses latest effective unit cost")
        check(abs(Decimal(str(r["fx_local_per_eur"])) - rate) < Decimal("1e-12"), f"{r['order_id']} uses original sale-month ECB quote")
        check(Decimal(str(r["gross_local"])) == gross_local, f"{r['order_id']} local gross equals quantity × price − discount")
        check(Decimal(str(r["gross_sales_eur"])) == money(gross_local / rate), f"{r['order_id']} gross EUR uses per-order half-up rounding")
        check(Decimal(str(r["refunds_eur"])) == money(Decimal(str(r["refund_local"])) / rate), f"{r['order_id']} refund EUR uses same sale-month rate and per-order rounding")
        gross_cogs = money(qty * expected_unit_cost)
        recovered_cogs = money(Decimal(str(r["restocked_units"])) * expected_unit_cost)
        check(Decimal(str(r["gross_cogs_eur"])) == gross_cogs and Decimal(str(r["recovered_cogs_eur"])) == recovered_cogs, f"{r['order_id']} gross and restocked COGS use effective cost")
        check(Decimal(str(r["net_cogs_eur"])) == gross_cogs - recovered_cogs, f"{r['order_id']} net COGS bridge reconciles")
        fulfillment = money(Decimal(str(raw["fulfillment_eur"])))
        check(Decimal(str(r["fulfillment_eur"])) == fulfillment, f"{r['order_id']} fulfillment cost is rounded per order")
        net_sales = Decimal(str(r["gross_sales_eur"])) - Decimal(str(r["refunds_eur"]))
        contribution = net_sales - Decimal(str(r["net_cogs_eur"])) - Decimal(str(r["fulfillment_eur"]))
        check(Decimal(str(r["net_sales_eur"])) == net_sales and Decimal(str(r["contribution_eur"])) == contribution, f"{r['order_id']} net sales/contribution bridge reconciles")

    raw_returns = csv_rows(SRC / "returns.csv")
    unique_returns = {tuple(sorted(r.items())): r for r in raw_returns}.values()
    by_return = defaultdict(list)
    for row in unique_returns:
        by_return[row["return_id"]].append(row)
    selected_returns = [max(rows, key=lambda r: int(r["revision"])) for rows in by_return.values()]
    return_totals = defaultdict(lambda: {"quantity": 0, "restocked_quantity": 0, "refund_local": ZERO})
    for r in selected_returns:
        if r.get("received_at") and r["received_at"] <= "2026-01-31" and r.get("order_id") in eligible_ids:
            a = return_totals[r["order_id"]]
            a["quantity"] += int(r["quantity"])
            a["restocked_quantity"] += int(r["restocked_quantity"])
            a["refund_local"] += Decimal(r["refund_local"])
    for r in order_ledger:
        expected = return_totals[r["order_id"]]
        check(int(r["returned_units"]) == expected["quantity"] and int(r["restocked_units"]) == expected["restocked_quantity"], f"{r['order_id']} return/restock units join on selected return IDs")
        check(Decimal(str(r["refund_local"])) == expected["refund_local"], f"{r['order_id']} refund amount sums eligible selected return IDs")

    # Independently recalculate all individual hub options and pair arithmetic.
    options = {r["country"]: r for r in csv_rows(SRC / "hub-options.csv")}
    baselines = {r["country"]: r for r in metrics["countries"]}
    single = {(r["country"], r["scenario"]): r for r in metrics["hub_scenarios"]}
    uplifts = {"low": Decimal("0.10"), "base": Decimal("0.25"), "high": Decimal("0.40")}
    for country, option in options.items():
        b = baselines[country]
        C, U, G, N = [Decimal(str(b[k])) for k in ["contribution_eur", "shipped_units", "gross_sales_eur", "net_sales_eur"]]
        s, F = Decimal(option["saving_eur_per_unit"]), Decimal(option["annual_fixed_eur"])
        K, fte = int(option["capex_eur"]), int(option["fte"])
        for scenario in ["low", "base", "high"]:
            u = uplifts[scenario]
            expected = money(C*u + U*(Decimal(1)+u)*s - F)
            observed = Decimal(str(single[(country, scenario)]["incremental_contribution_eur"]))
            check(expected == observed, f"{country} {scenario} formula independently matches")
        fx_shock = Decimal("0.10")*N if country in {"POL", "CZE"} else ZERO
        c_stress = C - Decimal("0.03")*G - fx_shock
        stress_expected = money(c_stress*Decimal("1.25") - C + U*Decimal("1.25")*s - F)
        stress_row = single[(country, "stress")]
        check(stress_expected == Decimal(str(stress_row["incremental_contribution_eur"])), f"{country} stress formula independently matches")
        check(stress_row["capex_eur"] == K and stress_row["fte"] == fte, f"{country} option capex and staffing preserved")
        inc = stress_expected
        expected_payback = None if inc <= 0 else Decimal(K)/inc
        saved_payback = stress_row["payback_years"]
        check((expected_payback is None and saved_payback is None) or abs(float(expected_payback)-saved_payback) < 1e-10, f"{country} payback null/positive rule matches")

    pairs = metrics["combination_scenarios"]
    pair_keys = {(tuple(r["countries"]), r["scenario"]) for r in pairs}
    check(len(pair_keys) == 44, "all four scenarios for 11 feasible pairs are present")
    for r in pairs:
        expected = sum(Decimal(str(single[(c, r["scenario"])] ["incremental_contribution_eur"])) for c in r["countries"])
        check(money(expected) == Decimal(str(r["incremental_contribution_eur"])), f"pair {r['countries']} {r['scenario']} is additive")
        check(r["capex_eur"] <= 450000 and r["fte"] <= 7, f"pair {r['countries']} respects budgets")
    options_out = metrics["option_comparison"]
    winner = max(options_out, key=lambda r: r["base"])
    check(winner["label"] == "CZE+ESP", "Czechia + Spain is the computed base-case leader")
    check(metrics["recommendation"]["countries"] == ["CZE", "ESP"], "recommendation matches the base-case leader")
    risk = next(r for r in options_out if r["label"] == "NLD+ESP")
    check(risk["stress"] > next(r for r in options_out if r["label"] == "CZE+ESP")["stress"], "risk-sensitive NLD + ESP alternative is higher in stress")

    # Workbook structure and calculated reconciliation values.
    wb = load_workbook(DEL / "meridian_analysis.xlsx", data_only=False)
    check(len(wb.sheetnames) == 16, "workbook contains 16 documented sheets")
    check(wb["Monthly"].max_row == 73 and wb["Countries"].max_row == 7, "workbook monthly and annual table dimensions")
    check(wb["Order Ledger"].max_row == 1255, "workbook order ledger contains one row per eligible shipment")
    check(len(wb["Decision Charts"]._charts) == 4, "workbook includes four native charts")
    check(wb["Sensitivity"].max_row > 10, "workbook includes sensitivity ranges, results and flip conditions")
    check(all(wb["Reconciliation"].cell(row, 6).value == "PASS" for row in range(2, 56)), "all 54 workbook reconciliation cells pass")

    # PDFs are valid, paginated, text-bearing browser print output; screenshots were visually reviewed.
    for filename, expected_pages, required_text in [
        ("executive_report.pdf", 7, "Stage a Czechia + Spain"),
        ("board_presentation.pdf", 7, "STAGE CZECHIA + SPAIN"),
    ]:
        reader = PdfReader(str(DEL / filename))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        check(len(reader.pages) == expected_pages, f"{filename} has {expected_pages} pages")
        check(required_text.lower() in text.lower(), f"{filename} contains its recommendation text")
    for prefix, expected_size in [("report", (2248, 1588)), ("slide", (2560, 1440))]:
        directory = DEL / "previews" / ("report" if prefix == "report" else "deck")
        images = sorted(directory.glob(f"{prefix}-*.png"))
        check(len(images) == 7, f"{prefix} has seven rendered visual previews")
        with Image.open(images[0]) as im:
            check(im.size == expected_size, f"{prefix} preview raster size is {expected_size}")

    check((DEL / "executive_report.html").is_file() and (DEL / "board_presentation.html").is_file(), "editable HTML print masters are present")
    print(f"PASS all {CHECKS} independent provenance, per-order accounting, scenario, workbook, PDF and preview checks.")


if __name__ == "__main__":
    main()

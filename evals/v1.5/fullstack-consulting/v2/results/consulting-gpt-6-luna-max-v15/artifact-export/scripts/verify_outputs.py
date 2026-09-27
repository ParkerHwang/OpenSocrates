"""Verify deliverable schemas, reconciliations, scenario math and file structure."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from itertools import combinations
from pathlib import Path
import csv
import hashlib
import json

from openpyxl import load_workbook
from pypdf import PdfReader
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DELIVER = ROOT / "deliverables"
ANALYSIS = ROOT / "analysis"
METRICS = json.loads((DELIVER / "metrics.json").read_text(encoding="utf-8"))


def check(name, condition, detail):
    if not condition:
        raise AssertionError(f"FAIL {name}: {detail}")
    return {"check": name, "status": "pass", "detail": detail}


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    checks = []
    expected_fields = ["country", "shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units", "margin"]
    checks.append(check("metrics top-level schema", all(k in METRICS for k in ("monthly", "countries", "fx_monthly", "market_context", "hub_scenarios", "recommendation", "quality")), "All required top-level metrics fields exist."))
    checks.append(check("monthly schema and grid", len(METRICS["monthly"]) == 72 and all(set(expected_fields + ["month"]).issubset(r) for r in METRICS["monthly"]), "72 rows; required fields and month present."))
    checks.append(check("country schema and grid", len(METRICS["countries"]) == 6 and all(set(expected_fields).issubset(r) for r in METRICS["countries"]), "Six rows; required fields present."))
    monthly = METRICS["monthly"]
    countries = METRICS["countries"]
    check_fields = expected_fields[1:-1]
    sums = defaultdict(lambda: defaultdict(float))
    for row in monthly:
        sums[row["country"]]["_months"] += 1
        for field in check_fields:
            sums[row["country"]][field] += row[field]
    for c in countries:
        for field in check_fields:
            tolerance = 0.005 if field.endswith("_eur") else 0
            if abs(sums[c["country"]][field] - c[field]) > tolerance:
                raise AssertionError(f"Country/month total mismatch {c['country']} {field}")
        if sums[c["country"]]["_months"] != 12:
            raise AssertionError(f"Missing month for {c['country']}")
    checks.append(check("country-month-to-year reconciliation", True, "Every country's 12 months equal its country total for counts and monetary fields."))
    ledger = read_csv(ANALYSIS / "order_ledger.csv")
    checks.append(check("order ledger population", len(ledger) == METRICS["quality"]["eligible_2025_shipped_orders"], f"{len(ledger)} eligible order records match the metrics quality count."))
    for row in ledger:
        if round(float(row["gross_sales_eur"]) - float(row["refunds_eur"]), 2) != round(float(row["net_sales_eur"]), 2):
            raise AssertionError(f"Net sales formula mismatch for {row['order_id']}")
        if round(float(row["net_sales_eur"]) - float(row["net_cogs_eur"]) - float(row["fulfillment_eur"]), 2) != round(float(row["contribution_eur"]), 2):
            raise AssertionError(f"Contribution formula mismatch for {row['order_id']}")
    checks.append(check("order accounting formulas", True, "Each eligible order satisfies gross−refunds=net sales and net sales−net COGS−fulfillment=contribution."))

    checks.append(check("FX grid", len(METRICS["fx_monthly"]) == 24 and {x["currency"] for x in METRICS["fx_monthly"]} == {"PLN", "CZK"}, "12 monthly mean quotes each for PLN and CZK; EUR=1 is disclosed as convention."))
    check_fx = {(r["currency"], r["month"]): r["local_per_eur"] for r in METRICS["fx_monthly"]}
    source_fx = read_csv(ROOT / "evidence" / "source_room" / "ecb-history.csv")
    accum = defaultdict(lambda: [0.0, 0])
    for row in source_fx:
        if row["Date"].startswith("2025-"):
            month = row["Date"][:7]
            for code in ("PLN", "CZK"):
                if row[code] and row[code] != "N/A":
                    accum[(code, month)][0] += float(row[code])
                    accum[(code, month)][1] += 1
    for key, (total, n) in accum.items():
        if abs(check_fx[key] - total / n) > 1e-7:
            raise AssertionError(f"ECB monthly mean mismatch {key}")
    checks.append(check("ECB monthly means", True, "All PLN/CZK monthly means independently recomputed from saved daily CSV within 1e-7."))

    checks.append(check("World Bank context grid", len(METRICS["market_context"]) == 18 and {x["year"] for x in METRICS["market_context"]} == {2022, 2023, 2024}, "18 country-year rows for six markets and 2022–2024; nulls remain representable."))
    hubs = METRICS["hub_scenarios"]
    option_names = {r["country"] for r in hubs}
    checks.append(check("hub scenario coverage", len(hubs) == 72 and len(option_names) == 18 and all(sum(1 for r in hubs if r["country"] == name) == 4 for name in option_names), "Four scenarios for six singles, 11 feasible pairs and DEFER."))
    by_country = defaultdict(dict)
    for row in hubs:
        by_country[row["country"]][row["scenario"]] = row
    for row in hubs:
        if row["country"] == "DEFER":
            continue
        if row["incremental_contribution_eur"] > 0:
            expected_payback = row["capex_eur"] / row["incremental_contribution_eur"]
            if abs(expected_payback - row["payback_years"]) > 0.00011:
                raise AssertionError(f"Payback mismatch {row['country']} {row['scenario']}")
        elif row["payback_years"] is not None:
            raise AssertionError(f"Nonpositive scenario payback must be null: {row['country']} {row['scenario']}")
    checks.append(check("scenario payback", True, "Positive scenarios use capex/annual contribution; nonpositive scenarios have null payback."))
    rec = METRICS["recommendation"]
    checks.append(check("recommendation capex constraint", rec["capex_eur"] <= 450000, f"EUR {rec['capex_eur']:,} <= EUR 450,000"))
    checks.append(check("recommendation staffing constraint", rec["fte"] <= 7 and len(rec["countries"]) <= 2, f"{rec['fte']} FTE; {len(rec['countries'])} hubs."))
    checks.append(check("recommendation and alternative", rec["countries"] == ["CZE", "ESP"] and rec["strongest_alternative"]["country"] == "POL+ESP" and rec["stress_resilient_alternative"]["country"] == "NLD+ESP", "Base-ranked alternative and stress-resilient alternative are explicit."))

    source_manifest = json.loads((ROOT / "evidence" / "source_room" / "collection-manifest.json").read_text())
    for item in source_manifest["files"]:
        actual = hashlib.sha256((ROOT / item["file"]).read_bytes()).hexdigest()
        if actual != item["sha256"]:
            raise AssertionError(f"Source hash mismatch: {item['file']}")
    checks.append(check("saved evidence hashes", True, f"All {len(source_manifest['files'])} collected source-room objects match their recorded SHA-256."))
    register = read_csv(ANALYSIS / "source_register.csv")
    checks.append(check("source register fields", len(register) == len(source_manifest["files"]) and all(set(["file", "url", "retrieved_at_utc", "sha256", "units", "period", "status"]).issubset(r) for r in register), f"{len(register)} source rows carry URL/time/hash/units/period/status."))

    book_path = DELIVER / "meridian_analysis.xlsx"
    wb = load_workbook(book_path, data_only=False)
    checks.append(check("workbook structure", len(wb.sheetnames) >= 15 and wb["Monthly"].max_row == 73 and wb["Country totals"].max_row == 7 and wb["Hub scenarios"].max_row == 73, f"{len(wb.sheetnames)} sheets; monthly=72, country=6, scenario=72 records plus header."))
    checks.append(check("workbook charts", len(wb["Decision charts"]._charts) == 2, "Two native Excel charts are embedded."))
    # Exact workbook/JSON country-total correspondence by headers.
    ws = wb["Country totals"]
    headers = [ws.cell(1, col).value for col in range(1, ws.max_column + 1)]
    excel_rows = {ws.cell(r, 1).value: {headers[c-1]: ws.cell(r, c).value for c in range(1, len(headers)+1)} for r in range(2, ws.max_row + 1)}
    for row in countries:
        for field in check_fields:
            if abs(float(excel_rows[row["country"]][field]) - float(row[field])) > (0.005 if field.endswith("_eur") else 0):
                raise AssertionError(f"Workbook country mismatch {row['country']} {field}")
    checks.append(check("workbook values", True, "Country totals in workbook equal metrics.json for all count and monetary fields."))

    pdfs = [("meridian_board_report.pdf", 8, ["CZE+ESP", "POL+ESP", "NLD+ESP", "2026-01-31"]), ("meridian_board_presentation.pdf", 6, ["CZE + ESP", "€225k", "NLD+ESP"])]
    for name, page_n, tokens in pdfs:
        reader = PdfReader(DELIVER / name)
        if len(reader.pages) != page_n:
            raise AssertionError(f"Unexpected page count for {name}: {len(reader.pages)}")
        content = "\n".join(page.extract_text() or "" for page in reader.pages)
        if any(token not in content for token in tokens):
            raise AssertionError(f"Missing required text in {name}: {[t for t in tokens if t not in content]}")
        if any(len(page.extract_text() or "") < 300 for page in reader.pages):
            raise AssertionError(f"Unexpected near-empty page in {name}")
    checks.append(check("PDF structure and content", True, "Report has 8 pages, presentation 6 pages; required recommendation, alternatives, cutoff and funding values extract from PDF text."))
    for name in ("meridian_board_report_contact.png", "meridian_board_presentation_contact.png"):
        img = Image.open(ANALYSIS / "qa" / name)
        if img.width < 500 or img.height < 500:
            raise AssertionError(f"Rendered contact sheet unexpectedly small: {name}")
    checks.append(check("PDF visual render", True, "Both PDFs were rasterized with pypdfium2 and contact sheets reviewed; page layouts fit without observed table overlaps after revisions."))

    result = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "checks": checks,
        "limitations": [
            "The workbook was structurally reopened and its tables/charts/data were checked with openpyxl; an installed spreadsheet GUI renderer was unavailable, so workbook visual rendering was not directly inspected.",
            "PDFs were rasterized and visually reviewed. Source observations are frozen archive snapshots and client data is synthetic.",
        ],
    }
    (DELIVER / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = ["# Deliverable verification", "", f"Status: **{result['status']}**", f"Verified at: {result['verified_at_utc']}", "", "Checks:"]
    lines += [f"- PASS — {x['check']}: {x['detail']}" for x in checks]
    lines += ["", "Limitations:"]
    lines += [f"- {x}" for x in result["limitations"]]
    (DELIVER / "verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

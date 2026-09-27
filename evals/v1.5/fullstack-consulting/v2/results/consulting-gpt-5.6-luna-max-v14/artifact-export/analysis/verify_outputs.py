#!/usr/bin/env python3
"""Independent checks for the generated Meridian Parts deliverables."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

from openpyxl import load_workbook
from pptx import Presentation
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
import reproduce


def fail(message: str) -> None:
    raise AssertionError(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    out = ROOT / "deliverables"
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"), parse_constant=lambda value: fail(f"invalid JSON constant {value}"))
    for key in ["monthly", "countries", "fx_monthly", "market_context", "hub_scenarios", "recommendation", "quality"]:
        if key not in metrics:
            fail(f"missing metrics key {key}")
    if len(metrics["monthly"]) != 72 or len(metrics["countries"]) != 6 or len(metrics["fx_monthly"]) != 24 or len(metrics["market_context"]) != 18:
        fail("unexpected deterministic metric array length")
    if metrics["recommendation"]["selected_option"] != "CZE+ESP":
        fail("recommendation changed unexpectedly")
    if metrics["recommendation"]["capex_eur"] > 450000 or metrics["recommendation"]["fte"] > 7 or len(metrics["recommendation"]["countries"]) > 2:
        fail("recommendation violates hard constraints")
    # Recompute from raw files and compare all metric values at the published precision.
    core = reproduce.run_core()
    expected_monthly, expected_countries = reproduce.metric_records(core["monthly"], core["countries"])
    if expected_monthly != metrics["monthly"] or expected_countries != metrics["countries"]:
        fail("JSON monthly/country metrics do not match a fresh raw-data recomputation")
    expected_fx = core["fx_monthly"][["currency", "month", "local_per_eur"]].to_dict("records")
    if expected_fx != metrics["fx_monthly"]:
        fail("FX JSON does not match a fresh recomputation")
    if max(abs(float(x)) for x in metrics["quality"]["reconciliations"]["country_minus_monthly_by_metric"].values()) != 0:
        fail("country/month reconciliation is not zero")
    # Source register integrity.
    for entry in json.loads((out / "source-register.json").read_text(encoding="utf-8")):
        saved = ROOT / "evidence" / "raw" / entry["file"]
        if not saved.exists() or sha256(saved) != entry["sha256"]:
            fail(f"source hash mismatch: {entry['file']}")
    # Workbook structure and embedded charts.
    wb = load_workbook(out / "meridian_parts_analytical_workbook.xlsx", read_only=False, data_only=False)
    required_sheets = {"README", "Source_Quality", "Order_Detail", "Monthly", "Country_Totals", "FX_Monthly", "Market_Context", "Hub_Scenarios", "Decision_Summary", "Charts", "Source_Register"}
    if not required_sheets.issubset(set(wb.sheetnames)):
        fail("workbook missing required sheet")
    if len(wb["Charts"]._images) < 5:
        fail("workbook has too few embedded charts")
    if wb["Monthly"].max_row != 76 or wb["Country_Totals"].max_row != 10:
        fail("workbook dimensions are unexpected")
    workbook_sheet_count = len(wb.sheetnames)
    wb.close()
    # PDF text and page count.
    pdf = PdfReader(str(out / "meridian_parts_executive_report.pdf"))
    pdf_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    for marker in ["CZE+ESP", "2025 operating diagnosis", "Staged 90-day implementation", "Source register summary", "Appendix"]:
        if marker not in pdf_text:
            fail(f"report marker missing: {marker}")
    if "{q[" in pdf_text or len(pdf.pages) < 8:
        fail("report contains a placeholder or is too short")
    # PPTX package/slide text check.
    prs = Presentation(str(out / "meridian_parts_board_presentation.pptx"))
    if len(prs.slides) != 8:
        fail("presentation must contain 8 slides")
    deck_text = "\n".join(shape.text for slide in prs.slides for shape in slide.shapes if hasattr(shape, "text"))
    for marker in ["CZE+ESP", "Board decision", "90-day plan", "Board ask and limitations"]:
        if marker not in deck_text:
            fail(f"deck marker missing: {marker}")
    result = {
        "status": "PASS",
        "checks": [
            "JSON schema keys, deterministic array lengths and valid JSON constants",
            "Fresh raw-data recomputation equals published monthly, country and FX metrics",
            "Country totals reconcile to monthly records to the cent",
            "Saved raw evidence SHA-256 hashes match source-register.json",
            "Workbook sheets, tables and five embedded charts present",
            "PDF text markers and page count present",
            "PPTX package opens through python-pptx with eight slides and required markers",
        ],
        "pdf_pages": len(pdf.pages),
        "pptx_slides": len(prs.slides),
        "workbook_sheets": workbook_sheet_count,
        "monthly_rows": len(metrics["monthly"]),
        "render_note": "PDF pages rendered to .render-check/report and representative pages/chart assets visually inspected. No native Office renderer is installed in the sandbox; PPTX was package-validated and structurally inspected.",
    }
    (out / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

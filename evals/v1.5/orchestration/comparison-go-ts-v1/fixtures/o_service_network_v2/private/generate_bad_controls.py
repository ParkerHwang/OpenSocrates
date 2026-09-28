#!/usr/bin/env python3
"""Versioned, deliberately wrong controls; never stage to a subject role."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "private/controls"
GOOD = ROOT / "good"
BAD = ROOT / "bad"


def save(label: str, name: str, content: str) -> None:
    target = BAD / label / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


def replace_one(text: str, old: str, new: str) -> str:
    assert text.count(old) >= 1, old
    return text.replace(old, new, 1)


def main() -> None:
    good = (GOOD / "analysis.go").read_text()
    policy_old = "at(row.Effective).After(at(best.Effective))||(row.Effective==best.Effective&&row.Revision>best.Revision)"
    save("latest_vs_max_policy", "analysis.go", replace_one(good, policy_old, "row.Hours>best.Hours||(row.Hours==best.Hours&&row.Revision>best.Revision)"))
    before_rate, rate_func = good.split("func effectiveRate", 1)
    assert policy_old in rate_func
    save("latest_vs_max_rate", "analysis.go", before_rate + "func effectiveRate" + replace_one(rate_func, policy_old, "row.Cents>best.Cents||(row.Cents==best.Cents&&row.Revision>best.Revision)"))
    product = replace_one(good, "jobParts:=0\n  for _,line:=range event.Parts{", "jobParts:=0;sumQty,sumUnit:=0,0\n  for _,line:=range event.Parts{")
    product = replace_one(product, "jobParts+=*line.Qty*rate.Cents;unit:=rate.Cents", "sumQty+=*line.Qty;sumUnit+=rate.Cents;unit:=rate.Cents")
    product = replace_one(product, "knownParts+=jobParts;jobs=append", "jobParts=sumQty*sumUnit;knownParts+=jobParts;jobs=append")
    save("product_of_sums", "analysis.go", product)
    missing = good.replace("unknownCredit++", "unknownCredit+=0").replace("unknownPartLines++", "unknownPartLines+=0").replace("unknownLabor++", "unknownLabor+=0").replace("unknownPartJobs[order.ID]=true", "delete(unknownPartJobs,order.ID)")
    save("missing_as_zero", "analysis.go", missing)
    save("creation_month_labor", "analysis.go", replace_one(good, "month:=completion[:7]", "month:=order.CreatedAt[:7]"))
    save("wrong_event_id_tie", "analysis.go", replace_one(good, "event.ID>old.ID", "event.ID<old.ID"))
    save("future_as_current", "analysis.go", replace_one(good, "if at(event.RecordedAt).After(at(manifest.DecisionAt)){future++;continue}", "if at(event.RecordedAt).After(at(manifest.DecisionAt)){future++}"))
    save("omit_shared_pairs", "analysis.go", replace_one(good, "fixedShared+=len(manifest.PeriodMonths)*monthly", "fixedShared+=0*monthly"))
    save("wrong_capacity_sensitivity_site", "analysis.go", replace_one(good, 'westScenario&&site=="west"&&month=="2026-06"', 'westScenario&&site=="south"&&month=="2026-06"'))
    save("unknown_capacity_as_feasible", "analysis.go", replace_one(good, 'unknownWork[site+"|"+month]>0||used[site+"|"+month]>available', 'used[site+"|"+month]>available'))
    save("floor_per_job_credit", "analysis.go", replace_one(good, 'jobCredit=rounded(*event.ChargeCents*policy.BPS,10000)', 'jobCredit=(*event.ChargeCents*policy.BPS)/10000'))
    save("floor_per_job_labor", "analysis.go", replace_one(good, 'jobLabor=rounded(*event.WorkMinutes*cap.Hourly,60)', 'jobLabor=(*event.WorkMinutes*cap.Hourly)/60'))
    memo = (GOOD / "memo.md").read_text()
    save("misbound_memo", "memo.md", replace_one(memo, "| /cost/known_labor_cents | 1584588 | orders-v2, events-initial-v2, events-corrections-v2, capacity-v2 |", "| /cost/known_labor_cents | 1584588 | rates-v2 |"))
    missing_row = next(line for line in memo.splitlines() if line.startswith("| /portfolios/east+west+north/coverage_ratio |"))
    save("missing_portfolio_row", "memo.md", memo.replace(missing_row + "\n", ""))
    save("ineligible_recommendation", "memo.md", replace_one(memo, "Recommendation: east+west+north", "Recommendation: north+south"))
    save("empty_criterion", "memo.md", replace_one(memo, "Criterion: Preserve substantially more observed assigned work than the cheaper eligible pairs, while retaining baseline capacity feasibility; accept the larger lower-bound period cost only with a west-June capacity contingency and a separate review of omitted southern work.", "Criterion:"))
    save("missing_risk_register", "memo.md", memo.split("## Risks and assumptions", 1)[0].rstrip() + "\n")
    source_register = json.loads((GOOD / "sources.json").read_text())
    for item in source_register:
        if item["id"] == "events-initial-v2":
            item["path"] = "../../private/oracle.py"
    save("source_path_traversal", "sources.json", json.dumps(source_register, indent=2) + "\n")


if __name__ == "__main__":
    main()

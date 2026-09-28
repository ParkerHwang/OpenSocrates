#!/usr/bin/env python3
"""O v2 no-model analysis/full controls with retained disposable copies."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def policy_factory(path: Path):
    spec = importlib.util.spec_from_file_location("comparison_policy", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.candidate_policy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--deps", type=Path, required=True)
    parser.add_argument("--policy-module", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    assert not run_root.exists()
    run_root.mkdir(parents=True)
    make_policy = policy_factory(args.policy_module.resolve())
    algorithm = {
        "latest_vs_max_policy", "latest_vs_max_rate", "product_of_sums", "missing_as_zero",
        "creation_month_labor", "wrong_event_id_tie", "future_as_current", "omit_shared_pairs", "wrong_capacity_sensitivity_site",
        "unknown_capacity_as_feasible", "floor_per_job_credit", "floor_per_job_labor",
    }
    memo = {
        "misbound_memo": "v2_memo_evidence",
        "missing_portfolio_row": "v2_memo_evidence",
        "ineligible_recommendation": "v2_memo_decision_record",
        "empty_criterion": "v2_memo_decision_record",
        "missing_risk_register": "v2_memo_structure",
    }
    targets = [("good_analysis", "analysis", None), ("good_full", "full", None), ("allowed_alternative", "full", None)]
    targets += [(name, "analysis", "v2_program_matches_oracle") for name in sorted(algorithm)]
    targets += [(name, "analysis", "v2_source_register") for name in ("source_path_traversal",)]
    targets += [(name, "full", target) for name, target in memo.items()]
    results = []
    isolation = None
    for label, scope, expected_rejection in targets:
        run = run_root / label
        copy = run / "candidate-copy"
        shutil.copytree(ROOT / "public/starter", copy)
        shutil.copytree(ROOT / "public/data", copy / "data")
        good = ROOT / "private/controls/good"
        for name in ("analysis.go", "metrics.json", "sources.json") + (("memo.md",) if scope == "full" else ()):
            shutil.copyfile(good / name, copy / name)
        if label == "allowed_alternative":
            shutil.copyfile(ROOT / "private/controls/alternative/memo.md", copy / "memo.md")
        if expected_rejection:
            for path in (ROOT / "private/controls/bad" / label).rglob("*"):
                if path.is_file():
                    target = copy / path.relative_to(ROOT / "private/controls/bad" / label)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
        (copy / ".eval-copy").write_text("disposable qualification copy\n")
        (run / "candidate-policy.sb").write_text(make_policy(run, args.deps.resolve()))
        command = ["/Applications/Xcode.app/Contents/Developer/usr/bin/python3", "-B", str(ROOT / "private/verify_external_v2.py"), "--candidate", str(copy), "--deps", str(args.deps.resolve()), "--candidate-policy", str(run / "candidate-policy.sb"), "--scope", scope]
        process = subprocess.run(command, capture_output=True, text=True, timeout=240)
        try:
            receipt = json.loads(process.stdout)
        except json.JSONDecodeError:
            receipt = {"passed": False, "checks": [], "error": "invalid verifier receipt"}
        (run / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        if label == "good_analysis":
            canary = subprocess.run(["/Applications/Xcode.app/Contents/Developer/usr/bin/python3", "-B", str(ROOT / "private/isolation_canary.py"), "--candidate", str(copy), "--policy", str(run / "candidate-policy.sb")], capture_output=True, text=True, timeout=30)
            isolation = json.loads(canary.stdout)
            (run / "isolation-canary.json").write_text(json.dumps(isolation, indent=2) + "\n")
        check_by_id = {item["id"]: item for item in receipt.get("checks", [])}
        built = check_by_id.get("v2_go_build_run", {}).get("passed") is True
        if expected_rejection is None:
            as_expected = process.returncode == 0 and receipt.get("passed") is True
        else:
            as_expected = process.returncode != 0 and receipt.get("passed") is False and check_by_id.get(expected_rejection, {}).get("passed") is False and built
        results.append({"control": label, "scope": scope, "expected": "pass" if expected_rejection is None else "reject:" + expected_rejection, "go_build_passed": built, "observed_pass": receipt.get("passed"), "as_expected": as_expected})
    summary = {"schema": "opensocrates.eval.v2-controls/1.0.0", "task": "O-v2", "passed": all(item["as_expected"] for item in results) and bool(isolation and isolation["passed"]), "controls": results, "isolation_canary": isolation, "meaning": "Good and deliberately wrong mechanical controls only; no subject model or semantic recommendation verdict."}
    args.receipt.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

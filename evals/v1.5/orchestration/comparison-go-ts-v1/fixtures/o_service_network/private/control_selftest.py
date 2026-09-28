#!/usr/bin/env python3
"""No-model good/bad oracle controls, with retained disposable copies."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT.parent


def load_policy(module_path: Path):
    spec = importlib.util.spec_from_file_location("comparison_policy", module_path)
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
    root = args.run_root.resolve()
    assert not root.exists()
    root.mkdir(parents=True)
    policy = load_policy(args.policy_module.resolve())
    targets = {
        "good": None,
        "latest_vs_max_policy": "o_program_matches_oracle",
        "latest_vs_max_rate": "o_program_matches_oracle",
        "missing_as_zero": "o_program_matches_oracle",
        "product_of_sums": "o_program_matches_oracle",
        "misbound_memo": "o_memo_evidence",
        "missing_criterion": "o_memo_decision_record",
        "missing_portfolio_comparison": "o_memo_evidence",
        "wrong_feasibility": "o_memo_evidence",
        "missing_as_zero_artifact": "o_oracle_metrics",
    }
    summaries = []
    isolation = None
    for label, rejected_check in targets.items():
        run = root / label
        candidate = run / "candidate-copy"
        shutil.copytree(ROOT / "public/starter", candidate)
        shutil.copytree(ROOT / "public/data", candidate / "data")
        for path in (ROOT / "private/controls/good").iterdir():
            shutil.copyfile(path, candidate / path.name)
        if label != "good":
            for path in (ROOT / "private/controls/bad" / label).rglob("*"):
                if path.is_file():
                    target = candidate / path.relative_to(ROOT / "private/controls/bad" / label)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
        (candidate / ".eval-copy").write_text("disposable qualification copy\n")
        (run / "candidate-policy.sb").write_text(policy(run, args.deps.resolve()))
        command = ["/Applications/Xcode.app/Contents/Developer/usr/bin/python3", "-B", str(FIXTURES / "verify_external.py"), "--task", "O", "--candidate", str(candidate), "--deps", str(args.deps.resolve()), "--candidate-policy", str(run / "candidate-policy.sb")]
        process = subprocess.run(command, capture_output=True, text=True, timeout=180)
        try:
            result = json.loads(process.stdout)
        except json.JSONDecodeError:
            result = {"passed": False, "checks": [], "error": "malformed verifier receipt"}
        (run / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
        if label == "good":
            canary = subprocess.run(["/Applications/Xcode.app/Contents/Developer/usr/bin/python3", "-B", str(ROOT / "private/isolation_canary.py"), "--candidate", str(candidate), "--policy", str(run / "candidate-policy.sb")], capture_output=True, text=True, timeout=30)
            isolation = json.loads(canary.stdout)
            (run / "isolation-canary.json").write_text(json.dumps(isolation, indent=2) + "\n")
        found = any(item["id"] == rejected_check and item["passed"] is False for item in result.get("checks", [])) if rejected_check else False
        accepted = process.returncode == 0 and result.get("passed") is True if label == "good" else process.returncode != 0 and result.get("passed") is False and found
        summaries.append({"control": label, "expected": "pass" if label == "good" else f"reject:{rejected_check}", "observed_pass": result.get("passed"), "target_check_rejected": found, "as_expected": accepted})
    summary = {"schema": "opensocrates.eval.control-selftest/1.0.0", "task": "O", "passed": all(item["as_expected"] for item in summaries) and bool(isolation and isolation["passed"]), "controls": summaries, "isolation_canary": isolation, "meaning": "Mechanical oracle controls only; no subject model or recommendation-quality judgment."}
    args.receipt.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

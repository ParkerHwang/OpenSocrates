#!/usr/bin/env python3
"""No-model IncidentOps controls with retained disposable copies."""
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


def overlay(source: Path, candidate: Path) -> None:
    for path in source.rglob("*"):
        if path.is_file():
            target = candidate / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


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
        "policy_max_delay": "s_effective_policy_handover",
        "tenant_leak": "s_tenant_isolation",
        "obsolete_outbox": "s_late_fold_atomicity",
        "normal_sync": "s_active_durability",
        "form_reload": "s_browser_network_ui",
        "replay_as_new": "s_replay_conflict",
    }
    summaries = []
    for label, rejected_check in targets.items():
        run = root / label
        candidate = run / "candidate-copy"
        shutil.copytree(ROOT / "public/starter", candidate)
        overlay(ROOT / "private/controls/good", candidate)
        if label != "good":
            overlay(ROOT / "private/controls/bad" / label, candidate)
        (candidate / ".eval-copy").write_text("disposable qualification copy\n")
        (run / "candidate-policy.sb").write_text(policy(run, args.deps.resolve()))
        command = ["/Applications/Xcode.app/Contents/Developer/usr/bin/python3", "-B", str(FIXTURES / "verify_external.py"), "--task", "S", "--candidate", str(candidate), "--deps", str(args.deps.resolve()), "--candidate-policy", str(run / "candidate-policy.sb"), "--quick"]
        process = subprocess.run(command, capture_output=True, text=True, timeout=180)
        try:
            result = json.loads(process.stdout)
        except json.JSONDecodeError:
            result = {"passed": False, "checks": [], "error": "malformed verifier receipt"}
        (run / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
        target = next((item for item in result.get("checks", []) if item["id"] == rejected_check), None) if rejected_check else None
        found = bool(target and target.get("passed") is False and target.get("status") != "unassessable")
        accepted = process.returncode == 0 and result.get("passed") is True if label == "good" else process.returncode != 0 and result.get("passed") is False and found
        summaries.append({"control": label, "expected": "pass" if label == "good" else f"reject:{rejected_check}", "observed_pass": result.get("passed"), "target_check_rejected": found, "as_expected": accepted})
    summary = {"schema": "opensocrates.eval.control-selftest/1.0.0", "task": "S", "scope": "functional_prep_only", "passed": all(item["as_expected"] for item in summaries), "controls": summaries, "meaning": "Mechanical good/bad controls only; full workload is independently required."}
    args.receipt.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

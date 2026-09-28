#!/usr/bin/env python3
"""Versioned O v2 outer grader. Trusted Python; only candidate Go is sandboxed.

`analysis` grades an exact analysis artifact version without a document. `full`
grades a document version only with its actually qualified analysis dependency.
The runner, not this script, binds and records that dependency lineage.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public/data"
DATA_NAMES = ("manifest.json", "orders.json", "events_initial.json", "events_corrections.json", "sla_policies.json", "supplier_rates.json", "capacity.json", "shared_costs.json", "portfolios.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add(checks: list[dict], name: str, passed: bool, detail: str = "") -> None:
    checks.append({"id": name, "passed": bool(passed), "detail": detail[:180]})


def load_oracle():
    path = ROOT / "private/oracle.py"
    spec = importlib.util.spec_from_file_location("v2_oracle", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def child_env(candidate: Path, deps: Path) -> dict:
    for name in (".eval-home", ".eval-tmp", ".eval-go-build", ".eval-go-path", ".eval-clang-cache"):
        (candidate / name).mkdir(exist_ok=True)
    return {
        "PATH": "/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(candidate / ".eval-home"), "TMPDIR": str(candidate / ".eval-tmp"), "GOTMPDIR": str(candidate / ".eval-tmp"),
        "GOCACHE": os.environ.get("GOCACHE", str(candidate / ".eval-go-build")),
        "GOMODCACHE": str(deps / "go-modcache"), "GOPATH": str(candidate / ".eval-go-path"),
        "GOTOOLCHAIN": "local", "GOPROXY": "off", "GOSUMDB": "off", "CGO_ENABLED": "1",
        "CC": "/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang",
        "DEVELOPER_DIR": "/Applications/Xcode.app/Contents/Developer",
        "SDKROOT": "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk",
        "CLANG_MODULE_CACHE_PATH": str(candidate / ".eval-clang-cache"),
    }


def pointer(value: dict, path: str):
    for segment in path.lstrip("/").split("/"):
        value = value[segment.replace("~1", "/").replace("~0", "~")]
    return value


def parse_value(text: str, expected) -> bool:
    text = text.strip()
    if isinstance(expected, list):
        try:
            return json.loads(text) == expected
        except json.JSONDecodeError:
            return False
    if isinstance(expected, bool):
        return text.lower() == str(expected).lower()
    return text.replace(",", "") == str(expected)


def memo_checks(candidate: Path, expected: dict, register: list[dict], checks: list[dict]) -> None:
    memo_path = candidate / "memo.md"
    if not memo_path.is_file():
        add(checks, "v2_memo_evidence", False, "memo absent")
        add(checks, "v2_memo_decision_record", False, "memo absent")
        add(checks, "v2_memo_structure", False, "memo absent")
        return
    memo = memo_path.read_text()
    known = {item["id"] for item in register}
    event_sources = {"orders-v2", "events-initial-v2", "events-corrections-v2"}
    required = {
        "/selection/orders", "/selection/corrected", "/selection/future_ignored", "/selection/cancelled", "/selection/completed", "/backlog",
        "/sla/eligible", "/sla/on_time", "/sla/attainment", "/sla/unknown_credit_jobs", "/sla/zero_charge_completed_jobs",
        "/cost/known_part_cents", "/cost/unknown_part_lines", "/cost/unknown_part_jobs", "/cost/known_labor_cents", "/cost/unknown_labor_jobs", "/cost/known_credit_cents",
        "/sensitivity/relay_plus_10_known_part_cents", "/sensitivity/west_june_available_after_15pct", "/sensitivity/changed_decision_eligibility",
    }
    fields = ("covered_completed_jobs", "coverage_ratio", "period_cost_lower_bound_cents", "capacity_feasible", "decision_eligible")
    required |= {f"/portfolios/{name}/{field}" for name in expected["portfolios"] for field in fields}
    sources_required = {
        "/selection/orders": {"orders-v2"},
        "/selection/corrected": {"events-initial-v2", "events-corrections-v2"},
        "/selection/future_ignored": {"events-corrections-v2", "manifest-v2"},
        "/backlog": event_sources,
        "/sla/attainment": event_sources | {"sla-v2"},
        "/sla/unknown_credit_jobs": event_sources | {"sla-v2"},
        "/cost/known_part_cents": event_sources | {"rates-v2"},
        "/cost/known_labor_cents": event_sources | {"capacity-v2"},
        "/cost/known_credit_cents": event_sources | {"sla-v2"},
        "/capacity/south/2026-05/unknown_work_jobs": event_sources | {"capacity-v2"},
        "/capacity/west/2026-06/available_minutes": {"capacity-v2"},
        "/capacity/west/2026-06/used_known_minutes": event_sources | {"capacity-v2"},
        "/sensitivity/relay_plus_10_known_part_cents": event_sources | {"rates-v2"},
        "/sensitivity/west_june_available_after_15pct": {"capacity-v2"},
        "/sensitivity/changed_decision_eligibility": event_sources | {"capacity-v2", "portfolios-v2", "manifest-v2"},
    }
    for name in expected["portfolios"]:
        prefix = f"/portfolios/{name}/"
        sources_required[prefix + "covered_completed_jobs"] = event_sources | {"portfolios-v2"}
        sources_required[prefix + "coverage_ratio"] = event_sources | {"portfolios-v2"}
        sources_required[prefix + "period_cost_lower_bound_cents"] = event_sources | {"sla-v2", "rates-v2", "capacity-v2", "shared-v2", "portfolios-v2", "manifest-v2"}
        sources_required[prefix + "capacity_feasible"] = event_sources | {"capacity-v2", "portfolios-v2"}
        sources_required[prefix + "decision_eligible"] = event_sources | {"capacity-v2", "portfolios-v2", "manifest-v2"}
    found = set()
    valid = True
    for path, text_value, refs in re.findall(r"(?m)^\|\s*(/[^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", memo):
        path = path.strip()
        try:
            actual = pointer(expected, path)
            citations = {item.strip() for item in refs.split(",") if item.strip()}
            valid &= parse_value(text_value, actual) and bool(citations) and citations <= known and sources_required.get(path, set()) <= citations
            found.add(path)
        except (KeyError, TypeError, ValueError):
            valid = False
    add(checks, "v2_memo_evidence", valid and required <= found, f"valid_rows={valid}; required={len(required & found)}/{len(required)}")
    recommendation = re.search(r"(?mi)^Recommendation:[ \t]*([a-z+]+)[ \t]*$", memo)
    criterion = re.search(r"(?mi)^Criterion:[ \t]*([^\r\n]*)$", memo)
    uncertainty = re.search(r"(?mi)^Uncertainty:[ \t]*([^\r\n]*)$", memo)
    chosen = recommendation.group(1).lower() if recommendation else None
    supported = bool(chosen in expected["portfolios"] and expected["portfolios"][chosen]["decision_eligible"] and criterion and criterion.group(1).strip() and uncertainty and uncertainty.group(1).strip())
    lower = memo.lower()
    add(checks, "v2_memo_decision_record", supported, f"eligible_option={chosen}; nonempty criterion/uncertainty; narrative reviewed separately")
    has_plan = bool(re.search(r"operating plan|action plan|next steps|implementation plan", lower))
    has_register = "risk" in lower and "assumption" in lower
    add(checks, "v2_memo_structure", has_plan and has_register, "plan and risk/assumption material present; narrative quality reviewed separately")


def qualify(candidate: Path, deps: Path, policy: Path, scope: str) -> dict:
    checks: list[dict] = []
    frozen = {name: sha(DATA / name) for name in DATA_NAMES}
    staged = {name: sha(candidate / "data" / name) for name in DATA_NAMES}
    add(checks, "v2_frozen_input_bytes", staged == frozen, "all nine source files match frozen public bytes")
    try:
        metrics = json.loads((candidate / "metrics.json").read_text())
        sources = json.loads((candidate / "sources.json").read_text())
        assert isinstance(metrics, dict) and isinstance(sources, list)
        add(checks, "v2_artifact_json", True, "metric and source-register JSON parse")
    except (OSError, json.JSONDecodeError, AssertionError):
        add(checks, "v2_artifact_json", False, "metric or register absent/invalid")
        return {"scope": scope, "passed": False, "checks": checks, "limitations": ["No numeric conclusion from unparsable artifacts."]}
    locked_names = ["analysis.go", "metrics.json"] + (["memo.md"] if scope == "full" else [])
    before = {name: sha(candidate / name) for name in locked_names if (candidate / name).is_file()}
    generated = candidate / ".eval-generated-metrics.json"
    if generated.exists():
        add(checks, "v2_fresh_generated_path", False, "copy already contains generated output")
        return {"scope": scope, "passed": False, "checks": checks, "limitations": []}
    env = child_env(candidate, deps)
    command = ["/usr/bin/sandbox-exec", "-f", str(policy), "/usr/local/go/bin/go", "run", "analysis.go", "-data", "data", "-out", str(generated)]
    try:
        process = subprocess.run(command, cwd=candidate, env=env, capture_output=True, timeout=180)
        add(checks, "v2_go_build_run", process.returncode == 0, f"exit={process.returncode}")
        produced = json.loads(generated.read_text()) if process.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        add(checks, "v2_go_build_run", False, type(exc).__name__)
        produced = None
    add(checks, "v2_locked_source_integrity", staged == {name: sha(candidate / "data" / name) for name in DATA_NAMES} and before == {name: sha(candidate / name) for name in locked_names if (candidate / name).is_file()}, "candidate run did not change frozen inputs or locked artifacts")
    oracle = load_oracle()
    expected, expected_register = oracle.expected(DATA)
    add(checks, "v2_oracle_metrics", metrics == expected, "independent private recomputation")
    add(checks, "v2_program_matches_artifact", produced == metrics, "exact generated-versus-committed metrics")
    add(checks, "v2_program_matches_oracle", produced == expected, "generated metrics versus private answer key")
    try:
        current_sources = json.loads((candidate / "sources.json").read_text())
        match = sorted(sources, key=lambda item: item["id"]) == sorted(expected_register, key=lambda item: item["id"]) == sorted(current_sources, key=lambda item: item["id"])
    except (KeyError, TypeError, json.JSONDecodeError):
        match = False
    add(checks, "v2_source_register", match, "all nine IDs, paths and byte digests")
    if scope == "full":
        memo_checks(candidate, expected, expected_register, checks)
    return {"scope": scope, "passed": all(item["passed"] for item in checks), "checks": checks, "limitations": (["Recommendation narrative and operational feasibility still require independent semantic review."] if scope == "full" else [])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--deps", type=Path, required=True)
    parser.add_argument("--candidate-policy", type=Path, required=True)
    parser.add_argument("--scope", choices=("analysis", "full"), default="full")
    args = parser.parse_args()
    candidate, deps, policy = args.candidate.resolve(), args.deps.resolve(), args.candidate_policy.resolve()
    if not candidate.is_dir() or not (candidate / ".eval-copy").is_file() or ROOT in candidate.parents or not deps.is_dir() or not policy.is_file():
        result = {"scope": args.scope, "passed": False, "checks": [], "error": "marked disposable copy, pinned deps and strict child policy required"}
    else:
        try:
            result = qualify(candidate, deps, policy, args.scope)
        except Exception as exc:
            result = {"scope": args.scope, "passed": False, "checks": [], "error": "verifier_error:" + type(exc).__name__}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

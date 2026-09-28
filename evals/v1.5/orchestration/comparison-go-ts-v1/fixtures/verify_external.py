#!/usr/bin/env python3
"""Outer, non-native qualification in an isolated disposable copy.

Run only under the runner's copy-scoped filesystem and loopback network wrapper.
Private oracles stay at this fixture path and are never staged for subjects.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def emit(task: str, checks: list[dict], *, error: str | None = None, performance: dict | None = None, quick: bool = False) -> int:
    ok = all(check["passed"] for check in checks) and error is None
    limits = ["Document recommendation quality and operational feasibility require an explicit independent semantic review."] if task == "O" else []
    if any(item.get("status") == "unassessable" for item in checks):
        limits.append("At least one external integration obligation is unassessable under the locked sandbox; do not attribute it to candidate quality.")
    print(json.dumps({"task": task, "passed": ok, "checks": checks, "error": error, "limitations": limits, "performance": performance, "qualification_scope": "functional_prep_only" if quick else "full_external"}, sort_keys=True))
    return 0 if ok else 1


def check(checks: list[dict], name: str, passed: bool, detail: str = "") -> None:
    checks.append({"id": name, "passed": bool(passed), "detail": detail[:200]})


def load_oracle(path: Path):
    spec = importlib.util.spec_from_file_location("private_oracle", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_o(candidate: Path, deps: Path, policy: Path) -> list[dict]:
    checks: list[dict] = []
    frozen_data = ROOT / "o_service_network/public/data"
    data_names = ("manifest.json", "orders.json", "events.json", "sla_policies.json", "capacity.json", "supplier_rates.json", "shared_costs.json")
    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    staged_before = {name: sha(candidate / "data" / name) for name in data_names}
    frozen_hashes = {name: sha(frozen_data / name) for name in data_names}
    check(checks, "o_frozen_input_bytes", staged_before == frozen_hashes, "candidate data room matches frozen public sources")
    try:
        committed_metrics = json.loads((candidate / "metrics.json").read_text())
        committed_sources = json.loads((candidate / "sources.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        check(checks, "o_artifact_json", False, type(exc).__name__)
        return checks
    locked_files = [candidate / name for name in ("analysis.go", "metrics.json", "sources.json", "memo.md")]
    locked_before = {str(path): sha(path) for path in locked_files if path.is_file()}
    generated = candidate / ".external-generated-metrics.json"
    for directory in (candidate / ".eval-home", candidate / ".eval-tmp", candidate / ".eval-go-build", candidate / ".eval-go-path", candidate / ".eval-clang-cache"):
        directory.mkdir(exist_ok=True)
    env = {
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
    try:
        process = subprocess.run(["/usr/bin/sandbox-exec", "-f", str(policy), "/usr/local/go/bin/go", "run", "analysis.go", "-data", "data", "-out", str(generated)], cwd=candidate, env=env, capture_output=True, timeout=120)
        check(checks, "o_go_build_run", process.returncode == 0, f"exit={process.returncode}")
        if process.returncode == 0:
            produced = json.loads(generated.read_text())
            check(checks, "o_program_matches_artifact", produced == committed_metrics, "exact staged output")
        else:
            check(checks, "o_program_matches_artifact", False, "program did not complete")
            produced = None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        check(checks, "o_go_build_run", False, type(exc).__name__)
        produced = None
    check(checks, "o_source_integrity_after_run", {name: sha(candidate / "data" / name) for name in data_names} == staged_before and {str(path): sha(path) for path in locked_files if path.is_file()} == locked_before, "candidate execution did not rewrite locked sources or artifacts")
    oracle = load_oracle(ROOT / "o_service_network/private/oracle.py")
    expected_metrics, expected_sources = oracle.expected(frozen_data)
    check(checks, "o_oracle_metrics", committed_metrics == expected_metrics, "independent frozen data-room recomputation")
    check(checks, "o_source_register", sorted(committed_sources, key=lambda x: x["id"]) == sorted(expected_sources, key=lambda x: x["id"]), "source IDs and byte hashes")
    check(checks, "o_program_matches_oracle", produced == expected_metrics, "independent frozen data-room recomputation")
    memo = (candidate / "memo.md").read_text() if (candidate / "memo.md").is_file() else ""
    required = {
        "/backlog", "/sla/eligible", "/sla/on_time", "/sla/attainment", "/sla/credit_cents",
        "/sla/unknown_credit_jobs", "/part_cost/known_cents", "/part_cost/unknown_part_cost_jobs",
        "/sensitivity/relay_plus_10_part_cost_cents",
    }
    required |= {f"/portfolios/{name}/{field}" for name in ("east", "west", "east+west") for field in ("monthly_cost_cents", "completed_jobs", "available_minutes", "used_minutes", "feasible")}
    found: set[str] = set()
    valid_rows = True
    known_ids = {source["id"] for source in expected_sources}
    required_sources = {
        "/backlog": {"orders-v1", "events-v1"},
        "/sla/eligible": {"orders-v1", "events-v1", "sla-v1"},
        "/sla/on_time": {"orders-v1", "events-v1", "sla-v1"},
        "/sla/attainment": {"orders-v1", "events-v1", "sla-v1"},
        "/sla/credit_cents": {"orders-v1", "events-v1", "sla-v1"},
        "/sla/unknown_credit_jobs": {"orders-v1", "events-v1", "sla-v1"},
        "/part_cost/known_cents": {"events-v1", "rates-v1"},
        "/part_cost/unknown_part_cost_jobs": {"events-v1"},
        "/sensitivity/relay_plus_10_part_cost_cents": {"events-v1", "rates-v1"},
        "/portfolios/east/monthly_cost_cents": {"capacity-v1"},
        "/portfolios/west/monthly_cost_cents": {"capacity-v1"},
        "/portfolios/east+west/monthly_cost_cents": {"capacity-v1", "shared-v1"},
    }
    for portfolio in ("east", "west", "east+west"):
        required_sources[f"/portfolios/{portfolio}/completed_jobs"] = {"orders-v1", "events-v1"}
        required_sources[f"/portfolios/{portfolio}/available_minutes"] = {"capacity-v1"}
        required_sources[f"/portfolios/{portfolio}/used_minutes"] = {"orders-v1", "events-v1"}
        required_sources[f"/portfolios/{portfolio}/feasible"] = {"capacity-v1", "orders-v1", "events-v1"}
    for pointer, text_value, references in re.findall(r"(?m)^\|\s*(/[^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", memo):
        pointer = pointer.strip()
        try:
            actual = expected_metrics
            for segment in pointer.lstrip("/").split("/"):
                actual = actual[segment.replace("~1", "/").replace("~0", "~")]
            expected_text = str(actual).lower() if isinstance(actual, bool) else str(actual)
            valid_rows &= expected_text == text_value.strip().replace(",", "").lower()
            cited = {x.strip() for x in references.split(",") if x.strip()}
            valid_rows &= bool(cited) and cited <= known_ids and required_sources.get(pointer, set()) <= cited
            found.add(pointer)
        except (KeyError, TypeError):
            valid_rows = False
    check(checks, "o_memo_evidence", valid_rows and required <= found, f"valid={valid_rows}; required_rows={len(required & found)}/{len(required)}")
    lower = memo.lower()
    recommendation = re.search(r"(?mi)^Recommendation:\s*(east\+west|east|west)\s*$", memo)
    criterion = re.search(r"(?mi)^Criterion:\s*(.+)$", memo)
    uncertainty = re.search(r"(?mi)^Uncertainty:\s*(.+)$", memo)
    chosen = recommendation.group(1).lower() if recommendation else None
    supported = bool(chosen and expected_metrics["portfolios"][chosen]["feasible"] and criterion and len(criterion.group(1).strip()) >= 30 and uncertainty and len(uncertainty.group(1).strip()) >= 30)
    if chosen in ("east", "west"):
        supported &= bool(re.search(r"coverage|assignment|assigned", lower) and re.search(r"validat|check|before closure", lower))
    check(checks, "o_memo_decision_record", supported, f"portfolio={chosen}; criterion/uncertainty and single-site caveat as applicable")
    check(checks, "o_memo_structure", "## operating plan" in lower and "## risks and assumptions" in lower and "| risk |" in lower and "| assumption |" in lower, "plan and risk/assumption register; semantic review remains open")
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["S", "O"], required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--deps", type=Path, default=Path(os.environ.get("OPENSOCRATES_EVAL_DEPS", "/private/tmp/opensocrates-go-ts-deps-20260928")))
    parser.add_argument("--candidate-policy", type=Path, default=Path(os.environ.get("OPENSOCRATES_CANDIDATE_POLICY", "/nonexistent-candidate-policy.sb")))
    parser.add_argument("--quick", action="store_true", help="preparation smoke only; never a full qualification")
    args = parser.parse_args()
    candidate, deps, policy = args.candidate.resolve(), args.deps.resolve(), args.candidate_policy.resolve()
    if not candidate.is_dir() or not (candidate / ".eval-copy").is_file() or ROOT in candidate.parents or not deps.is_dir() or not policy.is_file():
        return emit(args.task, [], error="candidate must be a marked disposable copy outside fixture root; deps and strict candidate policy must exist")
    os.environ["OPENSOCRATES_CANDIDATE_POLICY"] = str(policy)
    try:
        if args.task == "O":
            checks, performance = verify_o(candidate, deps, policy), None
        else:
            checks, performance = verify_s(candidate, deps, quick=args.quick)
        return emit(args.task, checks, performance=performance, quick=args.quick)
    except Exception as exc:
        return emit(args.task, [], error=f"verifier_error:{type(exc).__name__}")


def verify_s(candidate: Path, deps: Path, *, quick: bool = False) -> tuple[list[dict], dict | None]:
    qualifier = load_oracle(ROOT / "s_incidentops/private/qualify.py")
    return qualifier.qualify(candidate, deps, performance=not quick)


if __name__ == "__main__":
    sys.exit(main())

"""No-model O24 freeze audit. An unready result cannot launch episodes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from opensocrates.orchestration.adapter import DISABLED_FEATURES
from opensocrates.orchestration.guidance import guides as product_guides
from opensocrates.orchestration.runtime import orchestrate
import opensocrates.orchestration.runtime as runtime

from boundary_gate import evaluate as evaluate_boundary_gate
from generic_guides import guides as control_guides
from protocol import B_ARCHIVE, CLIENT, D_ARCHIVE, DESCRIPTOR, HERE, ROOT, b_guides
from protocol import descriptor, main_cells, request, sha, single_assignment


O_PRODUCT_COMMIT = "6eb8d3774f3a9032f580359b38b8bf11208f70d3"
B_PACKAGE_SHA = "52994553d51e8fd65285165d39ea004be819e56da8dab99c22968591a165dc76"
D_PACKAGE_SHA = "01c5c1852a4c6293d835a5cf3b73fee22c6eef3bb62a9ecc2f1e1cd2651cf9c9"
CLIENT_SHA = "c3e30211bd454da70ceb4d9cbc2e05fe6466812ab05c311c3bbff6addeb14202"
DEPS = Path("/private/tmp/opensocrates-go-ts-deps-20260928")


def digest(data: bytes) -> str:
    return "sha256:" + sha(data)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def code_hashes() -> dict[str, str]:
    names = (
        "run_main.py", "protocol.py", "generic_guides.py", "observer.py",
        "native_profile_client.py", "usage.py", "external.py", "freeze_o.py",
        "qualify_main.py", "boundary_gate.py", "export.py",
    )
    return {name: sha((HERE / name).read_bytes()) for name in names}


def product_file_hashes() -> dict[str, str]:
    paths = [
        *(ROOT / "src/opensocrates/orchestration").glob("*.py"),
        *(ROOT / "src/opensocrates/project_memory").glob("*.py"),
        *(ROOT / "schemas/v1").glob("orchestration-*.schema.json"),
        ROOT / "src/opensocrates/cli/orchestration.py",
    ]
    return {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in sorted(paths)}


def tool_hashes() -> dict[str, str]:
    paths = (
        CLIENT, B_ARCHIVE, D_ARCHIVE,
        Path("/usr/local/go/bin/go"), Path("/usr/local/go/bin/gofmt"),
        Path("/usr/bin/python3"), Path("/Applications/Xcode.app/Contents/Developer/usr/bin/python3"),
        Path("/usr/bin/sandbox-exec"),
        Path("/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang"),
    )
    return {str(path): sha(path.read_bytes()) for path in paths}


def package_guides(task: dict[str, Any], task_key: str = "O") -> dict[str, Any]:
    d: dict[str, Any] = {}
    mismatch = []
    prefix = "runtime/darwin-arm64/opensocrates-runtime/_internal/plugin-src/shared/"
    schema_prefix = "runtime/darwin-arm64/opensocrates-runtime/_internal/"
    with ZipFile(D_ARCHIVE) as archive:
        names = set(archive.namelist())
        for unit in task["units"]:
            roles = (unit["role"], "review", "execution_verification")
            for role in roles:
                key = unit["unit_id"] + ":" + role
                actual = product_guides(unit, role, "en")
                generic = control_guides(unit, role, "en")
                if any("OpenSocrates" in item["text"] for item in generic):
                    mismatch.append("product_name_leaked_in_generic:" + key)
                d[key] = {
                    "D": [{"id": item["id"], "sha256": item["sha256"]} for item in actual],
                    "C": [{"id": item["id"], "sha256": item["sha256"]} for item in generic],
                }
                for item in actual:
                    member = prefix + item["id"]
                    if member not in names or digest(archive.read(member)) != item["sha256"]:
                        mismatch.append("D_guide_package_mismatch:" + item["id"])
        for kind in ("request", "assignment", "candidate", "assessment", "response"):
            path = f"schemas/v1/orchestration-{kind}.schema.json"
            member = schema_prefix + path
            if member not in names or (ROOT / path).read_bytes() != archive.read(member):
                mismatch.append("D_schema_package_mismatch:" + path)
    b = b_guides(task_key, "en")
    d["B-single"] = [{"id": item["id"], "sha256": item["sha256"]} for item in b]
    return {"manifest": d, "mismatches": mismatch}


def memory_and_dispatch() -> dict[str, Any]:
    memory_bytes = int(subprocess.check_output(["/usr/sbin/sysctl", "-n", "hw.memsize"]).strip())
    cores = int(subprocess.check_output(["/usr/sbin/sysctl", "-n", "hw.logicalcpu"]).strip())
    return {
        "max_workers": 24,
        "formula": "all 24 independent O cells, with no unobserved account or host cap",
        "host_logical_cpu": cores, "host_physical_memory_bytes": memory_bytes,
        "no_arbitrary_legacy_three_worker_cap": True,
        "atomic_claim": "mkdir(exist_ok=False) for each predeclared cell",
        "dispatch_order": "protocol.main_cells order filtered to task O; no quality-based replacement",
        "actual_overlap_and_pressure": "record at execution; not inferred from worker limit",
        "account_concurrency": "unknown before subject calls; access failures remain terminal",
    }


def dry_run_o(task: dict[str, Any], public: Path) -> dict[str, Any]:
    cells = [cell for cell in main_cells() if cell["task"] == "O"]
    states = []
    for cell in cells:
        if cell["arm"] in {"A", "B"}:
            assignment, _ = single_assignment(task, cell, public)
            states.append({"id": cell["id"], "state": "assignment_valid", "input_sha256": digest(canonical(assignment))})
        else:
            old = runtime.guides
            if cell["arm"] == "C":
                runtime.guides = control_guides
            try:
                prepared = orchestrate(request(task, cell, public,
                    public.parent / "candidate-absent", HERE / "native_profile_client.py", "prepare"))
            finally:
                runtime.guides = old
            if prepared["status"] != "prepared" or prepared["calls"]:
                raise ValueError("O_prepare_failed:" + cell["id"])
            states.append({"id": cell["id"], "state": "prepared_zero_calls",
                           "input_sha256": prepared["plan_sha256"]})
    return {"count": len(states), "cells": states, "model_calls": 0}


def freeze(source_descriptor: Path) -> dict[str, Any]:
    data = descriptor(source_descriptor, tasks={"O"})
    task = data["tasks"]["O"]
    public = source_descriptor.parent / task["public_root"]
    task_hash = sha(canonical(task))
    packet = source_descriptor.parent / "o_service_network_v2"
    standalone_path = packet / "descriptor.json"
    standalone = json.loads(standalone_path.read_text()) if standalone_path.exists() else {}
    blockers = []
    unprefixed = standalone.get("task") or {}
    standalone_hash = sha(canonical(unprefixed)) if unprefixed else None
    expected_integrated = json.loads(json.dumps(unprefixed)) if unprefixed else {}
    if expected_integrated:
        expected_integrated["public_root"] = "o_service_network_v2/" + expected_integrated["public_root"]
        expected_integrated["external_qualification"]["entrypoint"] = (
            "o_service_network_v2/" + expected_integrated["external_qualification"]["entrypoint"]
        )
    if not expected_integrated or canonical(expected_integrated) != canonical(task):
        blockers.append("integrated_O_task_differs_from_exact_standalone_except_two_path_prefixes")
    prep = packet / "private/FREEZE_PREP.json"
    prep_data = json.loads(prep.read_text()) if prep.exists() else {}
    if task_hash == "875a52e2c30526d79831f3df63a593d0c71ad01abd217312b90136c08f1745af":
        blockers.append("O_v1_small_packet_is_controls_only_not_hard_subject")
    if source_descriptor.resolve() != DESCRIPTOR.resolve() or not DESCRIPTOR.is_file():
        blockers.append("fixture_not_integrated_in_runner_worktree")
    if sha(B_ARCHIVE.read_bytes()) != B_PACKAGE_SHA:
        blockers.append("B_package_changed")
    if sha(D_ARCHIVE.read_bytes()) != D_PACKAGE_SHA:
        blockers.append("D_package_changed")
    if sha(CLIENT.read_bytes()) != CLIENT_SHA:
        blockers.append("actual_client_changed")
    if (B_ARCHIVE.parent != D_ARCHIVE.parent
        or B_ARCHIVE.name != "B-pre-orchestration.zip"
        or D_ARCHIVE.name != "D-current-orchestration.zip"):
        blockers.append("frozen_local_archive_copies_missing")
    if ROOT.resolve() == Path("/private/tmp/opensocrates-go-ts-runner-20260928").resolve():
        blockers.append("mutable_preparation_checkout_not_execution_checkout")
    diff = subprocess.run(["/usr/bin/git", "diff", "--quiet", O_PRODUCT_COMMIT,
                           "HEAD", "--", "src/opensocrates/orchestration", "schemas/v1",
                           "plugin-src/shared/orchestration", "plugin-src/shared/assistance",
                           "plugin-src/shared/coding-specialists"], cwd=ROOT, check=False)
    if diff.returncode != 0:
        blockers.append("product_source_differs_from_qualified_commit")
    guides = package_guides(task)
    blockers += guides["mismatches"]
    control_path = packet / "private/controls/selftest.json"
    native_path = packet / "private/native_selftest.json"
    control_data = json.loads(control_path.read_text()) if control_path.exists() else {}
    native_data = json.loads(native_path.read_text()) if native_path.exists() else {}
    packet_files_match = all(
        (packet / relative).is_file() and sha((packet / relative).read_bytes()) == expected
        for mapping in (prep_data.get("public_files", {}), prep_data.get("private_files", {}))
        for relative, expected in mapping.items()
    )
    positives = [item for item in control_data.get("controls", []) if item.get("expected") == "pass"]
    negatives = [item for item in control_data.get("controls", []) if item.get("expected") != "pass"]
    controls = {
        "prep_manifest_sha256": sha(prep.read_bytes()) if prep.exists() else None,
        "task_descriptor_sha256": task_hash,
        "standalone_task_descriptor_sha256": standalone_hash,
        "standalone_descriptor_sha256": sha(standalone_path.read_bytes()) if standalone_path.exists() else None,
        "source_hashes": {item["id"]: item["sha256"] for item in task["sources"]},
        "positive_passed": prep_data.get("positive_controls_passed"),
        "negative_rejected": prep_data.get("negative_controls_rejected"),
        "negative_total": len(negatives),
        "native_static_passed": prep_data.get("native_static_controls_passed"),
        "candidate_private_read_denied": prep_data.get("child_private_read_denied"),
        "external_verifier_sha256": sha((source_descriptor.parent / task["external_qualification"]["entrypoint"]).read_bytes()),
        "packet_file_hashes_match": packet_files_match,
        "control_selftest_sha256": sha(control_path.read_bytes()) if control_path.exists() else None,
        "native_selftest_sha256": sha(native_path.read_bytes()) if native_path.exists() else None,
        "private_oracle_sha256": prep_data.get("private_oracle_sha256"),
    }
    if (controls["positive_passed"] != len(positives) or controls["positive_passed"] < 3
        or control_data.get("passed") is not True or native_data.get("passed") is not True
        or native_data.get("good_bytes_unchanged") is not True
        or native_data.get("bad_bytes_unchanged") is not True
        or controls["native_static_passed"] is not True
        or controls["candidate_private_read_denied"] is not True or not controls["negative_total"]
        or controls["negative_rejected"] != controls["negative_total"]
        or prep_data.get("task_descriptor_canonical_sha256") != standalone_hash
        or prep_data.get("descriptor_sha256") != controls["standalone_descriptor_sha256"]
        or prep_data.get("external_verifier_sha256") != controls["external_verifier_sha256"]):
        blockers.append("O_fixture_controls_or_hashes_not_frozen")
    if not packet_files_match or prep_data.get("outcome_calls") != 0:
        blockers.append("O_v2_packet_bytes_or_pre_call_state_changed")
    deps_entries = sorted(item.name for item in DEPS.iterdir()) if DEPS.is_dir() else []
    if deps_entries != ["browsers", "go-modcache", "npm"]:
        blockers.append("subject_dependency_root_not_generic_only")
    boundary = evaluate_boundary_gate()
    if boundary.get("accepted_component_evidence") is not True:
        blockers.append("bounded_real_role_read_boundary_decision_unverified")
    prepared = dry_run_o(task, public)
    if prepared["count"] != 24:
        blockers.append("O_cell_count_mismatch")
    dispatch = memory_and_dispatch()
    hashes = code_hashes()
    products = product_file_hashes()
    for role_guides in guides["manifest"].values():
        if isinstance(role_guides, dict) and "D" in role_guides:
            for item in role_guides["D"]:
                relative = "plugin-src/shared/" + item["id"]
                products[relative] = sha((ROOT / relative).read_bytes())
    tools = tool_hashes()
    cells = [cell for cell in main_cells() if cell["task"] == "O"]
    checkout_commit = subprocess.check_output(["/usr/bin/git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    if not (ROOT / ".git").exists():
        blockers.append("execution_checkout_not_git_bound")
    return {
        "schema": "opensocrates.go-ts.execution-freeze/1",
        "lane": "O-office-v2-pending" if blockers else "O-office-v2",
        "ready_for_outcomes": not blockers,
        "blockers": sorted(set(blockers)),
        "study_design": {"main_total": 48, "this_lane": 24,
                         "other_main_S_pending": 24, "continuity_pending": 8,
                         "no_outcome_dependent_expansion": True},
        "task_descriptor_hashes": {"O": task_hash},
        "descriptor_sha256": sha(source_descriptor.read_bytes()),
        "cell_ids": [cell["id"] for cell in cells],
        "cells": cells, "dry_run": prepared,
        "fixture_controls": controls,
        "boundary_component_decision": boundary,
        "arm_guidance": guides["manifest"],
        "current_package_sha256": D_PACKAGE_SHA,
        "pre_orchestration_package_sha256": B_PACKAGE_SHA,
        "product_source_commit": O_PRODUCT_COMMIT,
        "execution_checkout_root": str(ROOT.resolve()),
        "execution_checkout_commit": checkout_commit,
        "archive_copy_dir": str(B_ARCHIVE.parent) if B_ARCHIVE.parent == D_ARCHIVE.parent else None,
        "client_version": "codex-cli 0.158.0-alpha.2",
        "role_client_controls": {
            "ephemeral": True, "ignore_user_config": True, "history_persistence": "none",
            "fast_mode": False, "native_tool_profile": "eval extends :read-only",
            "read_scope": "current role or check cwd only",
            "disabled_features": list(DISABLED_FEATURES),
            "enabled_feature": "skip_host_skill_discovery",
            "actual_per_call_argv_hashes": "argv-map.jsonl; original and effective; no raw args retained",
        },
        "actual_client_sha256": CLIENT_SHA,
        "shim_sha256": hashes["native_profile_client.py"],
        "runner_sha256": hashes["run_main.py"],
        "observer_sha256": hashes["observer.py"],
        "generic_guides_sha256": hashes["generic_guides.py"],
        "protocol_sha256": hashes["protocol.py"],
        "other_code_hashes": hashes,
        "product_file_hashes": products,
        "tool_and_archive_hashes": tools,
        "native_checks": {unit["unit_id"]: unit["checks"] for unit in task["units"]},
        "external_qualification": task["external_qualification"],
        "subject_dependency_root": str(DEPS), "subject_dependency_top_level": deps_entries,
        "dispatch": dispatch,
        "dispatch_observation": {
            "source": "fsynced per-role start/terminal journals plus episode start/terminal markers",
            "output": "results/dispatch-index.json",
            "measures": ["observed_peak_episode_overlap", "observed_peak_role_overlap",
                         "host_load_1m", "host_codex_process_count", "host_codex_rss_kib",
                         "episodes_started_without_terminal", "roles_started_without_terminal",
                         "episode_overlap_complete", "role_overlap_complete",
                         "malformed_observation_lines", "malformed_episode_markers"],
            "host_pressure_scope": "aggregate host sample; unrelated Codex processes may contribute",
        },
        "limits": {key: None for key in ("wall_clock_seconds", "input_tokens", "output_tokens",
                                         "total_tokens", "tool_calls", "output_bytes", "internal_retries")},
        "fast_mode": False, "native_repair_limit": 2,
        "usage_fields": ["input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                         "output_tokens", "reasoning_output_tokens"],
        "usage_rule": "null preserved; cache and reasoning are subsets; no billing claim; setup agent usage separate/unavailable",
        "failure_policy": "Atomic one-shot claims, no restart/rerun/coach/fallback/outer repair; startup, role, native, external and publication failures separate; partial evidence kept.",
        "export_allowlist": ["freeze", "dispatch_index", "started", "terminal", "summary", "response_public_structured",
                             "candidate_synthetic_artifacts", "role_observation_aggregates", "argv_hash_map",
                             "external_structured_receipts", "source_and_component_hashes"],
        "export_excluded": ["auth", "raw_prompt", "transcript", "reasoning", "raw_jsonl_events",
                            "tool_output_body", "private_oracle", "unbounded_stderr"],
        "evidence_status": "no_model_preparation_only",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--descriptor", type=Path, default=DESCRIPTOR)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = freeze(args.descriptor)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(value, out, sort_keys=True, indent=2, ensure_ascii=False)
        out.write("\n")
    print(json.dumps({"ready_for_outcomes": value["ready_for_outcomes"],
                      "blockers": value["blockers"], "cell_count": len(value["cell_ids"]),
                      "output_sha256": sha(args.output.read_bytes())}, sort_keys=True))


if __name__ == "__main__":
    main()

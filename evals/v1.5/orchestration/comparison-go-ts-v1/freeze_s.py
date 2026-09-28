"""No-model S24 freeze audit with explicit pending-browser decision."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from opensocrates.orchestration.runtime import orchestrate
import opensocrates.orchestration.runtime as runtime

from boundary_gate import evaluate as evaluate_boundary_gate
from freeze_o import (B_PACKAGE_SHA, CLIENT_SHA, D_PACKAGE_SHA, O_PRODUCT_COMMIT,
                      code_hashes, memory_and_dispatch, package_guides,
                      product_file_hashes, tool_hashes)
from generic_guides import guides as control_guides
from protocol import B_ARCHIVE, CLIENT, D_ARCHIVE, DESCRIPTOR, HERE, ROOT
from protocol import descriptor, main_cells, request, sha, single_assignment
from freeze_o import DEPS, canonical


def dry_run_s(task: dict[str, Any], public: Path) -> dict[str, Any]:
    states = []
    for cell in (item for item in main_cells() if item["task"] == "S"):
        if cell["arm"] in {"A", "B"}:
            assigned, _ = single_assignment(task, cell, public)
            states.append({"id": cell["id"], "state": "assignment_valid",
                           "input_sha256": "sha256:" + sha(canonical(assigned))})
        else:
            old = runtime.guides
            if cell["arm"] == "C":
                runtime.guides = control_guides
            try:
                result = orchestrate(request(task, cell, public,
                    public.parent / "candidate-absent", HERE / "native_profile_client.py", "prepare"))
            finally:
                runtime.guides = old
            if result["status"] != "prepared" or result["calls"]:
                raise ValueError("S_prepare_failed:" + cell["id"])
            states.append({"id": cell["id"], "state": "prepared_zero_calls",
                           "input_sha256": result["plan_sha256"]})
    return {"count": len(states), "model_calls": 0, "cells": states}


def freeze(source_descriptor: Path) -> dict[str, Any]:
    data = descriptor(source_descriptor, tasks={"S"})
    task = data["tasks"]["S"]
    task_hash = sha(canonical(task))
    packet = source_descriptor.parent / "s_incidentops"
    standalone_path = packet / "descriptor.json"
    standalone = json.loads(standalone_path.read_text()) if standalone_path.exists() else {}
    prep_path = packet / "private/FREEZE_PREP.json"
    prep = json.loads(prep_path.read_text()) if prep_path.exists() else {}
    control_path = packet / "private/controls/selftest.json"
    native_path = packet / "private/native_selftest.json"
    control = json.loads(control_path.read_text()) if control_path.exists() else {}
    native = json.loads(native_path.read_text()) if native_path.exists() else {}
    boundary_path = HERE / "S_BOUNDARY_DECISION.json"
    s_decision = json.loads(boundary_path.read_text()) if boundary_path.exists() else {}
    selected_decision = {key: s_decision.get(key) for key in ("status", "attribution", "reference")}
    blockers = []
    if canonical(standalone.get("task")) != canonical(task):
        blockers.append("integrated_S_task_differs_from_standalone")
    if source_descriptor.resolve() != DESCRIPTOR.resolve():
        blockers.append("S_fixture_not_integrated")
    if prep.get("task_descriptor_canonical_sha256") != task_hash:
        blockers.append("S_task_descriptor_prep_mismatch")
    if prep.get("descriptor_sha256") != sha(standalone_path.read_bytes()):
        blockers.append("S_standalone_descriptor_changed")
    all_files_match = all(
        (packet / relative).is_file() and sha((packet / relative).read_bytes()) == expected
        for mapping in (prep.get("public_files", {}), prep.get("private_files", {}))
        for relative, expected in mapping.items()
    )
    positives = [item for item in control.get("controls", []) if item.get("expected") == "pass"]
    negatives = [item for item in control.get("controls", []) if item.get("expected") != "pass"]
    if (not all_files_match or control.get("passed") is not True
        or native.get("passed") is not True or native.get("read_only_bytes_unchanged") is not True
        or prep.get("native_static_passed") is not True
        or prep.get("functional_control_passed") is not True
        or prep.get("full_good_control_passed") is not True
        or prep.get("child_private_read_denied") is not True
        or prep.get("bad_controls_rejected") != len(negatives) or len(negatives) < 6
        or not positives or prep.get("performance_all_accounted") is not True
        or prep.get("performance_post_state_valid") is not True
        or prep.get("outcome_calls") != 0):
        blockers.append("S_fixture_controls_or_bytes_not_frozen")
    if prep.get("release_status") != "pending_browser_transport_capability_decision":
        blockers.append("S_original_pending_label_changed")
    if (s_decision.get("source_prep_sha256") != sha(prep_path.read_bytes())
        or s_decision.get("public_environment_sha256") != sha((packet / "public/ENVIRONMENT.md").read_bytes())
        or selected_decision != {"status": "allow_unassessable_as_pending",
                                 "attribution": "parent_explicit",
                                 "reference": "parent:2026-09-28-s-transport-boundary"}):
        blockers.append("separate_parent_S_browser_decision_missing_or_changed")
    if sha(B_ARCHIVE.read_bytes()) != B_PACKAGE_SHA or sha(D_ARCHIVE.read_bytes()) != D_PACKAGE_SHA:
        blockers.append("B_or_D_package_changed")
    if sha(CLIENT.read_bytes()) != CLIENT_SHA:
        blockers.append("actual_client_changed")
    if (B_ARCHIVE.parent != D_ARCHIVE.parent or B_ARCHIVE.name != "B-pre-orchestration.zip"
        or D_ARCHIVE.name != "D-current-orchestration.zip"):
        blockers.append("frozen_local_archive_copies_missing")
    if ROOT.resolve() == Path("/private/tmp/opensocrates-go-ts-runner-20260928").resolve():
        blockers.append("mutable_preparation_checkout_not_execution_checkout")
    diff = subprocess.run(["/usr/bin/git", "diff", "--quiet", O_PRODUCT_COMMIT,
                           "HEAD", "--", "src/opensocrates", "schemas/v1", "plugin-src/shared"],
                          cwd=ROOT, check=False)
    if diff.returncode != 0:
        blockers.append("product_source_differs_from_qualified_commit")
    guides = package_guides(task, "S")
    blockers += guides["mismatches"]
    deps_entries = sorted(item.name for item in DEPS.iterdir()) if DEPS.is_dir() else []
    if deps_entries != ["browsers", "go-modcache", "npm"]:
        blockers.append("subject_dependency_root_not_generic_only")
    boundary = evaluate_boundary_gate()
    if boundary.get("accepted_component_evidence") is not True:
        blockers.append("bounded_real_role_read_boundary_decision_unverified")
    prepared = dry_run_s(task, source_descriptor.parent / task["public_root"])
    if prepared["count"] != 24:
        blockers.append("S_cell_count_mismatch")
    products = product_file_hashes()
    for role_guides in guides["manifest"].values():
        if isinstance(role_guides, dict) and "D" in role_guides:
            for item in role_guides["D"]:
                path = "plugin-src/shared/" + item["id"]
                products[path] = sha((ROOT / path).read_bytes())
    code = code_hashes()
    for name in ("freeze_s.py", "secondary/qualify_s.py", "S_BOUNDARY_DECISION.json"):
        code[name] = sha((HERE / name).read_bytes())
    tools = tool_hashes()
    extra_tools = (
        Path("/usr/local/bin/node"),
        DEPS / "npm/node_modules/.bin/tsc",
        DEPS / "npm/node_modules/playwright/package.json",
        DEPS / "npm/node_modules/typescript/package.json",
        DEPS / "browsers/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell",
        packet / "private/qualify.py",
        packet / "private/performance.py",
        packet / "private/browser_probe.cjs",
    )
    tools.update({str(path): sha(path.read_bytes()) for path in extra_tools})
    controls = {
        "prep_manifest_sha256": sha(prep_path.read_bytes()),
        "task_descriptor_sha256": task_hash,
        "source_hashes": {item["id"]: item["sha256"] for item in task["sources"]},
        "positive_passed": len(positives), "negative_rejected": len(negatives),
        "native_static_passed": native.get("passed"),
        "candidate_private_read_denied": prep.get("child_private_read_denied"),
        "packet_file_hashes_match": all_files_match,
        "external_verifier_sha256": sha((source_descriptor.parent / task["external_qualification"]["entrypoint"]).read_bytes()),
        "control_selftest_sha256": sha(control_path.read_bytes()),
        "native_selftest_sha256": sha(native_path.read_bytes()),
        "performance_seed_requests": prep.get("performance_seed_requests"),
        "performance_warmup_requests": prep.get("performance_warmup_requests"),
        "performance_measured_requests": prep.get("performance_measured_requests"),
    }
    if controls["external_verifier_sha256"] != prep.get("shared_external_verifier_sha256"):
        blockers.append("S_external_verifier_changed")
    head = subprocess.check_output(["/usr/bin/git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    dispatch = memory_and_dispatch()
    cells = [cell for cell in main_cells() if cell["task"] == "S"]
    return {
        "schema": "opensocrates.go-ts.execution-freeze/1", "lane": "S-incidentops",
        "ready_for_outcomes": not blockers, "blockers": sorted(set(blockers)),
        "study_design": {"main_total": 48, "this_lane": 24, "O24_separate_active_or_complete": 24,
                         "continuity_pending": 8, "no_outcome_dependent_expansion": True},
        "task_descriptor_hashes": {"S": task_hash},
        "descriptor_sha256": sha(source_descriptor.read_bytes()),
        "cell_ids": [cell["id"] for cell in cells], "cells": cells,
        "dry_run": prepared, "fixture_controls": controls,
        "arm_guidance": guides["manifest"],
        "s_browser_transport_decision": selected_decision,
        "s_boundary_decision_sha256": sha(boundary_path.read_bytes()),
        "boundary_component_decision": boundary,
        "current_package_sha256": D_PACKAGE_SHA,
        "pre_orchestration_package_sha256": B_PACKAGE_SHA,
        "product_source_commit": O_PRODUCT_COMMIT,
        "execution_checkout_root": str(ROOT.resolve()),
        "execution_checkout_commit": head,
        "archive_copy_dir": str(B_ARCHIVE.parent) if B_ARCHIVE.parent == D_ARCHIVE.parent else None,
        "client_version": "codex-cli 0.158.0-alpha.2",
        "actual_client_sha256": CLIENT_SHA,
        "shim_sha256": code["native_profile_client.py"],
        "runner_sha256": code["run_main.py"],
        "observer_sha256": code["observer.py"],
        "observer_revision": 2,
        "O24_observer_revision": 1,
        "generic_guides_sha256": code["generic_guides.py"],
        "protocol_sha256": code["protocol.py"],
        "other_code_hashes": code,
        "product_file_hashes": products,
        "tool_and_archive_hashes": tools,
        "native_checks": {unit["unit_id"]: unit["checks"] for unit in task["units"]},
        "external_qualification": task["external_qualification"],
        "subject_dependency_root": str(DEPS), "subject_dependency_top_level": deps_entries,
        "dispatch": dispatch,
        "dispatch_observation": {"output": "results/dispatch-index.json",
                                 "measures": ["actual_role_overlap", "host_load", "host_codex_rss",
                                              "missing_terminal_and_unknown_error_counts"]},
        "limits": {key: None for key in ("wall_clock_seconds", "input_tokens", "output_tokens",
                                         "total_tokens", "tool_calls", "output_bytes", "internal_retries")},
        "fast_mode": False, "native_repair_limit": 2,
        "usage_fields": ["input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                         "output_tokens", "reasoning_output_tokens"],
        "usage_rule": "null preserved; cache and reasoning subsets; setup usage separate/unavailable",
        "failure_policy": "Atomic one-shot claims, no restart/rerun/coach/fallback/outer repair; retained safe rejection quarantine; startup/native/external failures separate.",
        "serial_external_after_generation": True,
        "browser_transport_unknown_rule": "Unassessable FileServer signature remains pending, never a model defect or pass; real mixed defects still count.",
        "export_allowlist": ["freeze", "dispatch_index", "started", "terminal", "summary",
                             "response_public_structured", "candidate_synthetic_artifacts",
                             "unqualified_owned_quarantine", "role_observation_aggregates",
                             "argv_hash_map", "external_structured_receipts"],
        "export_excluded": ["auth", "raw_prompt", "transcript", "reasoning", "raw_jsonl_events",
                            "tool_output_body", "private_oracle", "server_logs"],
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

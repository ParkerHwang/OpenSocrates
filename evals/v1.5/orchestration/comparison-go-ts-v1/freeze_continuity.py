"""No-model freeze for eight real-memory versus maintained-note continuations."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from opensocrates.orchestration.guidance import guides as product_guides

from boundary_gate import evaluate as evaluate_boundary_gate
from freeze_o import B_PACKAGE_SHA, CLIENT_SHA, D_PACKAGE_SHA, O_PRODUCT_COMMIT, DEPS
from freeze_o import code_hashes, product_file_hashes, tool_hashes
from protocol import B_ARCHIVE, CLIENT, D_ARCHIVE, HERE, ROOT, sha


def freeze() -> dict[str, Any]:
    packet = HERE / "fixtures/continuity"
    descriptor_path = packet / "descriptor.json"
    setup_path = packet / "private/harness_setup.json"
    prep_path = packet / "private/FREEZE_PREP.json"
    controls_path = packet / "private/controls/selftest.json"
    native_path = packet / "private/native_selftest.json"
    checker_path = packet / "private/verify_continuity.py"
    description = json.loads(descriptor_path.read_text())
    prep = json.loads(prep_path.read_text())
    controls = json.loads(controls_path.read_text())
    native = json.loads(native_path.read_text())
    api_path = HERE / "CONTINUITY_API_PREFLIGHT.json"
    real_path = HERE / "CONTINUITY_REAL_STATE_CHECKS.json"
    api = json.loads(api_path.read_text()) if api_path.exists() else {}
    real = json.loads(real_path.read_text()) if real_path.exists() else {}
    blockers = []
    if len(description["cells"]) != 8 or len({cell["id"] for cell in description["cells"]}) != 8:
        blockers.append("continuity_cell_set_invalid")
    tuples = {(cell["model"], cell["effort"]) for cell in description["cells"]}
    conditions = {cell["condition"] for cell in description["cells"]}
    if tuples != {("gpt-6-sol", "high"), ("gpt-6-luna", "high")} or conditions != {
        "scoped_disposable_memory", "disabled_memory_with_equivalent_note"}:
        blockers.append("continuity_models_or_conditions_changed")
    if (prep["descriptor_sha256"] != sha(descriptor_path.read_bytes())
        or prep.get("control_selftest_passed") is not True
        or prep.get("native_static_passed") is not True
        or prep.get("control_checks") != 36
        or prep.get("outcome_calls") != 0
        or controls.get("passed") is not True or len(controls.get("controls", [])) != 36
        or native.get("passed") is not True):
        blockers.append("continuity_fixture_controls_not_frozen")
    fixture_file_hashes = {**prep.get("public_files", {}), **prep.get("private_files", {})}
    if not fixture_file_hashes or any(
        not (packet / name).is_file() or sha((packet / name).read_bytes()) != expected
        for name, expected in fixture_file_hashes.items()
    ):
        blockers.append("continuity_fixture_file_hash_mismatch")
    if (api.get("passed") is not True or api.get("planned_cells") != 8
        or api.get("role_model_calls") != 0
        or api.get("descriptor_sha256") != sha(descriptor_path.read_bytes())
        or api.get("setup_sha256") != sha(setup_path.read_bytes())
        or api.get("operator_sha256") != sha((HERE / "continuity_memory.py").read_bytes())):
        blockers.append("real_disposable_memory_api_preflight_missing_or_changed")
    if (real.get("passed") is not True or real.get("checked") != 8
        or real.get("role_model_calls") != 0
        or real.get("memory_api_receipt_sha256") != sha(api_path.read_bytes())
        or real.get("checker_sha256") != sha(checker_path.read_bytes())):
        blockers.append("continuity_real_state_checker_preflight_missing_or_changed")
    if len(api.get("results", [])) == 8:
        for item in api["results"]:
            memory = item["condition"] == "scoped_disposable_memory"
            if (item.get("scoped_forget_applied") is not True
                or item["deleted_record_id"] in item["persisted_record_ids"]
                or item["source_before_sha256"] == item["source_after_sha256"]):
                blockers.append("continuity_correction_or_forget_unverified")
            if memory and (item.get("projection_status") != "available"
                           or item.get("stale_projection") != "stale"):
                blockers.append("memory_projection_not_available_and_stale")
            if not memory and (item.get("projection_status") != "disabled"
                               or item.get("projected_record_ids") != []
                               or not item.get("maintained_note_equivalent_ids")):
                blockers.append("note_condition_projection_or_equivalence_wrong")
    boundary = evaluate_boundary_gate()
    if boundary.get("accepted_component_evidence") is not True:
        blockers.append("bounded_real_role_read_boundary_decision_unverified")
    if sha(CLIENT.read_bytes()) != CLIENT_SHA:
        blockers.append("actual_client_changed")
    if sha(D_ARCHIVE.read_bytes()) != D_PACKAGE_SHA or sha(B_ARCHIVE.read_bytes()) != B_PACKAGE_SHA:
        blockers.append("frozen_package_copy_changed")
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
    deps_entries = sorted(item.name for item in DEPS.iterdir()) if DEPS.is_dir() else []
    if deps_entries != ["browsers", "go-modcache", "npm"]:
        blockers.append("subject_dependency_root_not_generic_only")
    products = product_file_hashes()
    guide_manifest: dict[str, list[dict[str, str]]] = {}
    guide_prefix = "runtime/darwin-arm64/opensocrates-runtime/_internal/plugin-src/shared/"
    with ZipFile(D_ARCHIVE) as archive:
        for cell in description["cells"]:
            unit = cell["unit"]
            for role in (unit["role"], "review", "execution_verification"):
                key = cell["id"] + ":" + role
                values = product_guides(unit, role, cell["locale"])
                guide_manifest[key] = [{"id": item["id"], "sha256": item["sha256"]} for item in values]
                for item in values:
                    relative = "plugin-src/shared/" + item["id"]
                    member = guide_prefix + item["id"]
                    if "sha256:" + sha((ROOT / relative).read_bytes()) != item["sha256"] or (
                        member not in archive.namelist() or "sha256:" + sha(archive.read(member)) != item["sha256"]
                    ):
                        blockers.append("continuity_guide_package_mismatch:" + item["id"])
                    products[relative] = sha((ROOT / relative).read_bytes())
    code = code_hashes()
    for name in ("continuity_memory.py", "run_continuity.py", "freeze_continuity.py",
                 "secondary/qualify_continuity.py", "CONTINUITY_API_PREFLIGHT.json",
                 "CONTINUITY_REAL_STATE_CHECKS.json"):
        code[name] = sha((HERE / name).read_bytes())
    tools = tool_hashes()
    tools[str(checker_path)] = sha(checker_path.read_bytes())
    head = subprocess.check_output(["/usr/bin/git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    return {
        "schema": "opensocrates.go-ts.continuity-freeze/1",
        "lane": "continuity-EN-KO-memory-note",
        "ready_for_outcomes": not blockers, "blockers": sorted(set(blockers)),
        "study_design": {"main_episodes_separate": 48, "continuity_episodes": 8,
                         "nominal_no_repair_role_calls": 24, "no_outcome_dependent_expansion": True},
        "cell_ids": [cell["id"] for cell in description["cells"]],
        "cells": [{"id": cell["id"], "model": cell["model"], "effort": cell["effort"],
                   "locale": cell["locale"], "condition": cell["condition"]}
                  for cell in description["cells"]],
        "descriptor_sha256": sha(descriptor_path.read_bytes()),
        "memory_setup_sha256": sha(setup_path.read_bytes()),
        "fixture_prep_sha256": sha(prep_path.read_bytes()),
        "fixture_file_hashes": fixture_file_hashes,
        "real_memory_api_preflight_sha256": sha(api_path.read_bytes()),
        "real_state_checker_preflight_sha256": sha(real_path.read_bytes()),
        "private_checker_sha256": sha(checker_path.read_bytes()),
        "guide_manifest": guide_manifest,
        "boundary_component_decision": boundary,
        "product_source_commit": O_PRODUCT_COMMIT,
        "current_package_sha256": D_PACKAGE_SHA,
        "execution_checkout_root": str(ROOT.resolve()),
        "execution_checkout_commit": head,
        "client_version": "codex-cli 0.158.0-alpha.2", "actual_client_sha256": CLIENT_SHA,
        "shim_sha256": code["native_profile_client.py"],
        "observer_sha256": code["observer.py"], "observer_revision": 2,
        "O24_observer_revision": 1,
        "code_hashes": code, "product_hashes": products, "tool_hashes": tools,
        "dispatch": {"max_workers": 8, "formula": "all eight independent continuation cells",
                     "atomic_claim": "mkdir(exist_ok=False); no rerun on prior start",
                     "actual_overlap_pressure": "per-episode resource markers and dispatch-index"},
        "memory_protocol": {"enrollment_scope": "one fresh synthetic project/workspace per cell",
                            "recording": "existing init/observe/record/accept/delete/export/inspect API",
                            "source_correction": "tracked current-source.md v1 to v2 before fresh role",
                            "note_condition": "same persisted records then disabled native memory, exact equivalent note source",
                            "role_permissions": "read-only; no memory mutation API by role"},
        "native_checks": {cell["id"]: cell["unit"]["checks"] for cell in description["cells"]},
        "external_qualification": "serial post-generation private checker plus real post-role memory export/inspect/status",
        "subject_dependency_root": str(DEPS), "subject_dependency_top_level": deps_entries,
        "limits": {key: None for key in ("wall_clock_seconds", "input_tokens", "output_tokens",
                                         "total_tokens", "tool_calls", "output_bytes", "internal_retries")},
        "fast_mode": False, "native_repair_limit": 2,
        "usage_fields": ["input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                         "output_tokens", "reasoning_output_tokens"],
        "usage_rule": "null preserved; cache/reasoning subsets; setup usage separate/unavailable",
        "failure_policy": "One-shot claims; no model/effort substitution, coaching, outer repair or automatic restart; native and memory-state failures retained separately.",
        "export_allowlist": ["freeze", "dispatch_index", "started", "terminal", "memory_setup_public_receipt",
                             "summary", "response_public_structured", "candidate_synthetic_artifacts",
                             "unqualified_owned_quarantine", "role_observation_aggregates",
                             "argv_hash_map", "external_structured_receipts"],
        "export_excluded": ["auth", "raw_prompt", "transcript", "reasoning", "raw_jsonl_events",
                            "tool_output_body", "private_oracle", "raw_memory_export"],
        "clarification_timing": "unassessable_without_complete_public_message_stream",
        "evidence_status": "no_model_preparation_only",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = freeze()
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(value, out, sort_keys=True, indent=2, ensure_ascii=False)
        out.write("\n")
    print(json.dumps({"ready_for_outcomes": value["ready_for_outcomes"],
                      "blockers": value["blockers"], "cell_count": len(value["cell_ids"]),
                      "output_sha256": sha(args.output.read_bytes())}, sort_keys=True))


if __name__ == "__main__":
    main()

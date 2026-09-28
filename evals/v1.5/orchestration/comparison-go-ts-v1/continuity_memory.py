"""Real disposable memory-API correction, forgetting and projection setup.

This operator code runs before a continuation role. It never enrolls a real
project or asks a read-only model role to mutate memory. The source root is a
fresh synthetic workspace, and the private store stays outside role cwd.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from opensocrates.orchestration.runtime import Coordinator
from opensocrates.project_memory.registry import ProjectRegistry
from opensocrates.project_memory.service import handle_memory


HERE = Path(__file__).resolve().parent
SHIM = HERE / "native_profile_client.py"
NAMESPACE = UUID("cd53bb0a-fec7-4277-b914-2746e7dba28c")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def uid(label: str) -> str:
    return str(uuid5(NAMESPACE, label))


def call(registry: ProjectRegistry, identities: dict[str, str | None],
         operation: str, payload: dict[str, Any], label: str) -> dict[str, Any]:
    request = {
        "schema": "opensocrates.project-memory.request/1.0.0",
        "operation": operation, "request_id": uid("request:" + label),
        "project_id": identities.get("project_id"),
        "workspace_id": identities.get("workspace_id"),
        "task_id": identities.get("task_id"), "payload": payload,
    }
    result = handle_memory(request, registry=registry)
    if result["status"] != "ok":
        raise ValueError("memory_api_" + operation + "_" + result["status"])
    return result


def fixture(fixture_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root = fixture_root / "continuity"
    setup = json.loads((root / "private/harness_setup.json").read_text())
    description = json.loads((root / "descriptor.json").read_text())
    if setup["schema"] != "opensocrates.eval.continuity-setup/1.0.0":
        raise ValueError("continuity_setup_schema_changed")
    if description["schema"] != "opensocrates.eval.continuity-descriptor/1.0.0":
        raise ValueError("continuity_descriptor_schema_changed")
    return setup, description


def materialize(cell: dict[str, Any], fixture_root: Path, episode: Path) -> tuple[Path, dict[str, str]]:
    source = episode / "source"
    source.mkdir(mode=0o700, parents=True, exist_ok=False)
    root = fixture_root / "continuity"
    planned = {}
    for item in cell["sources"]:
        content = (root / item["fixture_path"]).read_bytes()
        if "sha256:" + sha(content) != item["sha256"]:
            raise ValueError("continuity_source_changed:" + item["id"])
        target = source / item["materialized_path"]
        if not target.resolve().is_relative_to(source.resolve()):
            raise ValueError("continuity_source_escape")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        planned[item["id"]] = item["sha256"]
    current = source / "current-source.md"
    before = (root / "private/harness_initial_source.md").read_bytes()
    current.write_bytes(before)
    return source, planned


def request_for(cell: dict[str, Any], source: Path, candidate: Path,
                binding: dict[str, str] | None) -> dict[str, Any]:
    memory = None if binding is None else {
        "project_id": binding["project_id"], "workspace_id": binding["workspace_id"],
        "record_ids": binding["record_ids"],
    }
    return {
        "schema": "opensocrates.orchestration.request/1.0.0",
        "operation": "prepare", "run_id": uid("continuity-run:" + cell["id"]),
        "task_id": uid("continuity-task:" + cell["id"]), "revision": 1,
        "authorization": {"reference": "user:comparison-execution", "attribution": "operator_declared"},
        "model": {"name": cell["model"], "effort": cell["effort"]},
        "locale": cell["locale"], "objective": cell["objective"],
        "required_artifacts": cell["required_artifacts"],
        "constraints": cell["constraints"], "permissions": cell["permissions"],
        "prohibitions": cell["prohibitions"], "source_root": str(source),
        "sources": [{"id": item["id"], "path": item["materialized_path"],
                     "sha256": item["sha256"]} for item in cell["sources"]],
        "candidate_root": str(candidate), "client_path": str(SHIM),
        "repair_limit": 2, "memory": memory, "handoff": cell["handoff"],
        "units": [cell["unit"]],
    }


def setup_one(cell: dict[str, Any], fixture_root: Path, episode: Path) -> dict[str, Any]:
    setup, _ = fixture(fixture_root)
    if episode.exists():
        if not episode.is_dir() or any((episode / name).exists()
                                           for name in ("source", "private-store", "candidate")):
            raise ValueError("continuity_episode_already_prepared")
    else:
        episode.mkdir(mode=0o700, parents=True, exist_ok=False)
    source, planned = materialize(cell, fixture_root, episode)
    registry = ProjectRegistry(episode / "private-store")
    identities: dict[str, str | None] = {
        "project_id": None, "workspace_id": None,
        "task_id": uid("continuity-task:" + cell["id"]),
    }
    policy = {"root": str(source), "apply": False, "mode": "read_write",
              "capture_policy": "milestones", "excluded_paths": []}
    preview = call(registry, identities, "init", policy, cell["id"] + ":preview")
    policy.update({
        "apply": True, "disclosure_digest": preview["result"]["disclosure_digest"],
        "authorization_basis": "user:comparison-execution",
        "authorization_attribution": "operator_declared",
        "idempotency_key": uid(cell["id"] + ":enroll"),
    })
    enrolled = call(registry, identities, "init", policy, cell["id"] + ":enroll")
    identities["project_id"] = enrolled["result"]["project_id"]
    identities["workspace_id"] = enrolled["result"]["workspace_id"]
    observed = call(registry, identities, "observe", {
        "path": "current-source.md", "idempotency_key": uid(cell["id"] + ":observe-v1")
    }, cell["id"] + ":observe-v1")
    snapshot = observed["result"]["snapshot"]
    reference = observed["result"]["reference"]
    versions = {}
    for spec in setup["pre_correction_records"]:
        source_dependent = spec["kind"] == "source_dependent_accepted_fact"
        record = call(registry, identities, "record", {
            "idempotency_key": uid(cell["id"] + ":record:" + spec["id"]),
            "record_id": spec["id"], "expected_record_version": 0,
            "kind": "decision", "scope": {"level": "project"},
            "summary": f"{spec['key']}: {spec['value']}",
            "origin": {"producer_kind": "agent", "source_reference": None,
                       "attestation": "agent_reported"},
            "support": "agent_reported",
            "source_refs": [reference["ref_id"]] if source_dependent else [],
            "snapshot_id": snapshot["snapshot_id"] if source_dependent else None,
            "revalidation": {
                "dependency_paths": ["current-source.md"] if source_dependent else [],
                "negative_claim": False,
                "on_change": "refresh_or_mark_stale" if source_dependent else "not_applicable",
            },
        }, cell["id"] + ":record:" + spec["id"])
        versions[spec["id"]] = record["result"]["record"]["version"]
        if spec["kind"] != "proposed_preference":
            accepted = call(registry, identities, "accept", {
                "record_id": spec["id"], "expected_record_version": versions[spec["id"]],
                "idempotency_key": uid(cell["id"] + ":accept:" + spec["id"]),
                "acceptance_basis": "user:comparison-execution",
                "acceptance_attribution": "operator_declared",
            }, cell["id"] + ":accept:" + spec["id"])
            versions[spec["id"]] = accepted["result"]["record"]["version"]
    prior = source / "current-source.md"
    before_hash = "sha256:" + sha(prior.read_bytes())
    corrected = (fixture_root / "continuity/public/current-source.md").read_bytes()
    prior.write_bytes(corrected)
    after_hash = "sha256:" + sha(prior.read_bytes())
    if before_hash == after_hash or after_hash != planned["current-source"]:
        raise ValueError("continuity_correction_not_frozen")
    removed = setup["postconditions"]["deleted_record_absent"]
    deleted = call(registry, identities, "delete", {
        "intent": "delete_record", "record_id": removed,
        "expected_record_version": versions[removed],
        "idempotency_key": uid(cell["id"] + ":delete:" + removed),
    }, cell["id"] + ":delete:" + removed)
    exported = call(registry, identities, "export", {"format": "json"}, cell["id"] + ":export")
    inspected = call(registry, identities, "inspect", {}, cell["id"] + ":inspect")
    records = inspected["result"]
    by_id = {item["record_id"]: item for item in records}
    retained = setup["postconditions"]["retained_record_ids"]
    stale = setup["postconditions"]["stale_record_id"]
    proposed = setup["postconditions"]["unaccepted_record_id"]
    if removed in by_id or any(key not in by_id for key in [*retained, stale, proposed]):
        raise ValueError("memory_persisted_record_set_wrong")
    if any(by_id[key]["lifecycle"] != "accepted" for key in [*retained, stale]):
        raise ValueError("accepted_intent_not_retained")
    if by_id[proposed]["lifecycle"] == "accepted":
        raise ValueError("proposal_promoted_to_intent")
    if removed in json.dumps(exported, ensure_ascii=False):
        raise ValueError("deleted_record_in_export")
    binding = {"project_id": str(identities["project_id"]),
               "workspace_id": str(identities["workspace_id"]),
               "record_ids": [*retained, stale, proposed]}
    if cell["condition"] == "disabled_memory_with_equivalent_note":
        call(registry, identities, "disable", {
            "expected_policy_version": 1,
            "idempotency_key": uid(cell["id"] + ":disable"),
        }, cell["id"] + ":disable")
    candidate = episode / "candidate"
    coordinator = Coordinator(request_for(cell, source, candidate, binding), registry=registry)
    assignment, _ = coordinator.assignment(cell["unit"], cell["unit"]["role"], {}, [], [])
    projected = assignment["memory"]
    if cell["condition"] == "scoped_disposable_memory":
        projected_by_id = {item["record_id"]: item for item in projected["records"]}
        if (projected["status"] != "available" or removed in projected_by_id
            or projected_by_id[stale]["freshness"] != "stale"
            or projected_by_id[proposed]["lifecycle"] == "accepted"
            or any(key not in projected_by_id for key in retained)):
            raise ValueError("memory_projection_wrong")
    else:
        if projected["status"] != "disabled" or projected["records"]:
            raise ValueError("disabled_note_condition_not_disabled")
    note_equivalent_ids: list[str] = []
    note_sha256 = None
    if cell["condition"] == "disabled_memory_with_equivalent_note":
        note = source / "maintained_note.md"
        expected_note = fixture_root / "continuity" / cell["maintained_note"]
        if not note.is_file() or note.read_bytes() != expected_note.read_bytes():
            raise ValueError("maintained_note_materialization_changed")
        note_sha256 = "sha256:" + sha(note.read_bytes())
        note_equivalent_ids = [*retained, stale, proposed]
    return {
        "schema": "opensocrates.go-ts.continuity-memory-setup/1",
        "cell_id": cell["id"], "condition": cell["condition"],
        "project_id": binding["project_id"], "workspace_id": binding["workspace_id"],
        "source_before_sha256": before_hash, "source_after_sha256": after_hash,
        "current_source_before_sha256": before_hash.removeprefix("sha256:"),
        "current_source_after_sha256": after_hash.removeprefix("sha256:"),
        "api_readback_verified": True, "correction_replayed": True,
        "scoped_forget_applied": deleted["result"]["deleted_record_id"] == removed,
        "control_only": False,
        "deleted_record_id": deleted["result"]["deleted_record_id"],
        "persisted_record_count": len(records),
        "persisted_record_ids": sorted(by_id),
        "retained_record_ids": retained, "stale_record_id": stale,
        "proposed_record_id": proposed,
        "projection_status": projected["status"],
        "projection_record_ids": [item["record_id"] for item in projected["records"]],
        "projected_record_ids": [item["record_id"] for item in projected["records"]],
        "maintained_note_equivalent_ids": note_equivalent_ids,
        "maintained_note_sha256": note_sha256,
        "stale_projection": next((item["freshness"] for item in projected["records"]
                                  if item["record_id"] == stale), None),
        "export_sha256": "sha256:" + sha(json.dumps(exported, sort_keys=True).encode()),
        "memory_api_operations": ["init_preview", "init_apply", "observe", "record", "accept",
                                  "source_correction", "delete", "export", "inspect"]
                                 + (["disable"] if cell["condition"] == "disabled_memory_with_equivalent_note" else []),
        "role_model_calls": 0,
        "private_store_outside_role_cwd": True,
        "raw_memory_export_or_source_contents_retained": False,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=HERE / "fixtures")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    setup, description = fixture(args.fixtures)
    args.output_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    results = []
    for cell in description["cells"]:
        try:
            result = setup_one(cell, args.fixtures, args.output_root / cell["id"])
            results.append(result)
            with (args.output_root / cell["id"] / "memory-setup.json").open("x", encoding="utf-8") as out:
                json.dump(result, out, sort_keys=True, indent=2, ensure_ascii=False)
                out.write("\n")
        except (OSError, ValueError) as error:
            results.append({"cell_id": cell["id"], "status": "setup_unavailable",
                            "error_type": type(error).__name__, "role_model_calls": 0})
    receipt = {
        "schema": "opensocrates.go-ts.continuity-memory-preflight/1",
        "descriptor_sha256": sha((args.fixtures / "continuity/descriptor.json").read_bytes()),
        "setup_sha256": sha((args.fixtures / "continuity/private/harness_setup.json").read_bytes()),
        "operator_sha256": sha(Path(__file__).read_bytes()),
        "planned_cells": len(description["cells"]), "results": results,
        "passed": len(results) == 8 and all(item.get("projection_status") in {"available", "disabled"}
                                            for item in results),
        "role_model_calls": 0,
        "evidence_scope": "real disposable project-memory APIs and native prepare projection; no subject outcomes",
    }
    with args.receipt.open("x", encoding="utf-8") as out:
        json.dump(receipt, out, sort_keys=True, indent=2, ensure_ascii=False)
        out.write("\n")
    print(json.dumps({"planned_cells": receipt["planned_cells"], "passed": receipt["passed"],
                      "role_model_calls": 0, "receipt_sha256": sha(args.receipt.read_bytes())},
                     sort_keys=True))


if __name__ == "__main__":
    main()

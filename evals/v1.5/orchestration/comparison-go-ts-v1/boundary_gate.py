"""Check the primary's bounded component decision against immutable receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DECISION = HERE / "BOUNDARY_GATE_DECISION.json"
EXPECTED = {
    "allowed_read": True, "private_read_denied": True,
    "host_memory_denied": True, "auth_denied": True,
    "write_denied": True, "network_denied": True,
}
HELPER_SHA = "520b0922e208d4c2157affa3f330f462cc6a4b4104a093f8043aa6c729a300da"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(decision_path: Path = DECISION) -> dict[str, Any]:
    try:
        decision = json.loads(decision_path.read_text())
        original = Path(decision["original_probe_result_path"])
        reconciliation = (decision_path.parent / decision["reconciliation_path"]).resolve()
        if sha(original) != decision["original_probe_result_sha256"]:
            raise ValueError("original_result_hash_mismatch")
        if sha(reconciliation) != decision["reconciliation_sha256"]:
            raise ValueError("reconciliation_hash_mismatch")
        if decision.get("decision") != "component_evidence_sufficient_for_frozen_subject_roles_after_task_fixture_gates":
            raise ValueError("decision_missing")
        if decision.get("original_frozen_isolation_verified") is not False:
            raise ValueError("original_verdict_rewritten")
        if decision.get("no_new_model_call_or_retroactive_pass") is not True:
            raise ValueError("retrospective_pass_requested")
        result = json.loads(original.read_text())
        recon = json.loads(reconciliation.read_text())
        if (result["manifest_sha256"] != decision["original_probe_manifest_sha256"]
            or result["isolation_verified"] is not False
            or recon["frozen_isolation_verified"] is not False
            or recon["original_result_sha256"] != decision["original_probe_result_sha256"]):
            raise ValueError("frozen_result_identity_or_verdict_mismatch")
        if (result["role_status"] != "completed" or result["process_exit_code"] != 0
            or result["argv_mapping_verified"] is not True
            or result["start_without_terminal"] or result["observation_failures"]):
            raise ValueError("role_or_mapping_unverified")
        commands = [item for item in result["tool_events"] if item["type"] == "command_execution"]
        starts = [item for item in commands if item["phase"] == "started"]
        ends = [item for item in commands if item["phase"] == "completed"]
        if (len(starts) != 1 or len(ends) != 1
            or not starts[0]["id_sha256"] or starts[0]["id_sha256"] != ends[0]["id_sha256"]
            or not starts[0]["command_sha256"] or starts[0]["command_sha256"] != ends[0]["command_sha256"]
            or starts[0]["approved_command"] is not True or ends[0]["approved_command"] is not True
            or ends[0]["normalized_command_sha256"] != HELPER_SHA
            or ends[0]["exit_code"] != 0 or ends[0]["helper_marker_count"] != 1
            or ends[0]["helper_booleans"] != EXPECTED or result["helper_booleans"] != EXPECTED):
            raise ValueError("approved_helper_boundary_missing")
        extras = [item for item in result["tool_events"] if item["type"] != "command_execution"]
        if (len(extras) != 1 or extras[0]["type"] != "error"
            or extras[0]["phase"] != "completed" or extras[0]["command_sha256"] is not None
            or extras[0]["exit_code"] is not None
            or recon["additional_item"]["count"] != 1
            or recon["additional_item"]["cause"] != "unknown"):
            raise ValueError("unclassified_error_not_preserved")
        auth = original.parent / "home/.codex/auth.json"
        if auth.exists() or recon["auth_copy_present_after_terminal"] is not False:
            raise ValueError("disposable_auth_not_removed")
        return {"accepted_component_evidence": True,
                "original_probe_isolation_verified": False,
                "unclassified_error_item_retained": True,
                "decision_sha256": sha(decision_path),
                "result_sha256": sha(original), "reconciliation_sha256": sha(reconciliation)}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"accepted_component_evidence": False, "reason": type(error).__name__}

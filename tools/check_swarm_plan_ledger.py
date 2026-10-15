#!/usr/bin/env python3
"""Regression checks for S042 report consumption by the local budget ledger.

All observations, identities, approvals and STARTED reservations below are newly
authored synthetic test data. They provide no host observation, resource lease,
study permission or model call. Run only against the selected integrated source:
  python tools/check_swarm_plan_ledger.py
"""

from __future__ import annotations

import argparse
import copy
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import swarm_isolation_preflight as preflight
import swarm_plan_ledger as ledger

SOURCE_SHA = "1" * 40
STUDY_ID = "synthetic-ledger-gate-only"


def synthetic_report(outcome: str = "PASS") -> dict[str, Any]:
    """Use the actual S042 producer with complete public categorical fixtures."""
    now = datetime.now(UTC) - timedelta(seconds=1)
    as_of = now.isoformat()
    frozen_at = (now - timedelta(seconds=1)).isoformat()
    identity = dict.fromkeys(preflight.IDENTITY_FIELDS)
    identity.update(
        repository="ParkerHwang/OpenSocrates",
        source_sha=SOURCE_SHA,
        product_version="synthetic",
        content_revision="synthetic",
        host="synthetic",
        platform="synthetic",
        model_requested="synthetic",
        effort="synthetic",
        service_tier_requested="priority",
    )
    data: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "snapshot_id": "synthetic-snapshot",
        "as_of": as_of,
        "source_identity": identity,
        "baseline": {
            "assigned_base_sha": preflight.BASE_SHA,
            "remote_main_sha": preflight.BASE_SHA,
        },
        "protocol": {
            "state": "INPUTS_LOCKED",
            "source_sha": SOURCE_SHA,
            "frozen_at": frozen_at,
            "input_files": [{"path": "evals/swarm-20261015/PROTOCOL.md", "sha256": "b" * 64}],
            "actor_budget_total": 54,
            "started_actor_calls": 0,
            "dimension_counts": {"tasks": 3, "locales": 2, "arms": 3, "repeats": 3},
            "one_attempt_per_cell": True,
            "count_failures": True,
            "count_timeouts": True,
            "run_owner": "S078",
            "native_mode": "installed-plugin",
        },
        "arms": [],
        "observations": [],
        "availability": {},
        "runtime_sha256": "a" * 64,
    }
    for index, name in enumerate(preflight.ARMS):
        data["arms"].append(
            {
                "arm": name,
                "scope_id": f"synthetic-scope-{index}",
                "os_profile_id": f"synthetic-profile-{index}",
                "paths": {
                    key: f"/synthetic-scope-map/arm{index}/{key}" for key in preflight.PATH_FIELDS
                },
                "runtime_sha256": "a" * 64,
            }
        )
    scopes = [("study", STUDY_ID, preflight.GLOBAL_RULES)]
    scopes.extend((arm["arm"], arm["scope_id"], preflight.ARM_RULES) for arm in data["arms"])
    for name, scope, rules in scopes:
        for check, rule in rules.items():
            data["observations"].append(
                {
                    "observation_id": f"synthetic-observation-{len(data['observations'])}",
                    "arm": name,
                    "scope_id": scope,
                    "check": check,
                    "value": (
                        rule.native_value if name == "native-opensocrates" else rule.control_value
                    ),
                    "kind": rule.kind,
                    "observer": "S078",
                    "observed_at": as_of,
                    "snapshot_id": data["snapshot_id"],
                    "source_sha": SOURCE_SHA,
                    "coverage": sorted(rule.coverage),
                }
            )
    if outcome == "FAIL":
        data["observations"][0]["value"] = sorted(preflight.GLOBAL_RULES["source"].failure_values)[
            0
        ]
    elif outcome == "UNKNOWN":
        data["observations"].pop(0)
    return preflight.evaluate(preflight.validate_input(data))


class GateContractChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="synthetic-ledger-gate-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.config_path = self.write(
            "config.json",
            {"study_id": STUDY_ID, "source_sha": SOURCE_SHA, "assignment_seed": 43},
        )
        self.plan_path = self.root / "assignment-plan.json"
        ledger.plan_command(argparse.Namespace(input=self.config_path, output=self.plan_path))
        self.plan, self.plan_bytes = ledger.load_json(self.plan_path)
        self.plan_sha = ledger.digest(self.plan_bytes)
        self.freeze = {
            "schema_version": 1,
            "state": "FROZEN",
            "source_sha": SOURCE_SHA,
            "isolation_state": "VERIFIED",
            "quota": 54,
            "approved_by": "S001",
            "frozen_at": (datetime.now(UTC) - timedelta(seconds=3)).isoformat(),
            "input_files": [
                {"path": "evals/swarm-20261015/assignment-plan.json", "sha256": self.plan_sha}
            ],
        }
        self.freeze_path = self.write("freeze.json", self.freeze)
        self.report = synthetic_report()
        self.report_path = self.write("isolation.json", self.report)

    def write(self, name: str, value: Any) -> Path:
        path = self.root / name
        path.write_bytes(ledger.encoded(value))
        return path

    def gates(self) -> dict[str, str]:
        return ledger.gate_evidence(
            self.freeze_path, self.report_path, SOURCE_SHA, self.plan_sha, STUDY_ID
        )

    def refused_report(self, value: dict[str, Any], reason: str) -> None:
        self.write("isolation.json", value)
        with self.assertRaises(ledger.LedgerError) as failure:
            self.gates()
        self.assertEqual(str(failure.exception), reason)

    def test_actual_pass_report_can_initialize_and_reserve_one_synthetic_attempt(self) -> None:
        self.assertEqual(self.report["status"], "PASS")
        self.assertIs(self.report["isolation_blocked"], False)
        self.assertIs(self.report["experiment_blocked"], True)
        self.assertIs(self.report["execution_authorized"], False)
        original = self.report_path.read_bytes()
        gates = self.gates()
        self.assertEqual(gates["isolation_sha256"], ledger.digest(original))
        ledger_path = self.root / "assignment-ledger.json"
        ledger.init_command(
            argparse.Namespace(
                input=self.plan_path,
                output=ledger_path,
                owner="S078",
                freeze=self.freeze_path,
                isolation=self.report_path,
            )
        )
        first = self.plan["cells"][0]
        event = self.write(
            "event.json",
            {"cell_id": first["cell_id"], "attempt_id": first["attempt_id"], "status": "STARTED"},
        )
        result = ledger.record_command(
            argparse.Namespace(
                input=ledger_path,
                output=ledger_path,
                event=event,
                expected_revision=0,
                owner="S078",
                freeze=self.freeze_path,
                isolation=self.report_path,
            )
        )
        self.assertEqual(result["cell_status"], "STARTED")
        self.assertEqual(result["attempted"], 1)
        self.assertEqual(result["assigned"], 54)
        stored, _ = ledger.load_json(ledger_path)
        self.assertEqual(stored["gate_evidence"], gates)
        self.assertEqual(len(ledger.replay_ledger(stored, ledger_path)), 54)
        self.assertEqual(self.report_path.read_bytes(), original)

    def test_actual_fail_and_unknown_reports_remain_refused(self) -> None:
        for status in ("FAIL", "UNKNOWN"):
            with self.subTest(status=status):
                report = synthetic_report(status)
                self.assertEqual(report["status"], status)
                self.assertIs(report["isolation_blocked"], True)
                self.refused_report(report, "isolation_unverified")

    def test_preflight_cannot_claim_execution_permission(self) -> None:
        changes = (
            ("execution_authorized", True, "isolation_is_not_authorization"),
            ("experiment_blocked", False, "isolation_is_not_authorization"),
            ("isolation_blocked", True, "isolation_blocked"),
            ("final_study_freeze_and_lease_required", False, "isolation_central_gates_required"),
            ("execution_authorized", None, "isolation_is_not_authorization"),
        )
        for field, value, reason in changes:
            with self.subTest(field=field, value=value):
                report = copy.deepcopy(self.report)
                report[field] = value
                self.refused_report(report, reason)

    def test_forged_pass_label_does_not_hide_structured_fail_or_unknown(self) -> None:
        for status in ("FAIL", "UNKNOWN"):
            with self.subTest(status=status):
                report = copy.deepcopy(self.report)
                report["global_checks"][0]["status"] = status
                self.refused_report(report, "isolation_check_not_pass")
                report = copy.deepcopy(self.report)
                report["arms"][0]["checks"][0]["status"] = status
                self.refused_report(report, "isolation_check_not_pass")
                report = copy.deepcopy(self.report)
                report["arms"][0]["status"] = status
                self.refused_report(report, "isolation_arm_not_pass")

    def test_missing_or_duplicate_inventory_is_refused(self) -> None:
        changes = (
            ("global_checks", [], "isolation_checks_missing"),
            ("arms", self.report["arms"][:2], "isolation_arms_missing"),
            ("blocking_checks", [{"status": "UNKNOWN"}], "isolation_blocking_checks_present"),
        )
        for field, value, reason in changes:
            with self.subTest(field=field):
                report = copy.deepcopy(self.report)
                report[field] = value
                self.refused_report(report, reason)
        report = copy.deepcopy(self.report)
        report["global_checks"][0] = copy.deepcopy(report["global_checks"][1])
        self.refused_report(report, "isolation_check_inventory")
        report = copy.deepcopy(self.report)
        report["arms"][0] = copy.deepcopy(report["arms"][1])
        self.refused_report(report, "isolation_duplicate_arm")

    def test_report_study_and_source_must_match_the_selected_plan(self) -> None:
        report = copy.deepcopy(self.report)
        report["study_id"] = "another-synthetic-study"
        self.refused_report(report, "isolation_study_mismatch")
        report = copy.deepcopy(self.report)
        report["source_identity"]["source_sha"] = "2" * 40
        self.refused_report(report, "isolation_source_mismatch")

    def test_pass_does_not_bypass_central_freeze_or_budget(self) -> None:
        changes = (
            ("state", "DRAFT", "protocol_not_frozen"),
            ("quota", 53, "freeze_budget_mismatch"),
            ("approved_by", "S078", "freeze_approval_missing"),
            ("isolation_state", "UNVERIFIED", "freeze_isolation_unverified"),
        )
        for field, value, reason in changes:
            with self.subTest(field=field):
                freeze = copy.deepcopy(self.freeze)
                freeze[field] = value
                self.write("freeze.json", freeze)
                with self.assertRaises(ledger.LedgerError) as failure:
                    self.gates()
                self.assertEqual(str(failure.exception), reason)


if __name__ == "__main__":
    unittest.main()

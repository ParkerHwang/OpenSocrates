#!/usr/bin/env python3
"""Behavioral checks for synthetic-only study ownership and human-first review."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from opensocrates.evaluation import Lab, LabError
from opensocrates.evaluation.report import report, validate_export
from opensocrates.evaluation.storage import read_bytes

ROOT = Path(__file__).resolve().parents[1]
ENV = {"os": "macos", "arch": "arm64", "source": "local_platform"}


class LabBehavior(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.pack = self.base / "pack"
        shutil.copytree(ROOT / "evals/office-work-v1", self.pack)
        self.lab = Lab(self.base / "study", self.pack)
        self.platform_patch = patch(
            "opensocrates.evaluation.engine.controller_environment", return_value=ENV
        )
        self.platform_patch.start()
        self.addCleanup(self.platform_patch.stop)
        self.addCleanup(self.temporary.cleanup)

    def create(self, phase: str = "calibration", budget: int = 10) -> dict[str, Any]:
        return self.lab.action(
            "create", {"phase": phase, "cells": ["macos-work"], "budget": budget, "seed": 17}
        )

    def preflight(self, run: dict[str, Any], **changes: Any) -> dict[str, Any]:
        data = {
            "run_id": run["id"],
            "observed_model": "gpt-6-luna",
            "observed_effort": "max",
            "host_version": "1.2.3",
            "execution_mode": "local",
            "isolation": "clear",
            "environment": "clean_snapshot",
            "opensocrates": "enabled" if run["arm"] == "C" else "absent",
            "model_mapping_confirmed": False,
            "exploratory": False,
            "pack_approved": True,
        }
        data.update(changes)
        return self.lab.action("preflight", data)

    def prepare(self, run: dict[str, Any]) -> dict[str, Any]:
        # A stub transport avoids actor calls and never claims live host qualification.
        guide = {
            "profile": "synthetic-fixture",
            "status": "manual_required",
            "steps": [],
            "links": [],
        }
        with patch("opensocrates.evaluation.hosts.prepare_content", return_value=guide):
            return self.lab.action("prepare", {"run_id": run["id"]})

    def complete(self, run: dict[str, Any], answer: str = "검토할 가상 결과물입니다.") -> None:
        self.prepare(run)
        self.assertTrue(self.preflight(run)["can_start"])
        self.lab.action("start", {"run_id": run["id"]})
        self.lab.action(
            "finish",
            {
                "run_id": run["id"],
                "status": "completed",
                "intake": "manual",
                "final_text": answer,
                "synthetic_approved": True,
            },
        )

    def assert_code(self, expected: str, action: str, data: dict[str, Any]) -> None:
        with self.assertRaises(LabError) as caught:
            self.lab.action(action, data)
        self.assertEqual(caught.exception.code, expected)

    def test_freeze_source_and_owned_root(self) -> None:
        snapshot = self.create()
        self.assertEqual(len(snapshot["runs"]), 6)
        manifest = json.loads((self.pack / "pack.json").read_text())
        manifest["cases"][0]["prompt"] = "Changed public source"
        (self.pack / "pack.json").write_text(json.dumps(manifest))
        self.assertEqual(self.lab.snapshot()["pack"]["sha256"], snapshot["pack"]["sha256"])
        self.assert_code(
            "root_exists", "create", {"phase": "calibration", "cells": ["macos-work"], "budget": 6}
        )
        foreign = self.base / "foreign"
        foreign.mkdir()
        with self.assertRaises(LabError):
            Lab(foreign, self.pack).snapshot()
        self.assertFalse((foreign / ".office-lab").exists())

    def test_exact_model_isolation_os_and_reservation(self) -> None:
        snapshot = self.create(budget=1)
        run = next(item for item in snapshot["runs"] if item["arm"] == "A")
        prepared = self.prepare(run)
        self.assertFalse(
            any("evaluator" in path.name for path in Path(prepared["actor_path"]).rglob("*"))
        )
        self.assertFalse(self.preflight(run, observed_model="unknown")["can_start"])
        self.assert_code("preflight_blocked", "start", {"run_id": run["id"]})
        self.assertFalse(
            self.preflight(run, isolation="contaminated", exploratory=True)["can_start"]
        )
        self.assertFalse(self.preflight(run, isolation="unknown")["can_start"])
        self.assertTrue(self.preflight(run, isolation="unknown", exploratory=True)["can_start"])
        with patch(
            "opensocrates.evaluation.engine.controller_environment",
            return_value={**ENV, "os": "windows"},
        ):
            self.assert_code("preflight_blocked", "start", {"run_id": run["id"]})
        self.preflight(run)
        self.lab.action("start", {"run_id": run["id"]})
        self.lab.action("finish", {"run_id": run["id"], "status": "failed"})
        self.assertEqual(self.lab.snapshot()["started_count"], 1)
        self.assert_code("budget_exhausted", "retry", {"run_id": run["id"]})

    def test_clarification_card_survives_prepared_and_running_resume(self) -> None:
        run = next(item for item in self.create()["runs"] if item["arm"] == "A")
        prepared = self.prepare(run)
        expected = prepared["clarification_reply"]
        self.assertTrue(expected)
        source = self.pack / "pack.json"
        manifest = json.loads(source.read_text())
        for case in manifest["cases"]:
            if case["id"] == run["case_id"]:
                case["clarification_reply"] = "Changed source must not replace the frozen card."
        source.write_text(json.dumps(manifest))
        self.lab = Lab(self.base / "study", self.pack)
        resumed = next(item for item in self.lab.snapshot()["runs"] if item["id"] == run["id"])
        self.assertEqual(resumed["clarification_reply"], expected)
        repeated = self.lab.action("prepare", {"run_id": run["id"]})
        self.assertEqual(repeated["run"]["clarification_reply"], expected)
        self.assertEqual(repeated["clarification_reply"], expected)
        self.assertNotIn("evaluator_checks", resumed)
        self.preflight(run)
        self.lab.action("start", {"run_id": run["id"]})
        resumed_lab = Lab(self.base / "study", self.pack)
        running = next(item for item in resumed_lab.snapshot()["runs"] if item["id"] == run["id"])
        self.assertEqual(running["status"], "running")
        self.assertEqual(running["clarification_reply"], expected)
        self.assertNotIn("evaluator_checks", running)

    def test_exact_preview_and_rejected_content_not_retained(self) -> None:
        run = next(item for item in self.create()["runs"] if item["arm"] == "A")
        actor = Path(self.prepare(run)["actor_path"])
        self.preflight(run)
        self.lab.action("start", {"run_id": run["id"]})
        final = actor / "out/final.md"
        final.write_text("First synthetic draft", encoding="utf-8")
        preview = self.lab.action("preview", {"run_id": run["id"]})
        self.assertTrue(self.lab.action("monitor", {"run_id": run["id"]})["ready"])
        final.write_text("Unapproved changed text", encoding="utf-8")
        self.assert_code(
            "preview_changed",
            "finish",
            {
                "run_id": run["id"],
                "status": "completed",
                "synthetic_approved": True,
                "approval_token": preview["approval_token"],
            },
        )
        state = (self.base / "study/state.json").read_text()
        self.assertNotIn("Unapproved changed text", state)
        self.assertNotIn(preview["approval_token"], state)
        self.assertEqual(list((self.base / "study/approved").iterdir()), [])
        preview = self.lab.action("preview", {"run_id": run["id"]})
        self.lab.action(
            "finish",
            {
                "run_id": run["id"],
                "status": "completed",
                "synthetic_approved": True,
                "approval_token": preview["approval_token"],
            },
        )
        self.assertEqual(
            (self.base / "study/approved" / f"{run['id']}.md").read_text(),
            "Unapproved changed text",
        )

    def test_human_first_locked_judgment_and_closed_export(self) -> None:
        snapshot = self.create()
        group = snapshot["groups"][0]
        data = {"group_id": group["id"]}
        self.assert_code("judgment_required", "reveal", data)
        for run in snapshot["runs"]:
            if run["group_id"] == group["id"]:
                self.complete(run)
        packet = self.lab.action("packet", data)
        self.assertEqual(packet, self.lab.action("packet", data))
        self.assertNotIn("arm", json.dumps(packet))
        self.lab.action(
            "judge",
            {
                **data,
                "choice": "tie",
                "confidence": "low",
                "recognition": "known",
                "reproduced_experience": "uncertain",
                "synthetic_approved": True,
                "first_reaction": "",
            },
        )
        self.assert_code(
            "judgment_locked",
            "judge",
            {
                **data,
                "choice": "tie",
                "confidence": "low",
                "recognition": "known",
                "reproduced_experience": "uncertain",
                "synthetic_approved": True,
            },
        )
        self.assertEqual(
            sorted(self.lab.action("reveal", data)["mapping"].values()), ["A", "B", "C"]
        )
        exported = self.lab.action("export", {})["export"]
        self.assertEqual(validate_export(exported), exported)
        self.assertEqual(exported["report"]["cells"][0]["primary_assigned"], 6)
        exported["runs"][0]["raw_transcript"] = "forbidden"
        with self.assertRaises(LabError):
            validate_export(exported)

    def test_retry_cannot_replace_failed_primary(self) -> None:
        snapshot = self.create()
        run = snapshot["runs"][0]
        self.lab.action("finish", {"run_id": run["id"], "status": "blocked"})
        retry = self.lab.action("retry", {"run_id": run["id"]})["run"]
        self.assertEqual(retry["attempt"], 2)
        self.complete(retry)
        self.assert_code("group_incomplete", "packet", {"group_id": run["group_id"]})
        self.assertEqual(self.lab.snapshot()["started_count"], 1)

    def test_confirmation_requires_immutable_human_criteria(self) -> None:
        snapshot = self.create(phase="confirmation")
        self.assertEqual(snapshot["pack"]["approval"]["cases"], [])
        run = snapshot["runs"][0]
        self.assert_code("criteria_not_frozen", "prepare", {"run_id": run["id"]})
        criteria = {
            "criteria": "Human tentative criteria",
            "discovery_reference": "synthetic-discovery-1",
            "synthetic_approved": True,
        }
        self.lab.action("freeze", criteria)
        self.assert_code("criteria_locked", "freeze", criteria)
        self.assertTrue(self.lab.snapshot()["pack"]["approval"]["cases"])
        self.prepare(run)

    def test_outbox_symlink_and_state_lock_refused(self) -> None:
        run = self.create()["runs"][0]
        actor = Path(self.prepare(run)["actor_path"])
        self.preflight(run)
        self.lab.action("start", {"run_id": run["id"]})
        outside = self.base / "unrelated.md"
        outside.write_text("unrelated")
        try:
            (actor / "out/final.md").symlink_to(outside)
        except OSError:
            self.skipTest("This Windows account cannot create a symlink")
        self.assert_code("unsafe_path", "preview", {"run_id": run["id"]})
        (self.base / "study/.lock").write_text("existing lock")
        self.assert_code("study_locked", "monitor", {"run_id": run["id"]})
        self.assertTrue((self.base / "study/.lock").exists())

    def test_missing_content_explicitly_unavailable(self) -> None:
        run = next(item for item in self.create()["runs"] if item["arm"] == "C")
        prepared = self.lab.action("prepare", {"run_id": run["id"]})
        self.assertEqual(prepared["setup"]["status"], "unavailable")
        self.assertFalse(self.preflight(run)["can_start"])

    def test_tampered_ledger_id_cannot_escape_owned_directories(self) -> None:
        self.create()
        state_path = self.base / "study/state.json"
        state = json.loads(state_path.read_text())
        unsafe_id = "../../outside"
        state["runs"][0]["id"] = unsafe_id
        state_path.write_text(json.dumps(state))
        self.assert_code("invalid_id", "prepare", {"run_id": unsafe_id})
        self.assertFalse((self.base / "outside").exists())

    def _assert_invalid_export(self, payload: Any) -> None:
        with self.assertRaises(LabError) as caught:
            validate_export(payload)
        self.assertEqual(caught.exception.code, "invalid_export")

    def test_read_bytes_too_large_and_export_cross_field_validation(self) -> None:
        oversized = self.base / "oversized.txt"
        oversized.write_bytes(b"abcdef")
        with self.assertRaises(LabError) as caught:
            read_bytes(oversized, 3)
        self.assertEqual(caught.exception.code, "too_large")

        for non_object in ([], "not-an-object", 7, None):
            self._assert_invalid_export(non_object)

        snapshot = self.create()
        first_group = snapshot["groups"][0]
        second_group = snapshot["groups"][1]
        for run in snapshot["runs"]:
            if run["group_id"] == first_group["id"]:
                self.complete(run)
        second_runs = [run for run in snapshot["runs"] if run["group_id"] == second_group["id"]]
        self.lab.action("finish", {"run_id": second_runs[0]["id"], "status": "failed"})
        self.lab.action("retry", {"run_id": second_runs[0]["id"]})
        baseline = self.lab.action("export", {})["export"]
        self.assertEqual(validate_export(baseline), baseline)

        completed_missing_preflight = copy.deepcopy(baseline)
        target_run = next(
            item for item in completed_missing_preflight["runs"] if item["status"] == "completed"
        )
        target_run["preflight"] = None
        completed_missing_preflight["report"] = report(completed_missing_preflight)
        self._assert_invalid_export(completed_missing_preflight)

        planned_with_finish = copy.deepcopy(baseline)
        planned_run = next(
            item for item in planned_with_finish["runs"] if item["status"] == "planned"
        )
        planned_run["finished_at"] = "2026-04-01T00:00:00+00:00"
        planned_with_finish["report"] = report(planned_with_finish)
        self._assert_invalid_export(planned_with_finish)

        failed_start_without_preflight = copy.deepcopy(baseline)
        failed_run = next(
            item for item in failed_start_without_preflight["runs"] if item["status"] == "failed"
        )
        failed_run["started_at"] = "2026-04-01T00:00:00+00:00"
        failed_run["preflight"] = None
        failed_start_without_preflight["report"] = report(failed_start_without_preflight)
        self._assert_invalid_export(failed_start_without_preflight)

        false_complete_group = copy.deepcopy(baseline)
        incomplete_group = next(
            item for item in false_complete_group["groups"] if item["id"] == second_group["id"]
        )
        incomplete_group["status"] = "complete"
        false_complete_group["report"] = report(false_complete_group)
        self._assert_invalid_export(false_complete_group)

        false_incomplete_group = copy.deepcopy(baseline)
        complete_group = next(
            item for item in false_incomplete_group["groups"] if item["id"] == first_group["id"]
        )
        complete_group["status"] = "incomplete"
        false_incomplete_group["report"] = report(false_incomplete_group)
        self._assert_invalid_export(false_incomplete_group)

        mismatched_retry = copy.deepcopy(baseline)
        retry_run = next(item for item in mismatched_retry["runs"] if item["attempt"] == 2)
        retry_run["case_id"] = first_group["case_id"]
        mismatched_retry["report"] = report(mismatched_retry)
        self._assert_invalid_export(mismatched_retry)

        duplicate_pair = copy.deepcopy(baseline)
        for item in duplicate_pair["groups"]:
            if item["id"] == second_group["id"]:
                item["case_id"] = first_group["case_id"]
        for item in duplicate_pair["runs"]:
            if item["group_id"] == second_group["id"]:
                item["case_id"] = first_group["case_id"]
        duplicate_pair["report"] = report(duplicate_pair)
        self._assert_invalid_export(duplicate_pair)

    def test_merge_exports_deduplicates_and_rejects_symlinks(self) -> None:
        self.create()
        first_export = self.lab.action("export", {})["export"]
        other_lab = Lab(self.base / "study-two", self.pack)
        other_lab.action(
            "create", {"phase": "calibration", "cells": ["windows-cowork"], "budget": 6, "seed": 23}
        )
        second_export = other_lab.action("export", {})["export"]

        first_path = self.base / "first.json"
        duplicate_path = self.base / "first-copy.json"
        second_path = self.base / "second.json"
        first_path.write_text(json.dumps(first_export), encoding="utf-8")
        duplicate_path.write_text(json.dumps(first_export), encoding="utf-8")
        second_path.write_text(json.dumps(second_export), encoding="utf-8")

        merger = ROOT / "tools/evaluation-lab/merge-exports.py"
        merged_path = self.base / "merged.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(merger),
                str(first_path),
                str(duplicate_path),
                str(second_path),
                "--output",
                str(merged_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        merged = json.loads(merged_path.read_text(encoding="utf-8"))
        self.assertEqual(len(merged["source_study_ids"]), 2)
        existing_bytes = merged_path.read_bytes()

        overwrite = subprocess.run(
            [sys.executable, str(merger), str(first_path), "--output", str(merged_path)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertNotEqual(overwrite.returncode, 0)
        self.assertEqual(merged_path.read_bytes(), existing_bytes)

        linked_input = self.base / "linked-input.json"
        linked_output = self.base / "linked-output.json"
        outside_target = self.base / "outside-target.json"
        try:
            linked_input.symlink_to(first_path)
            linked_output.symlink_to(outside_target)
        except OSError:
            return
        bad_in = subprocess.run(
            [
                sys.executable,
                str(merger),
                str(linked_input),
                "--output",
                str(self.base / "unused.json"),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertNotEqual(bad_in.returncode, 0)
        self.assertFalse((self.base / "unused.json").exists())
        bad_out = subprocess.run(
            [sys.executable, str(merger), str(first_path), "--output", str(linked_output)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertNotEqual(bad_out.returncode, 0)
        self.assertFalse(outside_target.exists())


if __name__ == "__main__":
    unittest.main()

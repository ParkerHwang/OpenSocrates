"""Independent negative controls for scoped completion and native memory revisions."""

from __future__ import annotations

import copy
import io
import json
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import check_project_memory as memory_checks
from check_assistance import request as assistance_request
from opensocrates.assistance.policy import InvalidAssistanceRequest, plan_assistance
from opensocrates.cli.assistance import run_assistance
from opensocrates.project_memory.contracts import load_schema, validate
from opensocrates.project_memory.service import handle_memory
from opensocrates.project_memory.store import MemoryStore

uid = memory_checks.uid


def obligation(identifier, *, kind="work", status="unmet", deps=(), required=True, question="main"):
    return {
        "obligation_id": identifier,
        "question_id": question,
        "kind": kind,
        "required": required,
        "status": status,
        "evidence_refs": ["check:fixture"] if status == "met" else [],
        "attribution": "agent_reported",
        "depends_on": list(deps),
    }


class ObligationTests(unittest.TestCase):
    def test_v2_cli_success_and_failure_keep_recognized_schema(self):
        value = assistance_request()
        value.update(
            schema="opensocrates.assistance.request/1.1.0",
            obligations=[obligation("done", status="met")],
        )
        for extra, expected in (({}, 0), ({"unknown": True}, 2)):
            output = io.StringIO()
            self.assertEqual(
                run_assistance(io.StringIO(json.dumps({**value, **extra})), output), expected
            )
            result = json.loads(output.getvalue())
            self.assertEqual(result["schema"], "opensocrates.assistance.plan/1.1.0")
            validate(result, load_schema("assistance-plan-v2.schema.json"))

    def plan(self, items, **task):
        value = assistance_request(**task)
        value.update(schema="opensocrates.assistance.request/1.1.0", obligations=items)
        result = plan_assistance(value)
        validate(result, load_schema("assistance-plan-v2.schema.json"))
        return result

    def test_global_green_does_not_hide_a_required_failure(self):
        for status in ("unmet", "unverified", "not_recorded", "not_applicable"):
            result = self.plan([obligation("legacy", status=status)], completion="checks_satisfied")
            self.assertEqual(result["next_action"], "continue")
            self.assertEqual(result["obligation_summary"]["blocking_ids"], ["legacy"])
        self.assertNotEqual(self.plan([], completion="checks_satisfied")["next_action"], "finish")

    def test_side_question_and_missing_input_preserve_independent_work(self):
        nodes = [
            obligation("approval", kind="input", question="budget"),
            obligation("booking", deps=["approval"]),
            obligation("draft"),
            obligation("side-answer", status="met", question="capacity"),
        ]
        result = self.plan(nodes, completion="dependent_input_missing")
        summary = result["obligation_summary"]
        self.assertEqual(result["next_action"], "continue")
        self.assertEqual(summary["ready_ids"], ["draft"])
        self.assertEqual(summary["input_ids"], ["approval"])
        self.assertEqual(summary["waiting_ids"], ["booking"])
        self.assertTrue(summary["questions"][-1]["required_complete"])
        nodes[2] = obligation("draft", status="met")
        self.assertEqual(self.plan(nodes)["next_action"], "resolve_dependency")

    def test_completion_still_needs_attributed_evidence_and_valid_dependencies(self):
        self.assertEqual(self.plan([obligation("done", status="met")])["next_action"], "finish")
        self.assertNotEqual(
            self.plan([obligation("done", status="met")], material_change=True)["next_action"],
            "finish",
        )
        for field, value in (("evidence_refs", []), ("attribution", "unknown")):
            item = obligation("done", status="met")
            item[field] = value
            self.assertNotEqual(
                self.plan([item], completion="checks_satisfied")["next_action"], "finish"
            )
        for items in (
            [obligation("a", deps=["a"])],
            [obligation("a", deps=["missing"])],
            [obligation("a"), obligation("a")],
            [obligation("a", deps=["b"]), obligation("b", deps=["a"])],
        ):
            with self.assertRaises(InvalidAssistanceRequest):
                self.plan(items)
        nodes = [obligation("optional", required=False), obligation("done", status="met")]
        self.assertEqual(self.plan(nodes)["next_action"], "finish")

    def test_existing_assistance_contract_stays_unextended(self):
        value = assistance_request()
        self.assertEqual(plan_assistance(value)["schema"], "opensocrates.assistance.plan/1.0.0")
        value["obligations"] = []
        with self.assertRaises(InvalidAssistanceRequest):
            plan_assistance(value)

    def test_optional_inputs_do_not_become_required_and_global_dependency_survives(self):
        optional = obligation("suggestion", kind="input", required=False)
        self.assertEqual(self.plan([optional])["next_action"], "continue")
        nodes = [optional, obligation("required-work", deps=["suggestion"])]
        self.assertEqual(self.plan(nodes)["next_action"], "resolve_dependency")
        self.assertEqual(
            self.plan(nodes)["obligation_summary"]["required_input_ids"], ["suggestion"]
        )
        result = self.plan([obligation("done", status="met")], completion="dependent_input_missing")
        self.assertEqual(result["next_action"], "resolve_dependency")


class MemoryRevisionTests(unittest.TestCase):
    setUp = memory_checks.MemoryFixture.setUp
    request = memory_checks.MemoryFixture.request
    call = memory_checks.MemoryFixture.call
    enroll = memory_checks.MemoryFixture.enroll

    def revised(self, operation, payload, task=None):
        value = self.request(operation, payload, task_id=task)
        value["schema"] = "opensocrates.project-memory.request/1.1.0"
        return handle_memory(value, registry=self.registry)

    def bytes(self):
        return {
            str(p.relative_to(self.data)): p.read_bytes()
            for p in self.data.rglob("*")
            if p.is_file()
        }

    def prepare(self, task):
        return self.revised("prepare", {"target_operation": "checkpoint"}, task)

    @staticmethod
    def fill(prepared):
        value = copy.deepcopy(prepared["result"]["request"])
        value["payload"].update(
            objective="Preserve access and update the plan.",
            constraints=["Step-free access required."],
            completion_conditions=["The plan agrees with current capacity."],
            next_action="Read the changed source before continuing.",
        )
        return value

    def accepted(self, text):
        created = self.call(
            "record",
            {
                "idempotency_key": uid(),
                "expected_record_version": 0,
                "kind": "decision",
                "scope": {"level": "project"},
                "summary": text,
                "origin": {
                    "producer_kind": "agent",
                    "source_reference": None,
                    "attestation": "agent_reported",
                },
                "support": "agent_reported",
                "source_refs": [],
                "revalidation": {
                    "dependency_paths": [],
                    "negative_claim": False,
                    "on_change": "not_applicable",
                },
            },
        )
        self.assertEqual(created["status"], "ok", created)
        identifier = created["result"]["record"]["record_id"]
        self.assertEqual(
            self.call(
                "accept",
                {
                    "record_id": identifier,
                    "expected_record_version": 1,
                    "idempotency_key": uid(),
                    "acceptance_basis": "fixture:approved",
                    "acceptance_attribution": "operator_declared",
                },
            )["status"],
            "ok",
        )
        return identifier

    def test_prepare_no_initialization_migration_backup_expiry_or_inferred_task(self):
        task = uid()
        self.assertEqual(self.prepare(task)["status"], "invalid_request")
        self.assertFalse(self.data.exists())
        self.enroll()
        before = self.bytes()
        with patch.object(
            MemoryStore, "ensure_current", side_effect=AssertionError("write path called")
        ):
            prepared = self.prepare(task)
        self.assertEqual(prepared["status"], "ok", prepared)
        self.assertTrue(prepared["result"]["prepared_only"])
        self.assertEqual(self.bytes(), before)
        self.assertEqual(self.prepare(None)["status"], "invalid_request")
        store = MemoryStore(self.registry.project_dir(self.project_id))
        with sqlite3.connect(store.path) as db:
            db.execute("DROP TABLE migration_audit")
            db.execute("UPDATE meta SET value='1' WHERE key='schema_version'")
        old = self.bytes()
        self.assertEqual(self.prepare(task)["status"], "unavailable")
        self.assertEqual(self.bytes(), old)
        store.ensure_current()
        manifest = json.loads(store.backup_manifest_path.read_text())
        manifest["verified_at"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        store._write_backup_manifest(manifest)
        expired = self.bytes()
        self.assertEqual(self.prepare(task)["status"], "ok")
        self.assertEqual(self.bytes(), expired)
        # A missing registered store must not be recreated by preparation.
        missing = store.path.with_suffix(".saved")
        store.path.rename(missing)
        before = self.bytes()
        self.assertEqual(self.prepare(task)["status"], "unavailable")
        self.assertEqual(self.bytes(), before)

    def test_prepared_submission_replay_cas_and_typed_recall(self):
        self.enroll()
        task = uid()
        approved = self.accepted("Keep step-free access.")
        prepared = self.prepare(task)
        first = self.fill(prepared)
        result = handle_memory(first, registry=self.registry)
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(handle_memory(first, registry=self.registry)["result"], result["result"])
        left = self.fill(self.prepare(task))
        right = self.fill(self.prepare(task))
        self.assertEqual(left["payload"]["expected_checkpoint_version"], 1)
        self.assertEqual(handle_memory(left, registry=self.registry)["status"], "ok")
        self.assertEqual(handle_memory(right, registry=self.registry)["status"], "conflict")
        payload = {"need": "resume", "budget_bytes": 65536}
        old = self.call("recall", payload, task_id=task)["result"]
        new = self.revised("recall", payload, task)["result"]
        validate(old, load_schema("project-memory-context-pack.schema.json"))
        validate(new, load_schema("project-memory-context-pack-v2.schema.json"))
        self.assertNotIn("checkpoint", old)
        self.assertEqual(new["checkpoint"]["checkpoint_version"], 2)
        self.assertEqual(new["checkpoint"]["lifecycle"], "proposed")
        by_id = {item["record_id"]: item for item in new["constraints"]}
        self.assertEqual(by_id[approved]["lifecycle"], "accepted")
        self.assertEqual(by_id[new["checkpoint_reference"]]["support"], "agent_reported")
        deleted = self.call(
            "delete",
            {
                "intent": "delete_record",
                "record_id": new["checkpoint_reference"],
                "expected_record_version": 2,
                "idempotency_key": uid(),
            },
        )
        self.assertEqual(deleted["status"], "ok", deleted)
        after = self.revised("recall", payload, task)["result"]
        self.assertIsNone(after["checkpoint"])
        self.assertEqual([item["record_id"] for item in after["decisions"]], [approved])

    def test_source_delivery_scope_keeps_intent_and_original_revalidation(self):
        for name in ("a", "ab"):
            (self.root / name).mkdir()
            (self.root / name / "brief.md").write_text("Alpha capacity is 64.")
        self.enroll()
        task = uid()
        approved = self.accepted("No booking is authorized.")
        observed = self.call("observe", {"query": "Alpha", "idempotency_key": uid()})
        self.assertEqual(observed["status"], "ok", observed)
        payload = {"need": "irrelevant terms", "budget_bytes": 65536, "scope_paths": ["a"]}
        result = self.revised("recall", payload, task)
        self.assertEqual(result["status"], "ok", result)
        pack = result["result"]
        self.assertEqual(pack["searched_scope"], ["a"])
        self.assertIn([], pack["revalidation_scopes"])
        self.assertEqual({r["locator"]["path"] for r in pack["source_evidence"]}, {"a/brief.md"})
        self.assertIn(approved, [r["record_id"] for r in pack["decisions"]])
        (self.root / "ab/brief.md").write_text("Alpha capacity changed to 40.")
        changed = self.revised("recall", payload, task)["result"]
        self.assertFalse(changed["source_evidence"])
        self.assertTrue(any("stale" in item for item in changed["unknowns"]))
        self.assertEqual(
            self.revised("recall", {**payload, "scope_paths": ["../outside"]}, task)["status"],
            "unavailable",
        )

    def test_existing_accepted_checkpoint_remains_readable(self):
        self.enroll()
        task = uid()
        created = handle_memory(self.fill(self.prepare(task)), registry=self.registry)
        identifier = created["result"]["record_id"]
        result = self.call(
            "accept",
            {
                "record_id": identifier,
                "expected_record_version": 1,
                "idempotency_key": uid(),
                "acceptance_basis": "fixture:accepted-checkpoint",
                "acceptance_attribution": "operator_declared",
            },
        )
        self.assertEqual(result["status"], "ok", result)
        recalled = self.revised("recall", {"need": "resume", "budget_bytes": 65536}, task)
        self.assertEqual(recalled["status"], "ok", recalled)
        self.assertEqual(recalled["result"]["checkpoint"]["lifecycle"], "accepted")
        self.assertEqual(recalled["result"]["checkpoint_reference"], identifier)

    def test_prepare_cannot_enable_capture_or_disabled_memory(self):
        self.enroll(mode="read_only")
        task = uid()
        prepared = self.prepare(task)
        self.assertEqual(prepared["status"], "ok", prepared)
        self.assertEqual(
            handle_memory(self.fill(prepared), registry=self.registry)["status"], "disabled"
        )
        disabled = self.call("disable", {"expected_policy_version": 1, "idempotency_key": uid()})
        self.assertEqual(disabled["status"], "ok", disabled)
        self.assertEqual(self.prepare(task)["status"], "disabled")

    def test_diagnostics_never_echo_unknown_keys_or_values(self):
        for payload in (
            {"SECRET_CANARY": "sensitive"},
            {"budget_bytes": "SECRET_CANARY", "need": "resume"},
            {"budget_bytes": 4096},
        ):
            result = self.revised("recall", payload, uid())
            self.assertEqual(result["status"], "invalid_request")
            self.assertNotIn("SECRET_CANARY", json.dumps(result))
            self.assertIn("field_path", result["result"])

    def test_revised_required_intent_overflow_is_explicit(self):
        self.enroll()
        for index in range(33):
            self.accepted(f"Constraint {index}.")
        result = self.revised("recall", {"need": "one tiny result", "budget_bytes": 65536}, uid())
        self.assertEqual(result["status"], "budget_insufficient")
        self.assertEqual(result["result"]["required_item_counts"]["constraints"], 33)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Disposable filesystem acceptance for the explicit memory boundary."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from opensocrates.persistence.locks import FileLock
from opensocrates.project_memory.registry import ProjectRegistry
from opensocrates.project_memory.service import handle_memory
from opensocrates.project_memory.store import MemoryStore


def uid() -> str:
    return str(uuid4())


class MemoryFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "project"
        self.root.mkdir()
        self.data = self.base / "owned-data"
        self.registry = ProjectRegistry(self.data)
        self.project_id: str | None = None
        self.workspace_id: str | None = None

    def request(
        self, operation: str, payload: dict[str, object], *, task_id: str | None = None
    ) -> dict[str, object]:
        return {
            "schema": "opensocrates.project-memory.request/1.0.0",
            "operation": operation,
            "request_id": uid(),
            "project_id": self.project_id,
            "workspace_id": self.workspace_id,
            "task_id": task_id,
            "payload": payload,
        }

    def call(
        self, operation: str, payload: dict[str, object], *, task_id: str | None = None
    ) -> dict[str, object]:
        return handle_memory(
            self.request(operation, payload, task_id=task_id), registry=self.registry
        )

    def enroll(self, *, mode: str = "read_write") -> None:
        payload: dict[str, object] = {
            "root": str(self.root),
            "apply": False,
            "mode": mode,
            "capture_policy": "milestones",
            "excluded_paths": [],
        }
        preview = self.call("init", payload)
        self.assertEqual(preview["status"], "ok")
        self.assertFalse(self.data.exists())
        payload.update(
            {
                "apply": True,
                "disclosure_digest": preview["result"]["disclosure_digest"],
                "authorization_basis": "fixture:enrollment",
                "authorization_attribution": "operator_declared",
                "idempotency_key": uid(),
            }
        )
        enrolled = self.call("init", payload)
        self.assertEqual(enrolled["status"], "ok", enrolled)
        replayed = self.call("init", payload)
        self.assertEqual(replayed["result"], enrolled["result"])
        self.project_id = enrolled["result"]["project_id"]
        self.workspace_id = enrolled["result"]["workspace_id"]

    def test_disabled_preview_and_unknown_fields_create_nothing(self) -> None:
        self.assertEqual(self.call("status", {})["status"], "disabled")
        self.assertFalse(self.data.exists())
        bad = self.request("status", {"surprise": True})
        self.assertEqual(handle_memory(bad, registry=self.registry)["status"], "invalid_request")
        self.assertFalse(self.data.exists())
        self.enroll()

    def test_authorization_basis_rejects_secret_before_storage(self) -> None:
        payload: dict[str, object] = {
            "root": str(self.root),
            "apply": False,
            "mode": "read_write",
            "capture_policy": "milestones",
            "excluded_paths": [],
        }
        preview = self.call("init", payload)
        payload.update(
            {
                "apply": True,
                "disclosure_digest": preview["result"]["disclosure_digest"],
                "authorization_basis": "api_key=SUPER_SECRET_CANARY",
                "authorization_attribution": "operator_declared",
                "idempotency_key": uid(),
            }
        )
        self.assertEqual(self.call("init", payload)["status"], "invalid_request")
        self.assertFalse(self.data.exists())

    def test_nongit_cold_resume_stale_source_and_forgetting(self) -> None:
        brief = self.root / "brief.md"
        brief.write_text("Venue capacity: 40.\n", encoding="utf-8")
        self.enroll()
        observed = self.call("observe", {"path": "brief.md", "idempotency_key": uid()})
        self.assertEqual(observed["status"], "ok", observed)
        reference = observed["result"]["reference"]
        decision = self.call(
            "record",
            {
                "idempotency_key": uid(),
                "expected_record_version": 0,
                "kind": "decision",
                "scope": {"level": "project"},
                "summary": "Keep wheelchair access in the event plan.",
                "origin": {
                    "producer_kind": "agent",
                    "source_reference": None,
                    "attestation": "agent_reported",
                },
                "support": "agent_reported",
                "source_refs": [reference["ref_id"]],
                "snapshot_id": observed["result"]["snapshot"]["snapshot_id"],
                "revalidation": {
                    "dependency_paths": ["brief.md"],
                    "negative_claim": False,
                    "on_change": "refresh_or_mark_stale",
                },
            },
        )
        self.assertEqual(decision["status"], "ok", decision)
        record_id = decision["result"]["record"]["record_id"]
        accepted = self.call(
            "accept",
            {
                "record_id": record_id,
                "expected_record_version": 1,
                "idempotency_key": uid(),
                "acceptance_basis": "fixture:acceptance",
                "acceptance_attribution": "operator_declared",
            },
        )
        self.assertEqual(accepted["status"], "ok", accepted)
        task_id = uid()
        checkpoint = self.call(
            "checkpoint",
            {
                "idempotency_key": uid(),
                "expected_checkpoint_version": 0,
                "objective": "Update event plan",
                "constraints": ["Keep wheelchair access."],
                "completion_conditions": ["Capacity checked"],
                "completed_actions": [],
                "remaining_actions": ["Revise attendee layout"],
                "next_action": "Read venue brief",
                "blockers": [],
                "decision_refs": [record_id],
                "source_refs": [reference["ref_id"]],
                "snapshot_id": observed["result"]["snapshot"]["snapshot_id"],
                "conflict_ids": [],
                "pending_effects": [],
                "parent_checkpoint_id": None,
            },
            task_id=task_id,
        )
        self.assertEqual(checkpoint["status"], "ok", checkpoint)
        fresh = handle_memory(
            self.request(
                "recall",
                {
                    "need": "event capacity accessibility",
                    "budget_bytes": 8192,
                },
                task_id=task_id,
            ),
            registry=ProjectRegistry(self.data),
        )
        self.assertEqual(fresh["status"], "ok", fresh)
        self.assertEqual(fresh["result"]["decisions"][0]["record_id"], record_id)
        self.assertTrue(fresh["result"]["source_evidence"])
        brief.write_text("Venue capacity: 80.\n", encoding="utf-8")
        stale = self.call(
            "recall", {"need": "event capacity", "budget_bytes": 8192}, task_id=task_id
        )
        self.assertEqual(stale["status"], "ok", stale)
        self.assertEqual(stale["result"]["source_evidence"], [])
        self.assertEqual(stale["result"]["decisions"][0]["freshness"], "stale")
        self.assertEqual(
            self.call(
                "delete",
                {
                    "intent": "delete_record",
                    "record_id": record_id,
                    "expected_record_version": 2,
                    "idempotency_key": uid(),
                },
            )["status"],
            "ok",
        )
        exported = self.call("export", {"format": "json"})
        self.assertNotIn(
            "wheelchair access in the event plan", json.dumps(exported, ensure_ascii=False)
        )

    def test_git_new_caller_invalidates_negative_claim(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "helper.py").write_text("def helper():\n    return 1\n")
        subprocess.run(["git", "-C", str(self.root), "add", "helper.py"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
            check=True,
        )
        self.enroll()
        snapshot = self.call("refresh", {"idempotency_key": uid()})["result"]["snapshot"]
        record = self.call(
            "record",
            {
                "idempotency_key": uid(),
                "expected_record_version": 0,
                "kind": "observation",
                "scope": {"level": "workspace", "workspace_id": self.workspace_id},
                "summary": "No callers found in the declared inventory.",
                "origin": {
                    "producer_kind": "agent",
                    "source_reference": None,
                    "attestation": "agent_reported",
                },
                "support": "agent_reported",
                "source_refs": [],
                "snapshot_id": snapshot["snapshot_id"],
                "revalidation": {
                    "dependency_paths": ["helper.py"],
                    "negative_claim": True,
                    "on_change": "refresh_or_mark_stale",
                },
            },
        )
        self.assertEqual(record["status"], "ok", record)
        (self.root / "new_caller.py").write_text("from helper import helper\nhelper()\n")
        pack = self.call("recall", {"need": "callers", "budget_bytes": 8192}, task_id=uid())
        self.assertEqual(pack["status"], "ok", pack)
        self.assertTrue(any(":stale" in item for item in pack["result"]["unknowns"]))

    def test_explicit_second_git_worktree_shares_intent_not_checkpoint(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "guide.md").write_text("Keep access.\n")
        subprocess.run(["git", "-C", str(self.root), "add", "guide.md"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
            check=True,
        )
        self.enroll()
        task_id = uid()
        decision = self.call(
            "record",
            {
                "idempotency_key": uid(),
                "expected_record_version": 0,
                "kind": "decision",
                "scope": {"level": "project"},
                "summary": "Keep access in every event plan.",
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
        record_id = decision["result"]["record"]["record_id"]
        self.assertEqual(
            self.call(
                "accept",
                {
                    "record_id": record_id,
                    "expected_record_version": 1,
                    "idempotency_key": uid(),
                    "acceptance_basis": "fixture:worktree-intent",
                    "acceptance_attribution": "operator_declared",
                },
            )["status"],
            "ok",
        )
        self.assertEqual(
            self.call(
                "checkpoint",
                {
                    "idempotency_key": uid(),
                    "expected_checkpoint_version": 0,
                    "objective": "Root task",
                    "constraints": ["Root-only step"],
                    "completion_conditions": ["Done"],
                    "completed_actions": [],
                    "remaining_actions": ["Root-only action"],
                    "next_action": "Continue root",
                    "blockers": [],
                    "decision_refs": [record_id],
                    "source_refs": [],
                    "snapshot_id": None,
                    "conflict_ids": [],
                    "pending_effects": [],
                    "parent_checkpoint_id": None,
                },
                task_id=task_id,
            )["status"],
            "ok",
        )
        other = self.base / "second-worktree"
        subprocess.run(
            ["git", "-C", str(self.root), "worktree", "add", "-q", "--detach", str(other)],
            check=True,
        )
        payload: dict[str, object] = {
            "root": str(other),
            "apply": False,
            "mode": "read_write",
            "capture_policy": "milestones",
            "excluded_paths": [],
            "expected_policy_version": 1,
        }
        preview = self.call("init", payload)
        self.assertEqual(preview["status"], "ok", preview)
        payload.update(
            {
                "apply": True,
                "disclosure_digest": preview["result"]["disclosure_digest"],
                "authorization_basis": "fixture:second-worktree",
                "authorization_attribution": "operator_declared",
                "idempotency_key": uid(),
            }
        )
        joined = self.call("init", payload)
        self.assertEqual(joined["status"], "ok", joined)
        second = joined["result"]["workspace_id"]
        recalled = handle_memory(
            {
                **self.request(
                    "recall", {"need": "event access", "budget_bytes": 8192}, task_id=task_id
                ),
                "workspace_id": second,
            },
            registry=ProjectRegistry(self.data),
        )
        self.assertEqual(recalled["status"], "ok", recalled)
        self.assertEqual(recalled["result"]["decisions"][0]["record_id"], record_id)
        self.assertIsNone(recalled["result"]["checkpoint_reference"])

    def test_modes_idempotency_and_secret_canary(self) -> None:
        self.enroll()
        payload = {
            "idempotency_key": uid(),
            "expected_record_version": 0,
            "kind": "decision",
            "scope": {"level": "project"},
            "summary": "Keep a short public plan.",
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
        }
        first = self.call("record", payload)
        second = self.call("record", payload)
        self.assertEqual(first["result"], second["result"])
        changed = dict(payload, summary="Changed under same idempotency key.")
        self.assertEqual(self.call("record", changed)["status"], "conflict")
        secret = dict(payload, idempotency_key=uid(), summary="api_key=SUPER_SECRET_CANARY")
        self.assertEqual(self.call("record", secret)["status"], "invalid_request")
        database = self.data / "projects" / str(self.project_id) / "memory.sqlite3"
        self.assertNotIn(b"SUPER_SECRET_CANARY", database.read_bytes())
        disable_key = uid()
        policy = self.call(
            "disable", {"expected_policy_version": 1, "idempotency_key": disable_key}
        )
        self.assertEqual(policy["status"], "ok")
        replay = self.call(
            "disable", {"expected_policy_version": 1, "idempotency_key": disable_key}
        )
        self.assertEqual(replay["result"], policy["result"])
        self.assertEqual(
            self.call(
                "disable",
                {
                    "expected_policy_version": 1,
                    "idempotency_key": uid(),
                },
            )["status"],
            "conflict",
        )
        self.assertEqual(
            self.call("recall", {"need": "plan", "budget_bytes": 8192})["status"], "disabled"
        )
        self.assertEqual(self.call("export", {"format": "json"})["status"], "ok")

    def test_project_delete_preserves_unknown_and_rejects_links_and_busy(self) -> None:
        self.enroll()
        directory = self.data / "projects" / str(self.project_id)
        database = directory / "memory.sqlite3"
        lock = directory / "memory.lock"
        delete = {
            "intent": "delete_project",
            "idempotency_key": uid(),
            "expected_policy_version": 1,
        }
        unknown = directory / "unrelated.txt"
        unknown.write_text("preserve me", encoding="utf-8")
        partial = self.call("delete", delete)
        self.assertEqual(partial["status"], "partial")
        self.assertEqual(unknown.read_text(), "preserve me")
        self.assertEqual(self.call("status", {})["result"]["policy"]["version"], 1)
        unknown.unlink()
        other = self.base / "database-link"
        os.link(database, other)
        self.assertEqual(self.call("delete", delete)["status"], "unavailable")
        self.assertTrue(other.exists())
        other.unlink()
        backup = self.base / "database-original"
        database.rename(backup)
        database.symlink_to(backup)
        self.assertEqual(self.call("delete", delete)["status"], "unavailable")
        database.unlink()
        backup.rename(database)
        with FileLock(lock):
            self.assertEqual(self.call("delete", delete)["status"], "busy")
        self.assertEqual(self.call("delete", delete)["status"], "ok")
        self.assertFalse(directory.exists())
        self.assertFalse(database.exists())

    def test_source_dependency_requires_snapshot_and_stale_constraint_is_labeled(self) -> None:
        (self.root / "brief.md").write_text("Capacity 40.\n")
        self.enroll()
        observed = self.call("observe", {"path": "brief.md", "idempotency_key": uid()})
        reference = observed["result"]["reference"]
        payload = {
            "idempotency_key": uid(),
            "expected_record_version": 0,
            "kind": "decision",
            "scope": {"level": "project"},
            "summary": "Capacity is 40.",
            "origin": {
                "producer_kind": "agent",
                "source_reference": None,
                "attestation": "agent_reported",
            },
            "support": "agent_reported",
            "source_refs": [reference["ref_id"]],
            "revalidation": {
                "dependency_paths": ["brief.md"],
                "negative_claim": False,
                "on_change": "refresh_or_mark_stale",
            },
        }
        self.assertEqual(self.call("record", payload)["status"], "invalid_request")
        payload["idempotency_key"] = uid()
        payload["snapshot_id"] = observed["result"]["snapshot"]["snapshot_id"]
        created = self.call("record", payload)
        self.assertEqual(created["status"], "ok", created)
        accepted = self.call(
            "accept",
            {
                "record_id": created["result"]["record"]["record_id"],
                "expected_record_version": 1,
                "idempotency_key": uid(),
                "acceptance_basis": "fixture:capacity-choice",
                "acceptance_attribution": "operator_declared",
            },
        )
        self.assertEqual(accepted["status"], "ok", accepted)
        (self.root / "brief.md").write_text("Capacity 80.\n")
        pack = self.call("recall", {"need": "capacity", "budget_bytes": 8192}, task_id=uid())
        self.assertEqual(pack["status"], "ok", pack)
        self.assertEqual(pack["result"]["constraints"][0]["freshness"], "stale")
        self.assertEqual(pack["result"]["source_evidence"], [])

    def test_lexical_search_returns_citations_without_persisting_query(self) -> None:
        (self.root / "brief.md").write_text("Capacity 40.\nAccessible entrance.\n")
        self.enroll()
        key = uid()
        result = self.call("observe", {"query": "Capacity", "idempotency_key": key})
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["result"]["references"][0]["locator"]["path"], "brief.md")
        self.assertEqual(result["result"]["references"][0]["locator"]["line_start"], 1)
        self.assertEqual(
            self.call(
                "observe",
                {
                    "query": "Capacity",
                    "idempotency_key": key,
                },
            )["result"],
            result["result"],
        )
        negative = self.call(
            "observe",
            {
                "query": "missingphrase",
                "idempotency_key": uid(),
            },
        )
        self.assertEqual(negative["status"], "ok", negative)
        self.assertEqual(negative["result"]["references"], [])
        database = self.data / "projects" / str(self.project_id) / "memory.sqlite3"
        self.assertNotIn(b"Capacity 40", database.read_bytes())
        self.assertNotIn(b"missingphrase", database.read_bytes())
        (self.root / "new.md").write_text("missingphrase appears now.\n")
        pack = self.call("recall", {"need": "missingphrase", "budget_bytes": 8192}, task_id=uid())
        self.assertEqual(pack["status"], "ok", pack)
        self.assertTrue(any(":stale" in item for item in pack["result"]["unknowns"]))

    def test_snapshot_mutations_are_idempotent_and_response_bounded(self) -> None:
        for index in range(900):
            (self.root / f"note-{index:04d}.md").write_text("A\n")
        self.enroll()
        key = uid()
        first = self.call("refresh", {"idempotency_key": key})
        second = self.call("refresh", {"idempotency_key": key})
        self.assertEqual(first["status"], "ok", first)
        self.assertEqual(first["result"], second["result"])
        self.assertLess(len(json.dumps(first).encode()), 64 * 1024)
        key = uid()
        observed = self.call("observe", {"path": "note-0000.md", "idempotency_key": key})
        repeated = self.call("observe", {"path": "note-0000.md", "idempotency_key": key})
        self.assertEqual(observed["status"], "ok", observed)
        self.assertEqual(observed["result"], repeated["result"])
        database = self.data / "projects" / str(self.project_id) / "memory.sqlite3"
        with sqlite3.connect(database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0], 2)
        (self.root / "note-0000.md").write_text("B\n")
        self.assertEqual(
            self.call(
                "observe",
                {
                    "path": "note-0000.md",
                    "idempotency_key": key,
                },
            )["status"],
            "conflict",
        )
        with sqlite3.connect(database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0], 2)

    def test_newer_schema_and_corruption_never_reset_store(self) -> None:
        self.enroll()
        database = self.data / "projects" / str(self.project_id) / "memory.sqlite3"
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
        newer = database.read_bytes()
        self.assertEqual(self.call("inspect", {})["status"], "unavailable")
        self.assertEqual(self.call("status", {})["status"], "unavailable")
        self.assertEqual(database.read_bytes(), newer)
        database.write_bytes(b"not a SQLite database")
        corrupt = database.read_bytes()
        self.assertEqual(self.call("inspect", {})["status"], "unavailable")
        self.assertEqual(self.call("status", {})["status"], "unavailable")
        self.assertEqual(database.read_bytes(), corrupt)

    def test_interrupted_initialization_leaves_no_partial_schema(self) -> None:
        directory = self.base / "synthetic-store"
        directory.mkdir(mode=0o700)
        database = directory / "memory.sqlite3"
        database.touch(mode=0o600)
        script = (
            "import os,sqlite3,sys;"
            "db=sqlite3.connect(sys.argv[1]);"
            "db.execute('BEGIN IMMEDIATE');"
            "db.execute('CREATE TABLE partial_only (value TEXT)');"
            "os._exit(7)"
        )
        crashed = subprocess.run(
            [sys.executable, "-c", script, str(database)],
            capture_output=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(crashed.returncode, 7)
        MemoryStore(directory).initialize()
        with sqlite3.connect(database) as connection:
            names = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            self.assertNotIn("partial_only", names)
            self.assertTrue({"meta", "records", "checkpoints", "snapshots"} <= names)

    def test_cross_process_record_compare_and_swap(self) -> None:
        self.enroll()
        record_id = uid()
        payload = {
            "record_id": record_id,
            "expected_record_version": 0,
            "kind": "decision",
            "scope": {"level": "project"},
            "summary": "A synthetic public choice.",
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
        }
        environment = dict(os.environ)
        environment.update(
            {
                "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
                "OPENSOCRATES_MEMORY_FIXTURE": "1",
                "OPENSOCRATES_DEVELOPMENT_MANIFEST": "1",
                "OPENSOCRATES_DATA_DIR": str(self.data),
            }
        )
        processes = []
        for _ in range(2):
            value = self.request("record", dict(payload, idempotency_key=uid()))
            process = subprocess.Popen(
                [sys.executable, "-m", "opensocrates", "memory"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
            )
            assert process.stdin is not None
            process.stdin.write(json.dumps(value).encode())
            process.stdin.close()
            processes.append(process)
        statuses = []
        for process in processes:
            process.wait(timeout=10)
            assert process.stdout is not None
            statuses.append(json.loads(process.stdout.read())["status"])
            process.stdout.close()
            assert process.stderr is not None
            process.stderr.close()
        self.assertEqual(sorted(statuses), ["conflict", "ok"])
        self.assertEqual(self.call("inspect", {"record_id": record_id})["result"]["version"], 1)

    def test_user_correction_supersedes_scoped_intent(self) -> None:
        self.enroll()

        def accepted(summary: str, conflicts: list[str] | None = None) -> dict[str, object]:
            created = self.call(
                "record",
                {
                    "idempotency_key": uid(),
                    "expected_record_version": 0,
                    "kind": "decision",
                    "scope": {"level": "project"},
                    "summary": summary,
                    "origin": {
                        "producer_kind": "agent",
                        "source_reference": None,
                        "attestation": "agent_reported",
                    },
                    "support": "agent_reported",
                    "source_refs": [],
                    "conflict_ids": conflicts or [],
                    "revalidation": {
                        "dependency_paths": [],
                        "negative_claim": False,
                        "on_change": "not_applicable",
                    },
                },
            )
            self.assertEqual(created["status"], "ok", created)
            record_id = created["result"]["record"]["record_id"]
            result = self.call(
                "accept",
                {
                    "record_id": record_id,
                    "expected_record_version": 1,
                    "idempotency_key": uid(),
                    "acceptance_basis": "fixture:user-correction",
                    "acceptance_attribution": "operator_declared",
                },
            )
            self.assertEqual(result["status"], "ok", result)
            return result["result"]["record"]

        old = accepted("Plan for 40 guests.")
        new = accepted("Plan for 20 guests.", [old["record_id"]])
        updated = self.call(
            "supersede",
            {
                "record_id": old["record_id"],
                "new_record_id": new["record_id"],
                "expected_record_version": 2,
                "expected_new_record_version": 2,
                "idempotency_key": uid(),
                "reason": "User corrected attendance.",
            },
        )
        self.assertEqual(updated["status"], "ok", updated)
        recalled = self.call("recall", {"need": "guest plan", "budget_bytes": 8192}, task_id=uid())
        self.assertEqual(recalled["status"], "ok", recalled)
        self.assertEqual(
            [item["summary"] for item in recalled["result"]["decisions"]], ["Plan for 20 guests."]
        )
        self.assertEqual(recalled["result"]["conflicts"], [])

    def test_prune_preserves_referenced_records_and_replays_apply(self) -> None:
        (self.root / "brief.md").write_text("Accessible venue.\n")
        self.enroll()
        observation = self.call("observe", {"path": "brief.md", "idempotency_key": uid()})
        ref = observation["result"]["reference"]["ref_id"]
        snapshot_id = observation["result"]["snapshot"]["snapshot_id"]
        kept = self.call(
            "record",
            {
                "idempotency_key": uid(),
                "expected_record_version": 0,
                "kind": "decision",
                "scope": {"level": "project"},
                "summary": "Keep accessible venue.",
                "origin": {
                    "producer_kind": "agent",
                    "source_reference": None,
                    "attestation": "agent_reported",
                },
                "support": "agent_reported",
                "source_refs": [ref],
                "snapshot_id": snapshot_id,
                "revalidation": {
                    "dependency_paths": ["brief.md"],
                    "negative_claim": False,
                    "on_change": "refresh_or_mark_stale",
                },
            },
        )
        self.assertEqual(
            self.call(
                "accept",
                {
                    "record_id": kept["result"]["record"]["record_id"],
                    "expected_record_version": 1,
                    "idempotency_key": uid(),
                    "acceptance_basis": "fixture:retention",
                    "acceptance_attribution": "operator_declared",
                },
            )["status"],
            "ok",
        )
        disposable = self.call(
            "record",
            {
                "idempotency_key": uid(),
                "expected_record_version": 0,
                "kind": "lesson",
                "scope": {"level": "project"},
                "summary": "Old unaccepted proposal.",
                "origin": {
                    "producer_kind": "agent",
                    "source_reference": None,
                    "attestation": "agent_reported",
                },
                "support": "inferred",
                "source_refs": [],
                "revalidation": {
                    "dependency_paths": [],
                    "negative_claim": False,
                    "on_change": "not_applicable",
                },
            },
        )
        old = "2020-01-01T00:00:00Z"
        database = self.data / "projects" / str(self.project_id) / "memory.sqlite3"
        with sqlite3.connect(database) as connection:
            for record_id in (
                observation["result"]["observation_record_id"],
                disposable["result"]["record"]["record_id"],
            ):
                row = connection.execute(
                    "SELECT data FROM records WHERE record_id=?", (record_id,)
                ).fetchone()
                value = json.loads(row[0])
                value["updated_at"] = old
                connection.execute(
                    "UPDATE records SET data=? WHERE record_id=?", (json.dumps(value), record_id)
                )
        preview = self.call("prune", {"dry_run": True, "retention_days": 30})
        self.assertEqual(preview["status"], "ok", preview)
        self.assertEqual(
            preview["result"]["eligible_record_ids"], [disposable["result"]["record"]["record_id"]]
        )
        key = uid()
        applied = self.call(
            "prune",
            {
                "dry_run": False,
                "retention_days": 30,
                "idempotency_key": key,
            },
        )
        repeated = self.call(
            "prune",
            {
                "dry_run": False,
                "retention_days": 30,
                "idempotency_key": key,
            },
        )
        self.assertEqual(applied["status"], "ok", applied)
        self.assertEqual(applied["result"], repeated["result"])
        self.assertIsNotNone(
            self.call(
                "inspect",
                {
                    "record_id": observation["result"]["observation_record_id"],
                },
            )["result"]
        )

    def test_required_constraints_never_truncate_silently(self) -> None:
        self.enroll()
        for index in range(33):
            created = self.call(
                "record",
                {
                    "idempotency_key": uid(),
                    "expected_record_version": 0,
                    "kind": "decision",
                    "scope": {"level": "project"},
                    "summary": f"Constraint {index:02d}.",
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
            accepted = self.call(
                "accept",
                {
                    "record_id": created["result"]["record"]["record_id"],
                    "expected_record_version": 1,
                    "idempotency_key": uid(),
                    "acceptance_basis": f"fixture:constraint-{index:02d}",
                    "acceptance_attribution": "operator_declared",
                },
            )
            self.assertEqual(accepted["status"], "ok", accepted)
        pack = self.call("recall", {"need": "constraints", "budget_bytes": 65536}, task_id=uid())
        self.assertEqual(pack["status"], "budget_insufficient", pack)
        self.assertEqual(pack["result"]["required_item_counts"]["constraints"], 33)


if __name__ == "__main__":
    unittest.main()

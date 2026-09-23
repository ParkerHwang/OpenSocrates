#!/usr/bin/env python3
"""Native fixture: isolated SQLite lifecycle and packaged v1.5 guide/schema bytes."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import stat
import subprocess
import tempfile
from contextlib import closing
from pathlib import Path
from uuid import uuid4


def uid() -> str:
    return str(uuid4())


def request(
    operation: str,
    payload: dict[str, object],
    project_id: str | None = None,
    workspace_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, object]:
    return {
        "schema": "opensocrates.project-memory.request/1.0.0",
        "operation": operation,
        "request_id": uid(),
        "project_id": project_id,
        "workspace_id": workspace_id,
        "task_id": task_id,
        "payload": payload,
    }


def run(binary: Path, environment: dict[str, str], value: dict[str, object]) -> dict[str, object]:
    completed = subprocess.run(
        [str(binary), "memory"],
        input=json.dumps(value).encode("utf-8"),
        capture_output=True,
        env=environment,
        check=False,
        timeout=15,
    )
    result = json.loads(completed.stdout)
    if completed.returncode != (0 if result["status"] != "unavailable" else 3):
        raise AssertionError(
            f"unexpected memory exit/status: {completed.returncode} {result['status']}"
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    binary_source = parser.add_mutually_exclusive_group(required=True)
    binary_source.add_argument("--binary", type=Path)
    binary_source.add_argument("--runtime-report", type=Path)
    parser.add_argument("--package", type=Path)
    args = parser.parse_args()
    if args.runtime_report is not None:
        report = json.loads(args.runtime_report.read_text(encoding="utf-8"))
        binary = (Path(__file__).resolve().parents[1] / report["artifact"]).resolve(strict=True)
    else:
        binary = args.binary.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="opensocrates-frozen-memory-") as tmp:
        sandbox = Path(tmp)
        data_root = sandbox / "data"
        source = sandbox / "event"
        if os.name == "nt":
            from opensocrates.persistence.permissions import create_owner_only_directory

            assert create_owner_only_directory(source)
        else:
            source.mkdir()
        brief = source / "brief.md"
        brief.write_text("Capacity: 40.\n", encoding="utf-8")
        env = dict(os.environ)
        env.update(
            {
                "OPENSOCRATES_MEMORY_FIXTURE": "1",
                "OPENSOCRATES_DEVELOPMENT_MANIFEST": "1",
                "OPENSOCRATES_DATA_DIR": str(data_root),
            }
        )
        status = run(binary, env, request("status", {}))
        assert status["status"] == "disabled" and not data_root.exists()
        payload: dict[str, object] = {
            "root": str(source),
            "apply": False,
            "mode": "read_write",
            "capture_policy": "milestones",
            "excluded_paths": [],
        }
        preview = run(binary, env, request("init", payload))
        assert preview["status"] == "ok" and not data_root.exists()
        payload.update(
            {
                "apply": True,
                "disclosure_digest": preview["result"]["disclosure_digest"],
                "authorization_basis": "fixture:native-enrollment",
                "authorization_attribution": "operator_declared",
                "idempotency_key": uid(),
            }
        )
        enrollment = run(binary, env, request("init", payload))
        assert enrollment["status"] == "ok", enrollment
        project_id = enrollment["result"]["project_id"]
        workspace_id = enrollment["result"]["workspace_id"]
        observed = run(
            binary,
            env,
            request(
                "observe",
                {
                    "path": "brief.md",
                    "idempotency_key": uid(),
                },
                project_id,
                workspace_id,
            ),
        )
        assert observed["status"] == "ok", observed
        task_id = uid()
        snapshot_id = observed["result"]["snapshot"]["snapshot_id"]
        checkpoint = run(
            binary,
            env,
            request(
                "checkpoint",
                {
                    "idempotency_key": uid(),
                    "expected_checkpoint_version": 0,
                    "objective": "Update event plan",
                    "constraints": ["Keep access"],
                    "completion_conditions": ["Capacity checked"],
                    "completed_actions": [],
                    "remaining_actions": ["Revise layout"],
                    "next_action": "Read current brief",
                    "blockers": [],
                    "decision_refs": [],
                    "source_refs": [],
                    "snapshot_id": snapshot_id,
                    "conflict_ids": [],
                    "pending_effects": [],
                    "parent_checkpoint_id": None,
                },
                project_id,
                workspace_id,
                task_id,
            ),
        )
        assert checkpoint["status"] == "ok", checkpoint
        recalled = run(
            binary,
            env,
            request(
                "recall",
                {
                    "need": "event capacity",
                    "budget_bytes": 8192,
                },
                project_id,
                workspace_id,
                task_id,
            ),
        )
        assert recalled["status"] == "ok" and recalled["result"]["source_evidence"]
        brief.write_text("Capacity: 80.\n", encoding="utf-8")
        stale = run(
            binary,
            env,
            request(
                "recall",
                {
                    "need": "event capacity",
                    "budget_bytes": 8192,
                },
                project_id,
                workspace_id,
                task_id,
            ),
        )
        assert stale["status"] == "ok" and not stale["result"]["source_evidence"]
        database = data_root / "projects" / project_id / "memory.sqlite3"
        assert database.is_file() and database.stat().st_size > 0
        registry_file = data_root / "projects" / "registry.json"
        lock_file = data_root / "projects" / project_id / "memory.lock"
        if os.name == "nt":
            from opensocrates.persistence.permissions import check_permissions

            assert check_permissions(database, directory=False).write_allowed
            assert check_permissions(lock_file, directory=False).write_allowed
            assert check_permissions(registry_file, directory=False).write_allowed
        else:
            assert stat.S_IMODE(database.stat().st_mode) == 0o600
            assert stat.S_IMODE(lock_file.stat().st_mode) == 0o600
            assert stat.S_IMODE(registry_file.stat().st_mode) == 0o600
        with closing(sqlite3.connect(database)) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE meta SET value='fixture-probe' WHERE key='schema_version'"
                )
                journal = data_root / "projects" / project_id / "memory.sqlite3-journal"
                assert journal.exists()
                if os.name == "nt":
                    assert check_permissions(journal, directory=False).write_allowed
                else:
                    assert stat.S_IMODE(journal.stat().st_mode) == 0o600
            finally:
                connection.rollback()
        # Exercise the shipped binary's real schema-1 to schema-2 migration.
        with closing(sqlite3.connect(database)) as connection:
            connection.execute("DROP TABLE migration_audit")
            connection.execute("UPDATE meta SET value='1' WHERE key='schema_version'")
            connection.commit()
        migrated = run(binary, env, request("status", {}, project_id, workspace_id))
        assert migrated["status"] == "ok" and migrated["result"]["schema_version"] == 2
        backup = database.parent / "memory.v1.backup.sqlite3"
        backup_manifest = database.parent / "migration-backup.json"
        assert backup.is_file() and backup_manifest.is_file()
        if os.name == "nt":
            assert check_permissions(backup, directory=False).write_allowed
            assert check_permissions(backup_manifest, directory=False).write_allowed
        else:
            assert stat.S_IMODE(backup.stat().st_mode) == 0o600
            assert stat.S_IMODE(backup_manifest.stat().st_mode) == 0o600
        with closing(sqlite3.connect(backup)) as connection:
            assert (
                connection.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[
                    0
                ]
                == "1"
            )
            assert connection.execute("SELECT COUNT(*) FROM records").fetchone()[0] >= 1
        exported = run(
            binary,
            env,
            request(
                "export",
                {
                    "format": "json",
                },
                project_id,
            ),
        )
        assert exported["status"] == "ok"
        assert str(source) not in json.dumps(exported)
        deleted = run(
            binary,
            env,
            request(
                "delete",
                {
                    "intent": "delete_project",
                    "idempotency_key": uid(),
                    "expected_policy_version": 1,
                },
                project_id,
            ),
        )
        assert deleted["status"] == "ok" and deleted["result"]["registration_removed"], {
            "status": deleted["status"],
            "limitations": deleted["limitations"],
            "result": deleted["result"],
        }
        assert not database.exists() and not backup.exists() and not backup_manifest.exists()
        if args.package:
            package = args.package
            for path in (
                "skills/opensocrates/references/assistance/guide.en.md",
                "skills/opensocrates/references/assistance/guide.ko.md",
                "skills/opensocrates/references/coding/reuse.en.md",
                "skills/opensocrates/references/coding/reuse.ko.md",
                "schemas/v1/project-memory-request.schema.json",
                "schemas/v1/assistance-request.schema.json",
            ):
                assert (package / path).is_file(), path
        print(
            "frozen-memory: PASS SQLite enrollment, source freshness, cold recall, migration backup, deletion, guide/schema assets"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Versioned SQLite authority for enrolled public records and checkpoints."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, cast
from uuid import uuid4

from ..persistence.locks import FileLock, LockPolicy
from ..persistence.permissions import check_permissions, create_owner_only_file
from .contracts import ContractError, load_schema, validate

SCHEMA_VERSION = 1
_SECRET = re.compile(
    r"(?i)(sk-[a-z0-9_-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:api[_-]?key|password|secret|token)\s*[:=]\s*\S+)"
)
_FORBIDDEN_FIELD = frozenset(
    {
        "prompt",
        "transcript",
        "messages",
        "raw_output",
        "tool_output",
        "credential",
        "cookie",
        "chain_of_thought",
        "reasoning",
    }
)


class StoreError(OSError):
    """Unavailable, corrupt, or unsafe store."""


class VersionConflict(StoreError):
    """Compare-and-swap input did not match the committed version."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _encoded(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _hash(value: object) -> str:
    return hashlib.sha256(_encoded(value).encode("utf-8")).hexdigest()


def _public(value: Any, private_root: str) -> None:
    """Reject obvious forbidden content before any SQLite write.

    This is a defensive filter, not a claim of perfect secret detection.
    """
    if isinstance(value, dict):
        if {key.casefold() for key in value} & _FORBIDDEN_FIELD:
            raise ContractError("forbidden content category")
        for child in value.values():
            _public(child, private_root)
    elif isinstance(value, list):
        for child in value:
            _public(child, private_root)
    elif isinstance(value, str):
        if _SECRET.search(value) or (private_root and private_root in value):
            raise ContractError("forbidden content")


def _regular_private(path: Path) -> None:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or stat.S_ISLNK(info.st_mode)
        or (getattr(info, "st_file_attributes", 0) & 0x400)
    ):
        raise StoreError("unsafe_path")
    if not check_permissions(path, directory=False).write_allowed:
        raise StoreError("permission_denied")


class MemoryStore:
    def __init__(self, project_dir: Path, *, private_root: str = "") -> None:
        self.project_dir = Path(project_dir)
        self.path = self.project_dir / "memory.sqlite3"
        self.lock_path = self.project_dir / "memory.lock"
        self.private_root = private_root

    def _check_parent(self) -> None:
        if not check_permissions(self.project_dir, directory=True).write_allowed:
            raise StoreError("permission_denied")
        if self.lock_path.exists():
            _regular_private(self.lock_path)

    @contextmanager
    def connect(self, *, write: bool = False, create: bool = False) -> Iterator[sqlite3.Connection]:
        self._check_parent()
        if not self.path.exists():
            if not create:
                raise StoreError("store_missing")
            descriptor = create_owner_only_file(self.path, flags=os.O_RDWR)
            os.close(descriptor)
        _regular_private(self.path)
        before = self.path.lstat()
        uri = self.path.as_uri() + ("?mode=rw" if write or create else "?mode=ro")
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=2.0, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=2000")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA secure_delete=ON")
            if write:
                mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
                if str(mode).lower() != "delete":
                    raise StoreError("unsupported_journal_mode")
            after = self.path.lstat()
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                raise StoreError("identity_mismatch")
            yield connection
        except sqlite3.DatabaseError as error:
            raise StoreError("store_corrupt") from error
        finally:
            if "connection" in locals():
                connection.close()
            if self.path.exists():
                _regular_private(self.path)
            journal = self.project_dir / "memory.sqlite3-journal"
            if journal.exists():
                _regular_private(journal)

    def initialize(self) -> None:
        with FileLock(self.lock_path, policy=LockPolicy(timeout_seconds=2)):
            with self.connect(write=True, create=True) as db:
                db.execute("BEGIN IMMEDIATE")
                # executescript() commits a pending transaction first. Individual
                # statements keep initial schema creation within this one BEGIN.
                for statement in (
                    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS records (record_id TEXT PRIMARY KEY, version INTEGER NOT NULL, data TEXT NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS record_history (record_id TEXT NOT NULL, version INTEGER NOT NULL, data TEXT NOT NULL, PRIMARY KEY(record_id, version))",
                    "CREATE TABLE IF NOT EXISTS checkpoints (task_id TEXT NOT NULL, workspace_id TEXT NOT NULL, record_id TEXT NOT NULL, version INTEGER NOT NULL, PRIMARY KEY(task_id,workspace_id))",
                    "CREATE TABLE IF NOT EXISTS snapshots (snapshot_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, data TEXT NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, operation TEXT NOT NULL, payload_hash TEXT NOT NULL, response TEXT NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS tombstones (record_id TEXT PRIMARY KEY, version INTEGER NOT NULL, origin_id TEXT)",
                ):
                    db.execute(statement)
                row = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
                if row is None:
                    db.execute(
                        "INSERT INTO meta(key,value) VALUES('schema_version',?)",
                        (str(SCHEMA_VERSION),),
                    )
                elif int(row[0]) != SCHEMA_VERSION:
                    raise StoreError("unsupported_schema")
                db.commit()

    def _version(self, db: sqlite3.Connection) -> None:
        try:
            row = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        except sqlite3.DatabaseError as error:
            raise StoreError("store_corrupt") from error
        if row is None or row[0] != str(SCHEMA_VERSION):
            raise StoreError("unsupported_schema")

    def probe_schema(self) -> int:
        """Read schema state without initializing or writing the database."""
        with self.connect() as db:
            self._version(db)
        return SCHEMA_VERSION

    def read_record(self, record_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            self._version(db)
            row = db.execute("SELECT data FROM records WHERE record_id=?", (record_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def list_records(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            self._version(db)
            rows = db.execute("SELECT data FROM records ORDER BY record_id").fetchall()
            return [json.loads(row[0]) for row in rows]

    def _mutate(
        self,
        operation: str,
        key: str,
        payload: dict[str, Any],
        mutation: Callable[[sqlite3.Connection], dict[str, Any]],
    ) -> dict[str, Any]:
        digest = _hash(payload)
        with FileLock(self.lock_path, policy=LockPolicy(timeout_seconds=2)):
            with self.connect(write=True) as db:
                self._version(db)
                db.execute("BEGIN IMMEDIATE")
                prior = db.execute(
                    "SELECT operation,payload_hash,response FROM idempotency WHERE key=?", (key,)
                ).fetchone()
                if prior:
                    if prior[0] != operation or prior[1] != digest:
                        raise VersionConflict("idempotency_conflict")
                    db.rollback()
                    return cast(dict[str, Any], json.loads(prior[2]))
                result = mutation(db)
                encoded_response = _encoded(result)
                if len(encoded_response.encode("utf-8")) > 48 * 1024:
                    raise ContractError("response budget insufficient")
                db.execute(
                    "INSERT INTO idempotency(key,operation,payload_hash,response) VALUES(?,?,?,?)",
                    (key, operation, digest, encoded_response),
                )
                db.commit()
                return result

    def write_record(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:  # noqa: C901  # CAS and evidence resolution are explicit.
        _public(payload, self.private_root)
        if len((payload["summary"] + (payload.get("rationale") or "")).encode("utf-8")) > 8192:
            raise ContractError("record public text exceeds 8 KiB")
        key = payload["idempotency_key"]
        record_id = payload.get("record_id") or str(uuid4())
        expected = payload["expected_record_version"]
        references: list[dict[str, Any]] = []
        for item in payload["source_refs"]:
            if isinstance(item, dict):
                references.append(item)
            elif isinstance(item, str):
                found = self.find_reference(item)
                if found is None:
                    raise ContractError("unknown source reference")
                references.append(found)
            else:
                raise ContractError("invalid source reference")

        def work(db: sqlite3.Connection) -> dict[str, Any]:
            if db.execute("SELECT 1 FROM tombstones WHERE record_id=?", (record_id,)).fetchone():
                raise VersionConflict("deleted_record_replay")
            prior = db.execute(
                "SELECT version,data FROM records WHERE record_id=?", (record_id,)
            ).fetchone()
            version = prior[0] if prior else 0
            if version != expected:
                raise VersionConflict("version_conflict")
            if prior and json.loads(prior[1])["lifecycle"] != "proposed":
                raise VersionConflict("accepted_record_requires_supersession")
            now = _now()
            record = {
                "schema": "opensocrates.project-memory.record/1.0.0",
                "record_id": record_id,
                "version": version + 1,
                "project_id": project_id,
                "kind": payload["kind"],
                "scope": payload["scope"],
                "lifecycle": "proposed",
                "origin": payload["origin"],
                "support": payload["support"],
                "freshness": "current" if payload["support"] == "runtime_observed" else "unknown",
                "summary": payload["summary"],
                "rationale": payload.get("rationale"),
                "source_refs": references,
                "snapshot_id": payload.get("snapshot_id"),
                "revalidation": payload["revalidation"],
                "created_at": json.loads(prior[1])["created_at"] if prior else now,
                "updated_at": now,
                "supersedes": None,
                "conflict_ids": payload.get("conflict_ids", []),
                "payload": None,
            }
            validate(record, load_schema("project-memory-record.schema.json"))
            if prior:
                db.execute(
                    "INSERT INTO record_history(record_id,version,data) VALUES(?,?,?)",
                    (record_id, version, prior[1]),
                )
            db.execute(
                "INSERT OR REPLACE INTO records(record_id,version,data) VALUES(?,?,?)",
                (record_id, version + 1, _encoded(record)),
            )
            return {"record": record}

        return self._mutate("record", key, payload, work)

    def find_reference(self, ref_id: str) -> dict[str, Any] | None:
        for record in self.list_records():
            for reference in record["source_refs"]:
                if reference["ref_id"] == ref_id:
                    return cast(dict[str, Any], reference)
        return None

    def write_checkpoint(
        self, project_id: str, workspace_id: str, task_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        _public(payload, self.private_root)
        if len(_encoded(payload).encode("utf-8")) > 16 * 1024:
            raise ContractError("checkpoint payload exceeds 16 KiB")
        key = payload["idempotency_key"]

        def work(db: sqlite3.Connection) -> dict[str, Any]:
            prior = db.execute(
                "SELECT record_id,version FROM checkpoints WHERE task_id=? AND workspace_id=?",
                (task_id, workspace_id),
            ).fetchone()
            version = prior[1] if prior else 0
            if version != payload["expected_checkpoint_version"]:
                raise VersionConflict("version_conflict")
            record_id = prior[0] if prior else str(uuid4())
            previous = db.execute(
                "SELECT data FROM records WHERE record_id=?", (record_id,)
            ).fetchone()
            now = _now()
            state = {
                k: v
                for k, v in payload.items()
                if k not in {"idempotency_key", "expected_checkpoint_version"}
            }
            state["checkpoint_version"] = version + 1
            record = {
                "schema": "opensocrates.project-memory.record/1.0.0",
                "record_id": record_id,
                "version": version + 1,
                "project_id": project_id,
                "kind": "checkpoint",
                "scope": {"level": "task", "workspace_id": workspace_id, "task_id": task_id},
                "lifecycle": "proposed",
                "origin": {
                    "producer_kind": "agent",
                    "source_reference": None,
                    "attestation": "agent_reported",
                },
                "support": "agent_reported",
                "freshness": "unknown",
                "summary": payload["objective"][:1024],
                "rationale": None,
                "source_refs": [],
                "snapshot_id": payload["snapshot_id"],
                "revalidation": {
                    "dependency_paths": [],
                    "negative_claim": False,
                    "on_change": "refresh_or_mark_stale",
                },
                "created_at": json.loads(previous[0])["created_at"] if previous else now,
                "updated_at": now,
                "supersedes": None,
                "conflict_ids": payload["conflict_ids"],
                "payload": state,
            }
            validate(record, load_schema("project-memory-record.schema.json"))
            if previous:
                db.execute(
                    "INSERT INTO record_history(record_id,version,data) VALUES(?,?,?)",
                    (record_id, version, previous[0]),
                )
            db.execute(
                "INSERT OR REPLACE INTO records(record_id,version,data) VALUES(?,?,?)",
                (record_id, version + 1, _encoded(record)),
            )
            db.execute(
                "INSERT OR REPLACE INTO checkpoints(task_id,workspace_id,record_id,version) VALUES(?,?,?,?)",
                (task_id, workspace_id, record_id, version + 1),
            )
            return {"record_id": record_id, "checkpoint_version": version + 1, "record": record}

        return self._mutate("checkpoint", key, payload, work)

    def latest_checkpoint(self, task_id: str, workspace_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            self._version(db)
            row = db.execute(
                "SELECT r.data FROM checkpoints c JOIN records r ON c.record_id=r.record_id WHERE c.task_id=? AND c.workspace_id=?",
                (task_id, workspace_id),
            ).fetchone()
            return json.loads(row[0]) if row else None

    def accept(self, payload: dict[str, Any]) -> dict[str, Any]:
        _public(payload, self.private_root)

        def work(db: sqlite3.Connection) -> dict[str, Any]:
            row = db.execute(
                "SELECT version,data FROM records WHERE record_id=?", (payload["record_id"],)
            ).fetchone()
            if row is None or row[0] != payload["expected_record_version"]:
                raise VersionConflict("version_conflict")
            record = json.loads(row[1])
            if record["kind"] == "observation" or record["lifecycle"] != "proposed":
                raise ContractError("record cannot be accepted")
            record["version"] += 1
            record["lifecycle"] = "accepted"
            record["updated_at"] = _now()
            record["origin"]["source_reference"] = payload["acceptance_basis"]
            record["origin"]["attestation"] = payload["acceptance_attribution"]
            validate(record, load_schema("project-memory-record.schema.json"))
            db.execute(
                "INSERT INTO record_history(record_id,version,data) VALUES(?,?,?)",
                (record["record_id"], row[0], row[1]),
            )
            db.execute(
                "UPDATE records SET version=?,data=? WHERE record_id=?",
                (record["version"], _encoded(record), record["record_id"]),
            )
            return {"record": record}

        return self._mutate("accept", payload["idempotency_key"], payload, work)

    @staticmethod
    def _snapshot_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
        return {
            "snapshot_id": snapshot["snapshot_id"],
            "workspace_kind": snapshot["workspace_kind"],
            "scope_paths": snapshot["scope_paths"],
            "inventory_digest": snapshot["inventory_digest"],
            "content_manifest_digest": snapshot["content_manifest_digest"],
            "coverage": snapshot["coverage"],
        }

    @staticmethod
    def _snapshot_fingerprint(snapshot: dict[str, Any]) -> dict[str, Any]:
        return {
            key: snapshot[key]
            for key in (
                "project_id",
                "workspace_id",
                "workspace_kind",
                "root_identity_digest",
                "head_oid",
                "ref",
                "status_digest",
                "scope_paths",
                "inventory_digest",
                "content_manifest_digest",
                "exclusion_digest",
                "configuration_digest",
                "adapter_versions",
                "coverage",
            )
        }

    def refresh_snapshot(
        self, snapshot: dict[str, Any], *, key: str, scope_paths: list[str]
    ) -> dict[str, Any]:
        validate(snapshot, load_schema("project-memory-snapshot.schema.json"))
        intent = {"scope_paths": scope_paths, "fingerprint": self._snapshot_fingerprint(snapshot)}

        def work(db: sqlite3.Connection) -> dict[str, Any]:
            db.execute(
                "INSERT INTO snapshots(snapshot_id,workspace_id,data) VALUES(?,?,?)",
                (snapshot["snapshot_id"], snapshot["workspace_id"], _encoded(snapshot)),
            )
            return {"snapshot": self._snapshot_summary(snapshot)}

        return self._mutate("refresh", key, intent, work)

    def observe_snapshot(
        self,
        snapshot: dict[str, Any],
        reference: dict[str, Any],
        *,
        path: str,
        symbol: str | None,
        key: str,
    ) -> dict[str, Any]:
        validate(snapshot, load_schema("project-memory-snapshot.schema.json"))
        intent = {
            "path": path,
            "symbol": symbol,
            "fingerprint": self._snapshot_fingerprint(snapshot),
        }

        def work(db: sqlite3.Connection) -> dict[str, Any]:
            db.execute(
                "INSERT INTO snapshots(snapshot_id,workspace_id,data) VALUES(?,?,?)",
                (snapshot["snapshot_id"], snapshot["workspace_id"], _encoded(snapshot)),
            )
            now = _now()
            record_id = str(uuid4())
            record = {
                "schema": "opensocrates.project-memory.record/1.0.0",
                "record_id": record_id,
                "version": 1,
                "project_id": snapshot["project_id"],
                "kind": "observation",
                "scope": {"level": "workspace", "workspace_id": snapshot["workspace_id"]},
                "lifecycle": "proposed",
                "origin": {
                    "producer_kind": "runtime_observer",
                    "source_reference": reference["ref_id"],
                    "attestation": "local_file_observation",
                },
                "support": "runtime_observed",
                "freshness": "current",
                "summary": f"Observed current metadata for {path}"
                + (f"#{symbol}" if symbol else ""),
                "rationale": None,
                "source_refs": [reference],
                "snapshot_id": snapshot["snapshot_id"],
                "revalidation": {
                    "dependency_paths": [path],
                    "negative_claim": False,
                    "on_change": "refresh_or_mark_stale",
                },
                "created_at": now,
                "updated_at": now,
                "supersedes": None,
                "conflict_ids": [],
                "payload": None,
            }
            validate(record, load_schema("project-memory-record.schema.json"))
            _public(record, self.private_root)
            db.execute(
                "INSERT INTO records(record_id,version,data) VALUES(?,?,?)",
                (record_id, 1, _encoded(record)),
            )
            return {
                "snapshot": self._snapshot_summary(snapshot),
                "reference": reference,
                "observation_record_id": record_id,
            }

        return self._mutate("observe", key, intent, work)

    def observe_search(
        self,
        snapshot: dict[str, Any],
        references: list[dict[str, Any]],
        *,
        query_digest: str,
        omitted_matches: int,
        key: str,
    ) -> dict[str, Any]:
        """Commit one lexical inventory observation without retaining the query."""
        validate(snapshot, load_schema("project-memory-snapshot.schema.json"))
        if len(references) > 32:
            raise ContractError("search reference limit exceeded")
        intent = {
            "query_digest": query_digest,
            "fingerprint": self._snapshot_fingerprint(snapshot),
        }

        def work(db: sqlite3.Connection) -> dict[str, Any]:
            db.execute(
                "INSERT INTO snapshots(snapshot_id,workspace_id,data) VALUES(?,?,?)",
                (snapshot["snapshot_id"], snapshot["workspace_id"], _encoded(snapshot)),
            )
            now = _now()
            record_id = str(uuid4())
            record = {
                "schema": "opensocrates.project-memory.record/1.0.0",
                "record_id": record_id,
                "version": 1,
                "project_id": snapshot["project_id"],
                "kind": "observation",
                "scope": {"level": "workspace", "workspace_id": snapshot["workspace_id"]},
                "lifecycle": "proposed",
                "origin": {
                    "producer_kind": "runtime_observer",
                    "source_reference": query_digest,
                    "attestation": "local_file_observation",
                },
                "support": "runtime_observed",
                "freshness": "current",
                "summary": f"Lexical search observed {len(references)} candidate locations.",
                "rationale": None,
                "source_refs": references,
                "snapshot_id": snapshot["snapshot_id"],
                "revalidation": {
                    "dependency_paths": [],
                    "negative_claim": not references and omitted_matches == 0,
                    "on_change": "refresh_or_mark_stale",
                },
                "created_at": now,
                "updated_at": now,
                "supersedes": None,
                "conflict_ids": [],
                "payload": None,
            }
            validate(record, load_schema("project-memory-record.schema.json"))
            _public(record, self.private_root)
            db.execute(
                "INSERT INTO records(record_id,version,data) VALUES(?,?,?)",
                (record_id, 1, _encoded(record)),
            )
            return {
                "snapshot": self._snapshot_summary(snapshot),
                "references": references,
                "omitted_matches": omitted_matches,
                "query_digest": query_digest,
                "observation_record_id": record_id,
            }

        return self._mutate("observe_search", key, intent, work)

    def read_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            self._version(db)
            row = db.execute(
                "SELECT data FROM snapshots WHERE snapshot_id=?", (snapshot_id,)
            ).fetchone()
            return json.loads(row[0]) if row else None

    def delete_record(self, record_id: str, expected_version: int, key: str) -> dict[str, Any]:
        payload = {"record_id": record_id, "expected_record_version": expected_version}

        def work(db: sqlite3.Connection) -> dict[str, Any]:
            row = db.execute(
                "SELECT version,data FROM records WHERE record_id=?", (record_id,)
            ).fetchone()
            if row is None or row[0] != expected_version:
                raise VersionConflict("version_conflict")
            record = json.loads(row[1])
            db.execute("DELETE FROM records WHERE record_id=?", (record_id,))
            db.execute("DELETE FROM record_history WHERE record_id=?", (record_id,))
            db.execute("DELETE FROM checkpoints WHERE record_id=?", (record_id,))
            for prior in db.execute("SELECT key,response FROM idempotency").fetchall():
                if record_id in prior[1]:
                    db.execute(
                        "UPDATE idempotency SET response=? WHERE key=?",
                        (_encoded({"deleted_record_id": record_id, "tombstone": True}), prior[0]),
                    )
            db.execute(
                "INSERT INTO tombstones(record_id,version,origin_id) VALUES(?,?,?)",
                (record_id, expected_version, record["origin"].get("source_reference")),
            )
            return {"deleted_record_id": record_id, "tombstone": True}

        return self._mutate("delete", key, payload, work)

    def supersede(self, payload: dict[str, Any]) -> dict[str, Any]:
        _public(payload, self.private_root)

        def work(db: sqlite3.Connection) -> dict[str, Any]:
            old_row = db.execute(
                "SELECT version,data FROM records WHERE record_id=?", (payload["record_id"],)
            ).fetchone()
            new_row = db.execute(
                "SELECT version,data FROM records WHERE record_id=?", (payload["new_record_id"],)
            ).fetchone()
            if (
                old_row is None
                or new_row is None
                or old_row[0] != payload["expected_record_version"]
                or new_row[0] != payload["expected_new_record_version"]
            ):
                raise VersionConflict("version_conflict")
            old = json.loads(old_row[1])
            new = json.loads(new_row[1])
            if (
                old["lifecycle"] != "accepted"
                or new["lifecycle"] != "accepted"
                or old["project_id"] != new["project_id"]
            ):
                raise ContractError("supersession requires accepted records in one project")
            old["lifecycle"] = "superseded"
            old["version"] += 1
            old["updated_at"] = _now()
            new["supersedes"] = old["record_id"]
            new["version"] += 1
            new["updated_at"] = _now()
            new["conflict_ids"] = [item for item in new["conflict_ids"] if item != old["record_id"]]
            db.execute(
                "INSERT INTO record_history(record_id,version,data) VALUES(?,?,?)",
                (old["record_id"], old_row[0], old_row[1]),
            )
            db.execute(
                "INSERT INTO record_history(record_id,version,data) VALUES(?,?,?)",
                (new["record_id"], new_row[0], new_row[1]),
            )
            db.execute(
                "UPDATE records SET version=?,data=? WHERE record_id=?",
                (old["version"], _encoded(old), old["record_id"]),
            )
            db.execute(
                "UPDATE records SET version=?,data=? WHERE record_id=?",
                (new["version"], _encoded(new), new["record_id"]),
            )
            return {
                "old_record_id": old["record_id"],
                "old_version": old["version"],
                "new_record_id": new["record_id"],
                "new_version": new["version"],
            }

        return self._mutate("supersede", payload["idempotency_key"], payload, work)

    @staticmethod
    def _prune_candidates(db: sqlite3.Connection, older_than: str) -> list[dict[str, Any]]:
        records = [
            json.loads(row[0])
            for row in db.execute("SELECT data FROM records ORDER BY record_id").fetchall()
        ]
        protected_ids: set[str] = set()
        protected_refs: set[str] = set()
        for record in records:
            active = record["lifecycle"] in {"accepted", "superseded"} or (
                record["kind"] == "checkpoint" and record["payload"]["remaining_actions"]
            )
            if not active:
                continue
            protected_ids.add(record["record_id"])
            protected_ids.update(record["conflict_ids"])
            if record["supersedes"]:
                protected_ids.add(record["supersedes"])
            if record["kind"] == "checkpoint":
                protected_ids.update(record["payload"]["decision_refs"])
                protected_refs.update(record["payload"]["source_refs"])
            protected_refs.update(ref["ref_id"] for ref in record["source_refs"])
        for record in records:
            if any(ref["ref_id"] in protected_refs for ref in record["source_refs"]):
                protected_ids.add(record["record_id"])
        return [
            record
            for record in records
            if record["record_id"] not in protected_ids and record["updated_at"] < older_than
        ]

    def prune(
        self,
        older_than: str,
        *,
        retention_days: int,
        dry_run: bool,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if dry_run:
            with self.connect() as db:
                self._version(db)
                eligible = self._prune_candidates(db, older_than)
            selected = eligible[:32]
            return {
                "eligible_record_ids": [item["record_id"] for item in selected],
                "remaining_count": max(0, len(eligible) - len(selected)),
                "applied": False,
            }
        if idempotency_key is None:
            raise ContractError("prune apply requires an idempotency key")

        def work(db: sqlite3.Connection) -> dict[str, Any]:
            eligible = self._prune_candidates(db, older_than)
            selected = eligible[:32]
            for record in selected:
                record_id = record["record_id"]
                db.execute("DELETE FROM records WHERE record_id=?", (record_id,))
                db.execute("DELETE FROM record_history WHERE record_id=?", (record_id,))
                db.execute("DELETE FROM checkpoints WHERE record_id=?", (record_id,))
                db.execute(
                    "INSERT INTO tombstones(record_id,version,origin_id) VALUES(?,?,?)",
                    (record_id, record["version"], record["origin"].get("source_reference")),
                )
                for prior in db.execute("SELECT key,response FROM idempotency").fetchall():
                    if record_id in prior[1]:
                        db.execute(
                            "UPDATE idempotency SET response=? WHERE key=?",
                            (
                                _encoded({"deleted_record_id": record_id, "tombstone": True}),
                                prior[0],
                            ),
                        )
            return {
                "eligible_record_ids": [item["record_id"] for item in selected],
                "remaining_count": max(0, len(eligible) - len(selected)),
                "applied": True,
            }

        return self._mutate("prune", idempotency_key, {"retention_days": retention_days}, work)

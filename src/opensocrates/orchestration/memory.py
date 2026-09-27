"""Read-only, version-frozen projections of the existing enrolled store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..project_memory.registry import ProjectRegistry
from ..project_memory.service import _current_snapshot, _freshness, _record_scope
from ..project_memory.store import MemoryStore
from .paths import BoundaryError, identity, root_path


def _overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _relevant(record: dict[str, Any], paths: list[str]) -> bool:
    scope = record["scope"].get("module_paths", [])
    return not scope or any(_overlap(a, b) for a in scope for b in paths)


def _lesson(record: dict[str, Any]) -> dict[str, Any] | None:
    if record["kind"] != "lesson" or not record["rationale"]:
        return None
    try:
        parsed = json.loads(record["rationale"])
        if not isinstance(parsed, dict) or set(parsed) != {
            "conditions",
            "mechanism",
            "exceptions",
            "provenance",
            "evidence_refs",
        }:
            return None
        from ..project_memory.contracts import validate
        from .contracts import schema

        shape = schema("assignment")["properties"]["memory"]["properties"]["records"]["items"][
            "properties"
        ]["lesson"]
        validate(parsed, shape)
        return parsed
    except (ValueError, TypeError):
        return None


class MemorySnapshot:
    """No enrollment, migration, capture, cache or durable orchestration state."""

    def __init__(self, request: dict[str, Any], registry: ProjectRegistry | None = None) -> None:
        self.request = request
        self.registry = registry or ProjectRegistry()
        self.status = "not_requested"
        self.records: list[dict[str, Any]] = []
        self.versions: dict[str, str] = {}
        self.accepted_ids: set[str] = set()
        self.paths: list[str] = []
        self.limitations: list[str] = []
        self.project_state: dict[str, Any] = {}
        self.workspace: dict[str, Any] = {}
        self.store: MemoryStore | None = None
        if request["memory"] is not None:
            self._freeze()

    def _freeze(self) -> None:
        binding = self.request["memory"]
        try:
            project, workspace = self.registry.get(binding["project_id"], binding["workspace_id"])
            if project["policy"]["mode"] == "disabled":
                self.status, self.limitations = "disabled", ["memory_disabled_handoff_required"]
                return
            if workspace is None or Path(workspace["root"]).resolve() != root_path(
                self.request["source_root"]
            ):
                raise BoundaryError("memory_workspace_mismatch")
            self.project_state, self.workspace = project, workspace
            self.store = MemoryStore(
                self.registry.project_dir(binding["project_id"]), private_root=workspace["root"]
            )
            if self.store.probe_schema() != 2:
                raise BoundaryError("memory_migration_requires_existing_api")
            paths = [path for unit in self.request["units"] for path in unit["owned_paths"]] + [
                source["path"] for source in self.request["sources"]
            ]
            self.paths = paths
            records = [
                record
                for record in self.store.list_records()
                if _record_scope(record, binding["workspace_id"], self.request["task_id"])
                and _relevant(record, paths)
            ]
            selected = set(binding["record_ids"])
            # A selection may narrow optional knowledge, never accepted intent.
            records = [
                record
                for record in records
                if (record["kind"] == "decision" and record["lifecycle"] == "accepted")
                or not selected
                or record["record_id"] in selected
            ]
            if len(records) > 64:
                raise BoundaryError("memory_context_overflow")
            self.records = records
            self.accepted_ids = {
                record["record_id"]
                for record in records
                if record["kind"] == "decision" and record["lifecycle"] == "accepted"
            }
            self.versions = {record["record_id"]: identity(record) for record in records}
            self.status = "available"
        except BoundaryError as error:
            if str(error) == "memory_context_overflow":
                raise
            self.status, self.limitations = (
                "unavailable",
                ["memory_unavailable_use_explicit_handoff"],
            )
        except (OSError, ValueError, KeyError):
            self.status, self.limitations = (
                "unavailable",
                ["memory_unavailable_use_explicit_handoff"],
            )

    def unchanged(self) -> bool:
        if self.status != "available" or self.store is None:
            return True
        binding = self.request["memory"]
        try:
            project, _ = self.registry.get(binding["project_id"], binding["workspace_id"])
            if project["policy"] != self.project_state["policy"]:
                return False
            current_accepted = {
                record["record_id"]
                for record in self.store.list_records()
                if record["kind"] == "decision"
                and record["lifecycle"] == "accepted"
                and _record_scope(record, binding["workspace_id"], self.request["task_id"])
                and _relevant(record, self.paths)
            }
            if current_accepted != self.accepted_ids:
                return False
            return all(
                identity(self.store.read_record(key)) == value
                for key, value in self.versions.items()
            )
        except (OSError, ValueError):
            return False

    def _project_record(self, record: dict[str, Any]) -> dict[str, Any]:
        assert self.store is not None
        binding = self.request["memory"]
        stored = self.store.read_snapshot(record["snapshot_id"]) if record["snapshot_id"] else None
        current = (
            _current_snapshot(
                self.workspace,
                binding["project_id"],
                binding["workspace_id"],
                self.project_state["policy"]["excluded_paths"],
                tuple(stored["scope_paths"]),
            )
            if stored
            else None
        )
        freshness = _freshness(record, current, stored)
        return {
            **{
                key: record[key]
                for key in (
                    "record_id",
                    "version",
                    "kind",
                    "lifecycle",
                    "support",
                    "summary",
                    "rationale",
                    "source_refs",
                    "conflict_ids",
                    "origin",
                )
            },
            "freshness": freshness,
            "review_state": "unknown",
            "lesson": _lesson(record),
            "constraints": record["payload"]["constraints"]
            if record["kind"] == "checkpoint"
            else [],
        }

    def project(self, unit: dict[str, Any], role: str) -> dict[str, Any]:
        if not self.unchanged():
            raise BoundaryError("memory_changed")
        records = []
        for record in self.records:
            if not _relevant(
                record,
                unit["owned_paths"]
                + [s["path"] for s in self.request["sources"] if s["id"] in unit["source_ids"]],
            ):
                continue
            accepted = record["kind"] == "decision" and record["lifecycle"] == "accepted"
            same_attempt = (
                record["origin"].get("source_reference") == "run:" + self.request["run_id"]
            )
            if (
                role in {"review", "execution_verification"}
                and not accepted
                and (record["kind"] == "checkpoint" or same_attempt or record["kind"] == "lesson")
            ):
                continue
            records.append(self._project_record(record))
        return {"status": self.status, "records": records, "limitations": self.limitations}

    @property
    def snapshot_sha256(self) -> str:
        return identity(self.versions)

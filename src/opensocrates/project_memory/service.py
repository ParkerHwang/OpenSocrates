"""One explicit request at a time; ordinary hooks and decisions never import this."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from ..persistence.atomic import canonical_json_bytes
from ..persistence.locks import FileLock, LockPolicy, LockTimeoutError
from ..persistence.permissions import check_permissions, discard_created_file, open_owner_only_file
from .contracts import ContractError, response, validate_basis_reference, validate_request
from .registry import ProjectRegistry, RegistryError, binding_for
from .store import MemoryStore, StoreError, VersionConflict

MAX_PACK_BYTES = 64 * 1024
MANAGEMENT = frozenset({"status", "inspect", "export", "delete", "disable", "prune"})
WRITES = frozenset({"observe", "record", "accept", "checkpoint", "refresh", "supersede"})


def _policy(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": payload["mode"],
        "capture_policy": payload["capture_policy"],
        "excluded_paths": payload["excluded_paths"],
    }


def _public_authorization(value: dict[str, str]) -> dict[str, str]:
    return {
        "attribution": value["attribution"],
        "basis_digest": "sha256:" + hashlib.sha256(value["basis"].encode("utf-8")).hexdigest(),
    }


def _capabilities(workspace_kind: str | None) -> dict[str, str]:
    return {
        "text": "lexical",
        "python": "ast" if workspace_kind == "git_worktree" else "unavailable",
        "memory": "sqlite3",
        "path_boundary": "local_drive_only" if os.name == "nt" else "local_owned_root",
    }


def _remove_owned_file(path: Path, project_dir: Path) -> None:
    """Delete one inspected managed file through the platform's identity-bound path."""
    if os.name == "nt":
        from ..windows_security import remove_private_path

        info = path.lstat()
        if (
            remove_private_path(
                path, root=project_dir, expected_identity=(info.st_dev, info.st_ino)
            )
            != 1
        ):
            raise StoreError("busy")
        return
    descriptor = open_owner_only_file(path, flags=os.O_RDONLY, share_delete=True)
    try:
        discard_created_file(descriptor, path)
    finally:
        os.close(descriptor)


def _record_scope(record: dict[str, Any], workspace_id: str | None, task_id: str | None) -> bool:
    scope = record["scope"]
    if scope["level"] == "project":
        return True
    if scope.get("workspace_id") != workspace_id:
        return False
    return bool(scope["level"] != "task" or scope.get("task_id") == task_id)


def _freshness(
    record: dict[str, Any], current: dict[str, Any] | None, stored: dict[str, Any] | None
) -> str:
    if record["kind"] in {"decision", "lesson"} and record["snapshot_id"] is None:
        return (
            "unknown"
            if record["source_refs"]
            or record["revalidation"]["dependency_paths"]
            or record["revalidation"]["negative_claim"]
            else "not_applicable"
        )
    if current is None or stored is None:
        return "unknown"
    from .sources import revalidate_snapshot

    return str(revalidate_snapshot(stored, current)["freshness"])


def _current_snapshot(
    workspace: dict[str, Any],
    project_id: str,
    workspace_id: str,
    excluded: list[str],
    scope_paths: tuple[str, ...] = (),
) -> dict[str, Any]:
    from .sources import capture_snapshot

    return capture_snapshot(
        Path(workspace["root"]),
        workspace["workspace_kind"],
        project_id,
        workspace_id,
        scope_paths=scope_paths,
        excluded_paths=tuple(excluded),
    )


def _pack(  # noqa: C901  # Required-pack composition is branch explicit.
    store: MemoryStore,
    project: dict[str, Any],
    workspace: dict[str, Any],
    project_id: str,
    workspace_id: str,
    task_id: str | None,
    payload: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    budget = min(payload["budget_bytes"], MAX_PACK_BYTES)
    current = _current_snapshot(
        workspace, project_id, workspace_id, project["policy"]["excluded_paths"]
    )
    scoped_current: dict[tuple[str, ...], dict[str, Any]] = {(): current}

    def current_for(stored: dict[str, Any] | None) -> dict[str, Any] | None:
        if stored is None:
            return None
        scope = tuple(stored["scope_paths"])
        if scope not in scoped_current:
            scoped_current[scope] = _current_snapshot(
                workspace,
                project_id,
                workspace_id,
                project["policy"]["excluded_paths"],
                scope,
            )
        return scoped_current[scope]

    records = [
        record for record in store.list_records() if _record_scope(record, workspace_id, task_id)
    ]
    query_words = set(payload["need"].casefold().split())

    def rank(record: dict[str, Any]) -> tuple[int, int, str]:
        overlap = len(query_words & set(record["summary"].casefold().split()))
        important = 2 if record["lifecycle"] == "accepted" and record["kind"] == "decision" else 0
        return (-important, -overlap, record["record_id"])

    records.sort(key=rank)
    checkpoint = store.latest_checkpoint(task_id, workspace_id) if task_id else None
    constraints: list[dict[str, str]] = []
    decisions: list[dict[str, str]] = []
    unknowns: list[str] = []
    conflicts: list[str] = []
    source_evidence: list[dict[str, Any]] = []
    for record in records:
        stored = store.read_snapshot(record["snapshot_id"]) if record["snapshot_id"] else None
        freshness = _freshness(record, current_for(stored), stored)
        if freshness != "current" and freshness != "not_applicable":
            unknowns.append(f"{record['record_id']}:{freshness}")
        conflicts.extend(record["conflict_ids"])
        if record["kind"] == "decision" and record["lifecycle"] == "accepted":
            decisions.append(
                {
                    "summary": record["summary"][:1024],
                    "record_id": record["record_id"],
                    "freshness": freshness,
                }
            )
            if record["scope"]["level"] != "task":
                constraints.append(
                    {
                        "text": record["summary"][:1024],
                        "record_id": record["record_id"],
                        "freshness": freshness,
                    }
                )
        if freshness == "current":
            source_evidence.extend(record["source_refs"])
    if checkpoint:
        stored = (
            store.read_snapshot(checkpoint["snapshot_id"]) if checkpoint["snapshot_id"] else None
        )
        checkpoint_freshness = _freshness(checkpoint, current_for(stored), stored)
        constraints.extend(
            {
                "text": text[:1024],
                "record_id": checkpoint["record_id"],
                "freshness": checkpoint_freshness,
            }
            for text in checkpoint["payload"]["constraints"]
        )
        if checkpoint_freshness != "current":
            unknowns.append("checkpoint_source_state_requires_revalidation")
    distinct_evidence: list[dict[str, Any]] = []
    seen_evidence: dict[tuple[str, str, str | None], str] = {}
    for reference in source_evidence:
        key = (
            reference["digest"],
            reference["locator"]["path"],
            reference["locator"].get("symbol"),
        )
        if key in seen_evidence:
            unknowns.append(
                f"duplicate_source_reference:{reference['ref_id']}:{seen_evidence[key]}"
            )
        else:
            seen_evidence[key] = reference["ref_id"]
            distinct_evidence.append(reference)
    source_evidence = distinct_evidence
    pack: dict[str, Any] = {
        "schema": "opensocrates.project-memory.context-pack/1.0.0",
        "pack_id": str(uuid4()),
        "project_id": project_id,
        "workspace_id": workspace_id,
        "task_id": task_id,
        "workspace_kind": workspace["workspace_kind"],
        "checked_snapshot": current["snapshot_id"],
        "constraints": constraints,
        "decisions": decisions,
        "source_evidence": source_evidence,
        "checkpoint_reference": checkpoint["record_id"] if checkpoint else None,
        "conflicts": sorted(set(conflicts)),
        "unknowns": unknowns,
        "searched_scope": current["scope_paths"],
        "excluded_scope": project["policy"]["excluded_paths"],
        "capabilities": {
            "text": "lexical",
            "python": "ast" if workspace["workspace_kind"] == "git_worktree" else "unavailable",
        },
        "budget_bytes": budget,
        "used_bytes": 0,
        "expansion_handle": None,
        "delivery": "emitted",
        "application": "unverified",
    }
    if any(
        len(items) > 32 for items in (constraints, decisions, source_evidence, conflicts, unknowns)
    ):
        return "budget_insufficient", {
            "required_item_counts": {
                "constraints": len(constraints),
                "decisions": len(decisions),
                "source_evidence": len(source_evidence),
                "conflicts": len(conflicts),
                "unknowns": len(unknowns),
            },
            "partition": "narrow task and source scope; required constraints were not truncated",
        }
    from .contracts import load_schema, validate

    validate(pack, load_schema("project-memory-context-pack.schema.json"))
    for _ in range(3):
        encoded = canonical_json_bytes(pack)
        if pack["used_bytes"] == len(encoded):
            break
        pack["used_bytes"] = len(encoded)
    if len(canonical_json_bytes(pack)) > budget:
        return "budget_insufficient", {
            "required_bytes": len(canonical_json_bytes(pack)),
            "budget_bytes": budget,
            "partition": "narrow need or increase budget within 65536 bytes",
        }
    return "ok", pack


def handle_memory(raw: Any, *, registry: ProjectRegistry | None = None) -> dict[str, Any]:  # noqa: C901
    """Handle a closed request and return one bounded public response."""
    request_id = raw.get("request_id") if isinstance(raw, dict) else None
    try:
        if not isinstance(request_id, str) or str(UUID(request_id)) != request_id.lower():
            request_id = None
    except ValueError:
        request_id = None
    try:
        req = validate_request(raw)
    except (ContractError, OSError, ValueError):
        return response(request_id, "invalid_request", limitations=["closed_request_rejected"])
    registry = registry or ProjectRegistry()
    operation = req["operation"]
    payload = req["payload"]
    project_id = req["project_id"]
    workspace_id = req["workspace_id"]
    task_id = req["task_id"]
    result: Any
    try:
        if operation == "init":
            policy = _policy(payload)
            if not payload["apply"]:
                return response(
                    request_id,
                    "ok",
                    registry.preview(
                        payload["root"],
                        policy,
                        payload.get("expected_policy_version"),
                        project_id,
                    ),
                )
            result = registry.enroll(
                payload["root"],
                policy,
                payload["disclosure_digest"],
                payload["authorization_basis"],
                payload["authorization_attribution"],
                payload.get("expected_policy_version"),
                project_id,
                payload["idempotency_key"],
            )
            return response(request_id, "ok", result)
        if operation == "status":
            if project_id is None:
                registered = registry.load()
                if registered is None:
                    return response(request_id, "disabled", {"enrolled": False})
                if "root" in payload:
                    binding = binding_for(payload["root"])
                    matches = [
                        {
                            "project_id": project["project_id"],
                            "workspace_id": wid,
                            "policy": project["policy"],
                            "authorization": _public_authorization(
                                workspace.get("authorization", project["authorization"])
                            ),
                            "workspace_kind": workspace["workspace_kind"],
                            "capabilities": _capabilities(workspace["workspace_kind"]),
                        }
                        for project in registered["projects"].values()
                        for wid, workspace in project["workspaces"].items()
                        if workspace["root"] == binding["root"]
                        and workspace["root_identity"] == binding["root_identity"]
                    ]
                    return response(
                        request_id, "ok" if matches else "disabled", {"matches": matches}
                    )
                return response(request_id, "ok", {"project_count": len(registered["projects"])})
            project, workspace = registry.get(project_id, workspace_id)
            store_state = MemoryStore(
                registry.project_dir(project_id),
                private_root=workspace["root"] if workspace else "",
            ).probe_schema()
            return response(
                request_id,
                "ok",
                {
                    "project_id": project_id,
                    "workspace_id": workspace_id,
                    "policy": project["policy"],
                    "authorization": _public_authorization(
                        workspace.get("authorization", project["authorization"])
                        if workspace
                        else project["authorization"]
                    ),
                    "workspace_kind": workspace["workspace_kind"] if workspace else None,
                    "capabilities": _capabilities(
                        workspace["workspace_kind"] if workspace else None
                    ),
                    "schema_version": store_state,
                },
            )
        assert isinstance(project_id, str)
        project, workspace = registry.get(project_id, workspace_id)
        mode = project["policy"]["mode"]
        if operation == "recall" and mode == "disabled":
            return response(request_id, "disabled", limitations=["automatic_memory_use_disabled"])
        if operation in WRITES and mode != "read_write":
            return response(request_id, "disabled", limitations=["capture_not_enabled"])
        if operation not in MANAGEMENT and mode == "disabled":
            return response(request_id, "disabled", limitations=["automatic_memory_use_disabled"])
        store = MemoryStore(
            registry.project_dir(project_id), private_root=workspace["root"] if workspace else ""
        )
        if operation == "record":
            origin = payload["origin"]
            if (origin["producer_kind"], origin["attestation"]) not in {
                ("agent", "agent_reported"),
                ("agent", "agent_reported_user_instruction"),
                ("import", "imported"),
            }:
                raise ContractError("caller cannot claim native or human attestation")
            if origin["source_reference"] is not None:
                validate_basis_reference(origin["source_reference"])
            scope = payload["scope"]
            if scope["level"] == "project":
                if scope.get("workspace_id") or scope.get("task_id"):
                    raise ContractError("project scope cannot carry workspace or task identity")
            elif scope.get("workspace_id") != workspace_id:
                raise ContractError("record workspace identity mismatch")
            if scope["level"] == "task" and scope.get("task_id") != task_id:
                raise ContractError("record task identity mismatch")
            if payload.get("snapshot_id") is not None:
                snap = store.read_snapshot(payload["snapshot_id"])
                if snap is None or snap["workspace_id"] != workspace_id:
                    raise ContractError("unknown source snapshot")
            if (
                payload["source_refs"]
                or payload["revalidation"]["dependency_paths"]
                or payload["revalidation"]["negative_claim"]
            ) and payload.get("snapshot_id") is None:
                raise ContractError("source-dependent record requires a snapshot")
            if payload["source_refs"]:
                available = {
                    ref["ref_id"]: item["snapshot_id"]
                    for item in store.list_records()
                    if item["kind"] == "observation"
                    and item["scope"].get("workspace_id") == workspace_id
                    for ref in item["source_refs"]
                }
                if not set(payload["source_refs"]) <= set(available) or any(
                    available[ref_id] != payload["snapshot_id"] for ref_id in payload["source_refs"]
                ):
                    raise ContractError("source reference scope mismatch")
            for conflict_id in payload.get("conflict_ids", []):
                if store.read_record(conflict_id) is None:
                    raise ContractError("unknown conflict reference")
            if payload["revalidation"]["negative_claim"]:
                source = (
                    store.read_snapshot(payload.get("snapshot_id"))
                    if payload.get("snapshot_id")
                    else None
                )
                if (
                    source is None
                    or source["scope_paths"]
                    or not source["coverage"]["complete_for_scope"]
                ):
                    raise ContractError("negative claim requires complete inventory snapshot")
            result = store.write_record(project_id, payload)
        elif operation == "accept":
            validate_basis_reference(payload["acceptance_basis"])
            result = store.accept(payload)
        elif operation == "checkpoint":
            assert isinstance(workspace_id, str) and isinstance(task_id, str)
            if any(
                item["support"] in {"runtime_observed", "tool_reported"}
                for item in payload["completed_actions"]
            ):
                raise ContractError("caller cannot claim native execution support")
            if payload["snapshot_id"] is not None:
                snap = store.read_snapshot(payload["snapshot_id"])
                if snap is None or snap["workspace_id"] != workspace_id:
                    raise ContractError("checkpoint snapshot identity mismatch")
            result = store.write_checkpoint(project_id, workspace_id, task_id, payload)
        elif operation == "inspect":
            result = (
                store.read_record(payload["record_id"])
                if "record_id" in payload
                else store.list_records()
            )
        elif operation == "recall":
            assert isinstance(workspace_id, str) and workspace is not None
            status, result = _pack(
                store, project, workspace, project_id, workspace_id, task_id, payload
            )
            return response(request_id, status, result)
        elif operation in {"observe", "refresh"}:
            if workspace is None or workspace_id is None:
                raise ContractError("workspace identity is required")
            lexical_search = operation == "observe" and "query" in payload
            scopes = (
                tuple(payload.get("scope_paths", ()))
                if lexical_search or operation == "refresh"
                else (payload["path"],)
            )
            snapshot = _current_snapshot(
                workspace, project_id, workspace_id, project["policy"]["excluded_paths"], scopes
            )
            if operation == "refresh":
                result = store.refresh_snapshot(
                    snapshot,
                    key=payload["idempotency_key"],
                    scope_paths=list(scopes),
                )
            elif lexical_search:
                from .sources import lexical_matches

                hits, omitted = lexical_matches(Path(workspace["root"]), snapshot, payload["query"])
                if not hits and not snapshot["coverage"]["complete_for_scope"]:
                    return response(
                        request_id,
                        "partial",
                        {"snapshot_id": snapshot["snapshot_id"], "references": []},
                        limitations=["scope_incomplete_no_negative_claim"],
                    )
                references = [
                    {
                        "ref_id": str(uuid4()),
                        "type": "project_document"
                        if workspace["workspace_kind"] == "directory"
                        else "source_file",
                        "locator": {
                            "path": hit["path"],
                            "symbol": None,
                            "line_start": hit["line"],
                            "line_end": hit["line"],
                        },
                        "digest": "sha256:" + cast(str, hit["sha256"]),
                        "collected_at": snapshot["captured_at"],
                        "collector": "local-source-lexical/1.0.0",
                        "coverage": {
                            "kind": "search",
                            "complete_for_scope": snapshot["coverage"]["complete_for_scope"]
                            and omitted == 0,
                            "scope": hit["path"],
                            "omitted": [],
                        },
                    }
                    for hit in hits
                ]
                query_digest = (
                    "sha256:" + hashlib.sha256(payload["query"].encode("utf-8")).hexdigest()
                )
                result = store.observe_search(
                    snapshot,
                    references,
                    query_digest=query_digest,
                    omitted_matches=omitted,
                    key=payload["idempotency_key"],
                )
                return response(
                    request_id,
                    "partial" if omitted else "ok",
                    result,
                    limitations=["additional_matches_omitted"] if omitted else [],
                )
            else:
                path = payload["path"]
                entry = snapshot["files"].get(path)
                if entry is None:
                    return response(
                        request_id,
                        "partial",
                        {"snapshot_id": snapshot["snapshot_id"], "reference": None},
                        limitations=["source_not_covered"],
                    )
                symbol = payload.get("symbol")
                line: int | None = None
                if symbol:
                    metadata = entry.get("python", {})
                    matches = [
                        item for item in metadata.get("definitions", []) if item["name"] == symbol
                    ]
                    if not matches:
                        return response(
                            request_id,
                            "partial",
                            {"snapshot_id": snapshot["snapshot_id"], "reference": None},
                            limitations=["symbol_not_observed"],
                        )
                    line = matches[0]["line"]
                ref_id = str(uuid4())
                reference = {
                    "ref_id": ref_id,
                    "type": "project_document"
                    if workspace["workspace_kind"] == "directory"
                    else "source_file",
                    "locator": {
                        "path": path,
                        "symbol": symbol,
                        "line_start": line,
                        "line_end": line,
                    },
                    "digest": "sha256:" + entry["sha256"],
                    "collected_at": snapshot["captured_at"],
                    "collector": "local-source/1.0.0",
                    "coverage": {
                        "kind": "definition" if symbol else "file",
                        "complete_for_scope": snapshot["coverage"]["complete_for_scope"],
                        "scope": path,
                        "omitted": list(snapshot["coverage"]["omitted_categories"]),
                    },
                }
                result = store.observe_snapshot(
                    snapshot,
                    reference,
                    path=path,
                    symbol=symbol,
                    key=payload["idempotency_key"],
                )
        elif operation == "disable":
            policy = registry.update_policy(
                project_id,
                payload["expected_policy_version"],
                "disabled",
                payload["idempotency_key"],
            )
            result = {"policy": policy}
        elif operation == "supersede":
            result = store.supersede(payload)
        elif operation == "delete":
            if payload["intent"] == "delete_record":
                result = store.delete_record(
                    payload["record_id"],
                    payload["expected_record_version"],
                    payload["idempotency_key"],
                )
            elif payload["intent"] == "delete_project":
                if project["policy"]["version"] != payload.get("expected_policy_version"):
                    raise VersionConflict("version_conflict")
                project_dir = registry.project_dir(project_id)
                permitted = {"memory.sqlite3", "memory.lock", "memory.sqlite3-journal"}
                if {item.name for item in project_dir.iterdir()} - permitted:
                    return response(
                        request_id,
                        "partial",
                        {"project_id": project_id},
                        limitations=["unknown_managed_files_preserved"],
                    )
                if store.lock_path.exists() and (
                    store.lock_path.lstat().st_nlink != 1
                    or not check_permissions(store.lock_path, directory=False).write_allowed
                ):
                    raise StoreError("permission_denied")
                with FileLock(store.lock_path, policy=LockPolicy(timeout_seconds=2)):
                    for path in (store.path, project_dir / "memory.sqlite3-journal"):
                        if not path.exists():
                            continue
                        if (
                            not check_permissions(path, directory=False).write_allowed
                            or path.lstat().st_nlink != 1
                        ):
                            raise StoreError("permission_denied")
                        _remove_owned_file(path, project_dir)
                if store.lock_path.exists():
                    if store.lock_path.lstat().st_nlink != 1:
                        raise StoreError("permission_denied")
                    _remove_owned_file(store.lock_path, project_dir)
                if os.name == "nt":
                    from ..windows_security import remove_private_path

                    info = project_dir.lstat()
                    if (
                        remove_private_path(
                            project_dir,
                            root=registry.layout.projects_dir,
                            expected_identity=(info.st_dev, info.st_ino),
                            directory_only=True,
                        )
                        != 1
                    ):
                        raise StoreError("busy")
                else:
                    project_dir.rmdir()
                registry.remove(project_id)
                result = {"deleted_project_id": project_id, "registration_removed": True}
            else:
                raise ContractError("unsupported_delete_scope")
        elif operation == "prune":
            cutoff = (
                (datetime.now(timezone.utc) - timedelta(days=payload["retention_days"]))
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
            )
            result = store.prune(
                cutoff,
                retention_days=payload["retention_days"],
                dry_run=payload["dry_run"],
                idempotency_key=payload.get("idempotency_key"),
            )
        elif operation == "export":
            records = store.list_records()
            digest = hashlib.sha256(
                canonical_json_bytes([(r["record_id"], r["version"]) for r in records])
            ).hexdigest()
            cursor = payload.get("cursor")
            offset = 0
            if cursor:
                token, _, raw_offset = cursor.partition(":")
                if token != digest or not raw_offset.isdigit():
                    raise VersionConflict("version_conflict")
                offset = int(raw_offset)
            selected: list[dict[str, Any]] = []
            while (
                offset < len(records)
                and len(canonical_json_bytes(selected + [records[offset]])) < 48 * 1024
            ):
                selected.append(records[offset])
                offset += 1
            if not selected and offset < len(records):
                return response(
                    request_id, "budget_insufficient", {"required": "single_record_exceeds_page"}
                )
            content: Any = (
                selected
                if payload["format"] == "json"
                else "\n".join(f"- {item['record_id']}: {item['summary']}" for item in selected)
            )
            result = {
                "format": payload["format"],
                "content": content,
                "next_cursor": f"{digest}:{offset}" if offset < len(records) else None,
                "record_version_snapshot": digest,
            }
        else:
            raise ContractError("operation not yet implemented")
        return response(request_id, "ok", result)
    except VersionConflict as error:
        return response(request_id, "conflict", limitations=[str(error)])
    except StoreError as error:
        if str(error) == "busy":
            return response(request_id, "busy", limitations=["managed_file_in_use"], retryable=True)
        reason = str(error)
        return response(
            request_id,
            "unavailable",
            limitations=[
                reason
                if reason
                in {
                    "permission_denied",
                    "unsafe_path",
                    "store_corrupt",
                    "unsupported_schema",
                    "store_missing",
                    "unsupported_journal_mode",
                }
                else "memory_unavailable"
            ],
        )
    except LockTimeoutError:
        return response(request_id, "busy", limitations=["bounded_lock_wait"], retryable=True)
    except RegistryError as error:
        if str(error) in {"version_conflict", "idempotency_conflict", "already_enrolled"}:
            return response(request_id, "conflict", limitations=[str(error)])
        reason = str(error)
        return response(
            request_id,
            "unavailable",
            limitations=[
                reason
                if reason
                in {
                    "identity_mismatch",
                    "permission_denied",
                    "unsafe_path",
                    "store_corrupt",
                    "unsupported_schema",
                }
                else "memory_unavailable"
            ],
        )
    except OSError as error:
        reason = str(error)
        return response(
            request_id,
            "unavailable",
            limitations=[
                reason
                if reason
                in {
                    "identity_mismatch",
                    "permission_denied",
                    "unsafe_path",
                    "store_corrupt",
                    "unsupported_schema",
                    "store_missing",
                    "unsupported_journal_mode",
                }
                else "memory_unavailable"
            ],
        )
    except ContractError as error:
        if str(error) == "response budget insufficient":
            return response(
                request_id,
                "budget_insufficient",
                {"partition": "narrow record output before mutation"},
            )
        return response(request_id, "invalid_request", limitations=["closed_operation_rejected"])
    except ValueError as error:
        return response(
            request_id,
            "unavailable",
            limitations=[
                str(error)
                if str(error)
                in {
                    "unsafe_path",
                    "identity_mismatch",
                    "git_unavailable",
                    "source_changed_during_read",
                    "windows_source_adapter_unavailable",
                }
                else "source_unavailable"
            ],
        )

"""Bounded source snapshots. Only relative metadata and digests leave this module."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import stat
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from opensocrates.windows_security import SourceRoot

WorkspaceKind = Literal["git_worktree", "directory"]
SCHEMA = "opensocrates.project-memory.snapshot/1.0.0"
ADAPTER = "local-source/1.0.0"
MAX_FILES = 2_000
MAX_INVENTORY = 8_000
MAX_FILE_BYTES = 1 << 20
MAX_BYTES = 32 << 20
MAX_SECONDS = 10
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_O_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "vendor",
        "build",
        "dist",
        "target",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)
EXCLUDED_NAMES = frozenset({".env", ".netrc", ".npmrc", "id_rsa", "id_ed25519"})
EXCLUDED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".der", ".sqlite", ".db")
TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".md",
        ".markdown",
        ".txt",
        ".rst",
        ".toml",
        ".yaml",
        ".yml",
        ".json",
        ".ini",
        ".cfg",
        ".sh",
        ".gitignore",
    }
)
CONFIG_NAMES = frozenset(
    {
        "pyproject.toml",
        "setup.cfg",
        "setup.py",
        "requirements.txt",
        "uv.lock",
        "poetry.lock",
        "pipfile.lock",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "makefile",
        "dockerfile",
        ".gitignore",
        ".gitattributes",
    }
)


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _allowed(path: str, kind: WorkspaceKind) -> bool:
    pure = PurePosixPath(path)
    if (
        pure.is_absolute()
        or not path
        or "\\" in path
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        return False
    parts = [part.lower() for part in pure.parts]
    name = parts[-1]
    if any(part in EXCLUDED_DIRS for part in parts[:-1]):
        return False
    if any(
        "credential" in part
        or "secret" in part
        or part.startswith(".env.")
        or part.startswith("sk-")
        for part in parts
    ):
        return False
    if (
        name in EXCLUDED_NAMES
        or name.startswith(".env.")
        or "credential" in name
        or "secret" in name
    ):
        return False
    if name.endswith(EXCLUDED_SUFFIXES):
        return False
    suffix = PurePosixPath(name).suffix
    return suffix in ({".md", ".markdown", ".txt"} if kind == "directory" else TEXT_SUFFIXES) or (
        kind == "git_worktree" and name in CONFIG_NAMES
    )


def _scope(path: str, scopes: tuple[str, ...]) -> bool:
    return not scopes or any(
        path == item or path.startswith(item.rstrip("/") + "/") for item in scopes
    )


def _safe_scope(paths: tuple[str, ...]) -> tuple[str, ...]:
    for path in paths:
        if not path or path == "." or path.startswith("/") or "\\" in path:
            raise ValueError("unsafe_path")
        if any(part in {"", ".", ".."} for part in path.split("/")):
            raise ValueError("unsafe_path")
        if os.name == "nt":
            from opensocrates.windows_security import validate_source_relative

            validate_source_relative(path)
    return tuple(sorted(set(paths)))


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, timeout=3, check=False
    )
    if result.returncode:
        raise ValueError("git_unavailable")
    return result.stdout


def _git_state(root: Path) -> dict[str, object]:
    if _git(root, "rev-parse", "--is-inside-work-tree").strip() != b"true":
        raise ValueError("git_unavailable")
    top = Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel").strip())).resolve()
    if os.name == "nt":
        from opensocrates.windows_security import open_source_root

        with open_source_root(top) as reported, open_source_root(root) as requested:
            if reported.identity != requested.identity:
                raise ValueError("identity_mismatch")
    elif top != root:
        raise ValueError("identity_mismatch")
    head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    ref_result = subprocess.run(
        ["git", "-C", str(root), "symbolic-ref", "-q", "--short", "HEAD"],
        capture_output=True,
        timeout=3,
        check=False,
    )
    if ref_result.returncode not in {0, 1}:
        raise ValueError("git_unavailable")
    ref = (
        ref_result.stdout.decode("utf-8", "replace").strip() if ref_result.returncode == 0 else None
    )
    status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored=no")
    paths = _git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    return {
        "head_oid": head,
        "ref": _digest(ref) if ref else None,
        "status_digest": hashlib.sha256(status).hexdigest(),
        "dirty": bool(status),
        "inventory": tuple(sorted({os.fsdecode(item) for item in paths.split(b"\0") if item})),
    }


def _directory_inventory(
    root: Path, deadline: float, source_root: SourceRoot | None = None
) -> tuple[tuple[str, ...], bool]:
    if os.name == "nt":
        from opensocrates.windows_security import inventory_source_files

        if source_root is None:
            raise ValueError("windows_source_adapter_unavailable")
        return inventory_source_files(
            source_root, deadline=deadline, max_paths=MAX_INVENTORY, excluded_dirs=EXCLUDED_DIRS
        )
    paths: list[str] = []
    if root.is_symlink():
        return (), True
    for base, dirs, files in os.walk(root, followlinks=False):
        if len(paths) >= MAX_INVENTORY or time.monotonic() >= deadline:
            return tuple(sorted(paths)), True
        dirs[:] = sorted(d for d in dirs if d.lower() not in EXCLUDED_DIRS)
        prefix = Path(base).relative_to(root)
        paths.extend((prefix / name).as_posix() for name in sorted(files))
        paths.extend(
            (prefix / name).as_posix() for name in dirs if (Path(base) / name).is_symlink()
        )
    return tuple(sorted(paths)), False


def _read_file(
    root_fd: int | SourceRoot, relative: str
) -> tuple[bytes | None, str | None, tuple[int, int, int, int] | None]:
    """Open each path component without following symlinks, then verify one read."""
    if os.name == "nt":
        from opensocrates.windows_security import read_source_file

        return read_source_file(cast("SourceRoot", root_fd), relative, MAX_FILE_BYTES)
    fd = os.dup(cast(int, root_fd))
    try:
        parts = relative.split("/")
        for component in parts[:-1]:
            child = os.open(component, os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        child = os.open(parts[-1], os.O_RDONLY | _O_NOFOLLOW | _O_NONBLOCK, dir_fd=fd)
        try:
            before = os.fstat(child)
            if not stat.S_ISREG(before.st_mode):
                return None, "unsafe_path", None
            if before.st_size > MAX_FILE_BYTES:
                return None, "oversized", None
            chunks: list[bytes] = []
            size = 0
            while True:
                chunk = os.read(child, min(65536, MAX_FILE_BYTES + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    return None, "oversized", None
                chunks.append(chunk)
            after = os.fstat(child)
            identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != identity:
                return None, "source_changed_during_read", None
            return b"".join(chunks), None, identity
        finally:
            os.close(child)
    except (OSError, ValueError):
        return None, "unsafe_path", None
    finally:
        os.close(fd)


def _python_metadata(data: bytes) -> dict[str, object]:
    try:
        tree = ast.parse(data.decode("utf-8"))
    except (UnicodeDecodeError, SyntaxError):
        return {
            "parse_status": "unavailable",
            "imports": [],
            "definitions": [],
            "dynamic_edges": "unknown",
        }
    imports: list[dict[str, object]] = []
    definitions: list[dict[str, object]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.parents: list[str] = []

        def visit_Import(self, node: ast.Import) -> None:
            imports.extend({"module": alias.name, "line": node.lineno} for alias in node.names)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            imports.append({"module": "." * node.level + (node.module or ""), "line": node.lineno})

        def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            self._definition(node, "function")

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self._definition(node, "class")

        def _definition(
            self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, kind: str
        ) -> None:
            definitions.append(
                {"name": ".".join([*self.parents, node.name]), "kind": kind, "line": node.lineno}
            )
            self.parents.append(node.name)
            self.generic_visit(node)
            self.parents.pop()

    Visitor().visit(tree)
    return {
        "parse_status": "ok",
        "imports": imports,
        "definitions": definitions,
        "dynamic_edges": "unknown",
    }


def capture_snapshot(  # noqa: C901 - bounded collection keeps one audit path
    root: Path,
    workspace_kind: WorkspaceKind,
    project_id: str,
    workspace_id: str,
    scope_paths: tuple[str, ...] = (),
    excluded_paths: tuple[str, ...] = (),
) -> dict[str, object]:
    """Capture a metadata-only snapshot of a registered root's declared text scope.

    The caller must validate registration/root ownership. This function rejects a
    symlink root and unsafe scope; it never follows symlinks during file reads.
    """
    if workspace_kind not in {"git_worktree", "directory"} or not project_id or not workspace_id:
        raise ValueError("invalid_snapshot_request")
    scopes = _safe_scope(scope_paths)
    exclusions = _safe_scope(excluded_paths)
    root = Path(root).absolute()
    source_root: SourceRoot | None = None
    if os.name == "nt":
        from opensocrates.windows_security import open_source_root

        source_root = open_source_root(root)
    else:
        if root.is_symlink() or not root.is_dir():
            raise ValueError("unsafe_path")
        root = root.resolve()
    try:
        root_before = root.stat(follow_symlinks=False)
        start = time.monotonic()
        deadline = start + MAX_SECONDS
        git_before = _git_state(root) if workspace_kind == "git_worktree" else None
        if git_before:
            inventory = git_before["inventory"]
            inventory_truncated = False
        else:
            inventory, inventory_truncated = _directory_inventory(root, deadline, source_root)
        assert isinstance(inventory, tuple)
        entries: dict[str, dict[str, object]] = {}
        omitted: dict[str, int] = {}
        if inventory_truncated:
            omitted["budget"] = 1
        unstable: list[str] = []
        identities: dict[str, tuple[int, int, int, int]] = {}
        scanned_bytes = 0
        root_fd: int | SourceRoot = (
            source_root
            if source_root is not None
            else os.open(root, os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW)
        )
        try:
            for path in inventory:
                if not _scope(path, scopes):
                    continue
                if any(_scope(path, (excluded,)) for excluded in exclusions):
                    omitted["excluded_or_unsupported"] = (
                        omitted.get("excluded_or_unsupported", 0) + 1
                    )
                    continue
                if not _allowed(path, workspace_kind):
                    omitted["excluded_or_unsupported"] = (
                        omitted.get("excluded_or_unsupported", 0) + 1
                    )
                    continue
                if (
                    len(entries) >= MAX_FILES
                    or scanned_bytes >= MAX_BYTES
                    or time.monotonic() - start >= MAX_SECONDS
                ):
                    omitted["budget"] = omitted.get("budget", 0) + 1
                    continue
                data, reason, identity = _read_file(root_fd, path)
                if reason or data is None or identity is None:
                    key = reason or "unavailable"
                    omitted[key] = omitted.get(key, 0) + 1
                    if key == "source_changed_during_read":
                        unstable.append(path)
                    continue
                if b"\0" in data:
                    omitted["binary"] = omitted.get("binary", 0) + 1
                    continue
                try:
                    data.decode("utf-8")
                except UnicodeDecodeError:
                    omitted["unsupported_encoding"] = omitted.get("unsupported_encoding", 0) + 1
                    continue
                scanned_bytes += len(data)
                if scanned_bytes > MAX_BYTES:
                    omitted["budget"] = omitted.get("budget", 0) + 1
                    break
                entry: dict[str, object] = {
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                }
                if path.endswith(".py") and workspace_kind == "git_worktree":
                    entry["python"] = _python_metadata(data)
                entries[path] = entry
                identities[path] = identity
            for path, before in identities.items():
                second_read, reason, after = _read_file(root_fd, path)
                if (
                    reason
                    or before != after
                    or second_read is None
                    or hashlib.sha256(second_read).hexdigest() != entries[path]["sha256"]
                ):
                    unstable.append(path)
        finally:
            if source_root is None:
                os.close(cast(int, root_fd))
        git_after = _git_state(root) if workspace_kind == "git_worktree" else None
        if git_after:
            inventory_after = git_after["inventory"]
            inventory_after_truncated = False
        else:
            inventory_after, inventory_after_truncated = _directory_inventory(
                root, deadline, source_root
            )
        if inventory_after_truncated:
            omitted["budget"] = omitted.get("budget", 0) + 1
        try:
            root_after = root.stat(follow_symlinks=False)
            root_changed = (root_before.st_dev, root_before.st_ino) != (
                root_after.st_dev,
                root_after.st_ino,
            )
        except OSError:
            root_changed = True
        if inventory_after != inventory or git_after != git_before:
            omitted["state_changed_during_scan"] = 1
        if source_root is not None:
            from opensocrates.windows_security import open_source_root

            try:
                again = open_source_root(root)
                root_changed = root_changed or source_root.identity != again.identity
                again.close()
            except OSError:
                root_changed = True
        if root_changed:
            omitted["root_changed_during_scan"] = 1
        config = {
            path: entry["sha256"]
            for path, entry in entries.items()
            if PurePosixPath(path).name.lower() in CONFIG_NAMES
        }
        coverage = {
            "complete_for_scope": not any(key != "excluded_or_unsupported" for key in omitted)
            and not unstable,
            "omitted_categories": omitted,
            "unstable_files": sorted(set(unstable)),
            "search_boundary": {
                "paths": list(scopes) if scopes else ["."],
                "file_types": "allowed_text_only",
            },
            "dynamic_edges": "unknown" if workspace_kind == "git_worktree" else "not_applicable",
        }
        return {
            "schema": SCHEMA,
            "snapshot_id": str(uuid.uuid4()),
            "project_id": project_id,
            "workspace_id": workspace_id,
            "workspace_kind": workspace_kind,
            "root_identity_digest": _digest(
                list(source_root.identity)
                if source_root is not None
                else [root_before.st_dev, root_before.st_ino]
            ),
            "head_oid": git_after["head_oid"] if git_after else None,
            "ref": git_after["ref"] if git_after else None,
            "status_digest": git_after["status_digest"] if git_after else None,
            "dirty": git_after["dirty"] if git_after else None,
            "scope_paths": list(scopes),
            "inventory_digest": _digest(sorted(entries)),
            "content_manifest_digest": _digest({p: e["sha256"] for p, e in entries.items()}),
            "exclusion_digest": _digest(
                {
                    "adapter": ADAPTER,
                    "excluded_dirs": sorted(EXCLUDED_DIRS),
                    "excluded_names": sorted(EXCLUDED_NAMES),
                    "excluded_suffixes": EXCLUDED_SUFFIXES,
                    "policy_exclusions": list(exclusions),
                }
            ),
            "configuration_digest": _digest(config),
            "adapter_versions": {"local_source": ADAPTER},
            "coverage": coverage,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "files": entries,
        }

    finally:
        if source_root is not None:
            source_root.close()


def revalidate_snapshot(old: dict[str, object], current: dict[str, object]) -> dict[str, object]:
    """Compare two snapshots; incomplete scope never yields a current claim."""
    identity_keys = (
        "schema",
        "project_id",
        "workspace_id",
        "workspace_kind",
        "scope_paths",
        "root_identity_digest",
    )
    if any(old.get(key) != current.get(key) for key in identity_keys):
        return {"freshness": "unknown", "reason": "identity_mismatch", "changes": {}}
    previous = old.get("files")
    present = current.get("files")
    if not isinstance(previous, dict) or not isinstance(present, dict):
        return {"freshness": "unknown", "reason": "missing_manifest", "changes": {}}
    removed = set(previous) - set(present)
    added = set(present) - set(previous)
    modified = sorted(p for p in set(previous) & set(present) if previous[p] != present[p])
    renamed: list[dict[str, str]] = []
    for before in sorted(removed):
        digest = previous[before].get("sha256") if isinstance(previous[before], dict) else None
        matches = [
            after
            for after in sorted(added)
            if isinstance(present[after], dict) and present[after].get("sha256") == digest
        ]
        if len(matches) == 1:
            after = matches[0]
            renamed.append({"from": before, "to": after})
            removed.remove(before)
            added.remove(after)
    changes: dict[str, object] = {
        "added": sorted(added),
        "removed": sorted(removed),
        "modified": modified,
        "renamed": renamed,
        "head_changed": old.get("head_oid") != current.get("head_oid"),
        "ref_changed": old.get("ref") != current.get("ref"),
        "dirty_changed": old.get("status_digest") != current.get("status_digest"),
        "inventory_changed": old.get("inventory_digest") != current.get("inventory_digest"),
        "configuration_changed": old.get("configuration_digest")
        != current.get("configuration_digest"),
        "exclusion_changed": old.get("exclusion_digest") != current.get("exclusion_digest"),
        "adapter_changed": old.get("adapter_versions") != current.get("adapter_versions"),
    }
    changed = bool(
        added
        or removed
        or modified
        or renamed
        or any(
            changes[key]
            for key in (
                "head_changed",
                "ref_changed",
                "dirty_changed",
                "inventory_changed",
                "configuration_changed",
                "exclusion_changed",
                "adapter_changed",
            )
        )
        or old.get("content_manifest_digest") != current.get("content_manifest_digest")
    )
    if changed:
        return {"freshness": "stale", "reason": "stale_snapshot", "changes": changes}
    old_coverage = old.get("coverage")
    new_coverage = current.get("coverage")
    if (
        not isinstance(old_coverage, dict)
        or not isinstance(new_coverage, dict)
        or not old_coverage.get("complete_for_scope")
        or not new_coverage.get("complete_for_scope")
    ):
        return {"freshness": "unknown", "reason": "scope_incomplete", "changes": changes}
    return {"freshness": "current", "reason": None, "changes": changes}


def lexical_matches(  # noqa: C901  # Bounded no-follow search validates each file.
    root: Path, snapshot: dict[str, object], query: str, *, max_hits: int = 32
) -> tuple[list[dict[str, object]], int]:
    """Return current, bounded lexical locations without retaining source bytes."""
    if not isinstance(query, str) or not query or len(query) > 256 or "\x00" in query:
        raise ValueError("invalid_search_query")
    files = snapshot.get("files")
    if not isinstance(files, dict):
        raise ValueError("invalid_snapshot")
    hits: list[dict[str, object]] = []
    omitted = 0
    deadline = time.monotonic() + MAX_SECONDS
    source_root: SourceRoot | None = None
    if os.name == "nt":
        from opensocrates.windows_security import open_source_root

        source_root = open_source_root(root)
        if _digest(list(source_root.identity)) != snapshot.get("root_identity_digest"):
            source_root.close()
            raise ValueError("identity_mismatch")
    root_fd: int | SourceRoot = (
        source_root
        if source_root is not None
        else os.open(root, os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW)
    )
    try:
        for path, entry in sorted(files.items()):
            if time.monotonic() >= deadline:
                raise ValueError("search_budget_exhausted")
            if not isinstance(path, str) or not isinstance(entry, dict):
                raise ValueError("invalid_snapshot")
            data, reason, _identity = _read_file(root_fd, path)
            if reason or data is None or hashlib.sha256(data).hexdigest() != entry.get("sha256"):
                raise ValueError("source_changed_during_read")
            decoded = data.decode("utf-8")
            for line_number, line in enumerate(decoded.splitlines(), start=1):
                if query.casefold() in line.casefold():
                    if len(hits) < max_hits:
                        hits.append({"path": path, "line": line_number, "sha256": entry["sha256"]})
                    else:
                        omitted += 1
    finally:
        if source_root is None:
            os.close(cast(int, root_fd))
        else:
            source_root.close()
    return hits, omitted

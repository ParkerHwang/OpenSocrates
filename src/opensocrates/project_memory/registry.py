"""Explicit project/workspace enrollment and private registry identity."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from ..persistence.atomic import (
    atomic_replace_bytes,
    canonical_json_bytes,
    decode_json_bytes,
    read_bytes,
)
from ..persistence.locks import FileLock, LockPolicy
from ..persistence.paths import DataRootLayout, resolve_data_root, secure_join
from ..persistence.permissions import check_permissions, create_owner_only_directory
from .contracts import validate_basis_reference
from .git import run_git

REGISTRY_VERSION = 1
MAX_REGISTRY_BYTES = 2 * 1024 * 1024


class RegistryError(OSError):
    """An identity, owner, or registry check failed closed."""


def _identity(path: Path) -> tuple[int, ...]:
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or (getattr(info, "st_file_attributes", 0) & 0x400)
    ):
        raise RegistryError("unsafe_path")
    if os.name == "nt":
        from ..windows_security import open_source_root, source_root_owner_is_current

        with open_source_root(path) as bound:
            if not source_root_owner_is_current(bound):
                raise RegistryError("permission_denied")
            return bound.identity
    current_uid = getattr(os, "getuid", None)
    if current_uid is None or info.st_uid != current_uid():
        raise RegistryError("permission_denied")
    return info.st_dev, info.st_ino


def _safe_root(raw: str) -> Path:
    path = Path(raw).expanduser().absolute()
    if not path.exists():
        raise RegistryError("unsafe_path")
    if path.is_symlink():
        raise RegistryError("unsafe_path")
    path = path.resolve(strict=True)
    for ancestor in (*reversed(path.parents), path):
        if ancestor.exists():
            info = ancestor.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise RegistryError("unsafe_path")
    _identity(path)
    return path.resolve(strict=True)


def _read_git_file(path: Path) -> str:
    """Read one bounded Git pointer through a no-follow file capability."""
    if os.name == "nt":
        from ..windows_security import open_source_root, read_source_file

        with open_source_root(path.parent) as parent:
            data, reason, _identity_value = read_source_file(parent, path.name, 4096)
        if reason or data is None:
            raise RegistryError("unsafe_path")
    else:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as error:
            raise RegistryError("unsafe_path") from error
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 4096:
                raise RegistryError("unsafe_path")
            data = os.read(descriptor, 4097)
            named = path.lstat()
            if (
                len(data) > 4096
                or stat.S_ISLNK(named.st_mode)
                or (before.st_dev, before.st_ino) != (named.st_dev, named.st_ino)
                or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (
                    os.fstat(descriptor).st_dev,
                    os.fstat(descriptor).st_ino,
                    os.fstat(descriptor).st_size,
                    os.fstat(descriptor).st_mtime_ns,
                )
            ):
                raise RegistryError("unsafe_path")
        finally:
            os.close(descriptor)
    try:
        value = data.decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise RegistryError("unsafe_path") from error
    if not value or "\x00" in value or "\n" in value or "\r" in value:
        raise RegistryError("unsafe_path")
    return value


def _same_regular_file(left: Path, right: Path) -> bool:
    try:
        first, second = left.lstat(), right.lstat()
    except OSError:
        return False
    if any(
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or (getattr(info, "st_file_attributes", 0) & 0x400)
        for info in (first, second)
    ):
        return False
    return (first.st_dev, first.st_ino) == (second.st_dev, second.st_ino)


def _validate_git_back_reference(root: Path, git_dir: Path) -> None:
    dotgit = root / ".git"
    try:
        metadata = dotgit.lstat()
    except OSError as error:
        raise RegistryError("identity_mismatch") from error
    if stat.S_ISDIR(metadata.st_mode):
        if _identity(dotgit) != _identity(git_dir):
            raise RegistryError("identity_mismatch")
        return
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise RegistryError("unsafe_path")
    pointer = _read_git_file(dotgit)
    if not pointer.startswith("gitdir: "):
        raise RegistryError("identity_mismatch")
    outbound = Path(pointer[len("gitdir: ") :])
    if not outbound.is_absolute():
        outbound = root / outbound
    if _identity(outbound.resolve(strict=True)) != _identity(git_dir):
        raise RegistryError("identity_mismatch")
    inbound = Path(_read_git_file(git_dir / "gitdir"))
    if not inbound.is_absolute():
        inbound = git_dir / inbound
    if not _same_regular_file(inbound, dotgit):
        raise RegistryError("identity_mismatch")


def _git_binding(root: Path) -> dict[str, Any] | None:
    try:
        result = run_git(
            root, "rev-parse", "--show-toplevel", "--absolute-git-dir", "--git-common-dir"
        )
    except ValueError as error:
        if (root / ".git").exists():
            raise RegistryError("git_unavailable") from error
        return None
    if result.returncode:
        return None
    try:
        lines = result.stdout.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise RegistryError("git_unavailable") from error
    if len(lines) != 3:
        raise RegistryError("identity_mismatch")
    top = _safe_root(lines[0])
    if top != root:
        raise RegistryError("identity_mismatch")
    git_dir = Path(lines[1]).resolve(strict=True)
    common = Path(lines[2])
    if not common.is_absolute():
        common = (root / common).resolve(strict=True)
    else:
        common = common.resolve(strict=True)
    _validate_git_back_reference(root, git_dir)
    return {
        "workspace_kind": "git_worktree",
        "git_dir": str(git_dir),
        "git_identity": list(_identity(git_dir)),
        "common_dir": str(common),
        "common_identity": list(_identity(common)),
    }


def binding_for(raw_root: str) -> dict[str, Any]:
    root = _safe_root(raw_root)
    binding: dict[str, Any] = {"root": str(root), "root_identity": list(_identity(root))}
    git = _git_binding(root)
    if git is None:
        binding.update(
            {
                "workspace_kind": "directory",
                "git_dir": None,
                "git_identity": None,
                "common_dir": None,
                "common_identity": None,
            }
        )
    else:
        binding.update(git)
    return binding


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def disclosure(
    binding: dict[str, Any],
    policy: dict[str, Any],
    policy_version: int = 1,
    target_project_id: str | None = None,
) -> dict[str, Any]:
    public = {
        "root": binding["root"],
        "workspace_kind": binding["workspace_kind"],
        "storage": "owned product data root/projects/<opaque project id>/memory.sqlite3",
        "mode": policy["mode"],
        "capture_policy": policy["capture_policy"],
        "excluded_paths": policy["excluded_paths"],
        "retention": "accepted decisions retained; eligible proposed/completed items after 30 days",
        "allowed": ["bounded public decisions", "task checkpoints", "source metadata and digests"],
        "forbidden": [
            "raw prompts",
            "transcripts",
            "source copies",
            "credentials",
            "hidden reasoning",
        ],
        "management": ["inspect", "export", "disable", "delete"],
        "policy_version": policy_version,
        "join_project_id": target_project_id,
    }
    return {
        "disclosure": public,
        "disclosure_digest": _digest({"binding": binding, "policy": public}),
    }


class ProjectRegistry:
    def __init__(self, data_root: Path | None = None) -> None:
        self.layout = DataRootLayout.from_root(data_root or resolve_data_root())

    @property
    def path(self) -> Path:
        return self.layout.projects_dir / "registry.json"

    def load(self) -> dict[str, Any] | None:
        """Read existing private registration without creating any path."""
        root = self.layout.root
        projects = self.layout.projects_dir
        if not projects.exists():
            return None
        if (
            not check_permissions(root, directory=True).write_allowed
            or not check_permissions(projects, directory=True).write_allowed
        ):
            raise RegistryError("permission_denied")
        if not self.path.exists():
            return None
        if (
            self.path.lstat().st_nlink != 1
            or not check_permissions(self.path, directory=False).write_allowed
        ):
            raise RegistryError("permission_denied")
        try:
            value = decode_json_bytes(
                read_bytes(self.path, max_bytes=MAX_REGISTRY_BYTES), max_bytes=MAX_REGISTRY_BYTES
            )
        except (OSError, ValueError) as error:
            raise RegistryError("store_corrupt") from error
        if (
            not isinstance(value, dict)
            or value.get("version") != REGISTRY_VERSION
            or not isinstance(value.get("projects"), dict)
        ):
            raise RegistryError("unsupported_schema")
        return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_replace_bytes(self.path, canonical_json_bytes(value, max_bytes=MAX_REGISTRY_BYTES))

    def preview(
        self,
        raw_root: str,
        policy: dict[str, Any],
        expected_policy_version: int | None = None,
        target_project_id: str | None = None,
    ) -> dict[str, Any]:
        binding = binding_for(raw_root)
        if target_project_id is not None:
            project, _ = self.get(target_project_id)
            self._check_join(project, binding, policy, expected_policy_version)
            return disclosure(binding, policy, expected_policy_version or 1, target_project_id)
        return disclosure(
            binding,
            policy,
            expected_policy_version + 1 if expected_policy_version is not None else 1,
        )

    @staticmethod
    def _check_join(
        project: dict[str, Any],
        binding: dict[str, Any],
        policy: dict[str, Any],
        expected_version: int | None,
    ) -> None:
        if (
            binding["workspace_kind"] != "git_worktree"
            or project["policy"]["version"] != expected_version
            or any(project["policy"].get(key) != value for key, value in policy.items())
            or not any(
                workspace["workspace_kind"] == "git_worktree"
                and workspace["common_identity"] == binding["common_identity"]
                and workspace["common_dir"] == binding["common_dir"]
                for workspace in project["workspaces"].values()
            )
        ):
            raise RegistryError("identity_mismatch")

    def enroll(  # noqa: C901  # Explicit enrollment, join, and policy CAS are audited together.
        self,
        raw_root: str,
        policy: dict[str, Any],
        expected_digest: str,
        authorization_basis: str,
        attribution: str,
        expected_policy_version: int | None = None,
        target_project_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        binding = binding_for(raw_root)
        if idempotency_key is None:
            raise RegistryError("idempotency_key_required")
        disclosed_version = (expected_policy_version or 0) + (
            0 if target_project_id is not None else 1
        )
        if disclosed_version < 1:
            raise RegistryError("version_conflict")
        preview = disclosure(binding, policy, disclosed_version, target_project_id)
        validate_basis_reference(authorization_basis)
        if expected_digest != preview["disclosure_digest"]:
            raise RegistryError("identity_mismatch")
        if attribution not in {"operator_declared", "agent_reported_user_instruction"}:
            raise RegistryError("permission_denied")
        create_owner_only_directory(self.layout.root, parents=True)
        create_owner_only_directory(self.layout.projects_dir)
        if (
            not check_permissions(self.layout.root, directory=True).write_allowed
            or not check_permissions(self.layout.projects_dir, directory=True).write_allowed
        ):
            raise RegistryError("permission_denied")
        with FileLock(
            self.layout.projects_dir / "registry.lock", policy=LockPolicy(timeout_seconds=2)
        ):
            registry = self.load() or {"version": REGISTRY_VERSION, "projects": {}}
            for existing in registry["projects"].values():
                prior = existing.get("enrollment_mutations", {}).get(idempotency_key)
                if prior is not None:
                    if (
                        prior["disclosure_digest"] != expected_digest
                        or prior["root"] != binding["root"]
                    ):
                        raise RegistryError("idempotency_conflict")
                    return cast(dict[str, Any], prior["result"])
            if target_project_id is not None:
                target = registry["projects"].get(target_project_id)
                if not isinstance(target, dict):
                    raise RegistryError("identity_mismatch")
                self._check_join(target, binding, policy, expected_policy_version)
                if any(
                    workspace["root"] == binding["root"]
                    for project in registry["projects"].values()
                    for workspace in project["workspaces"].values()
                ):
                    raise RegistryError("already_enrolled")
                workspace_id = str(uuid4())
                target["workspaces"][workspace_id] = {
                    "workspace_id": workspace_id,
                    **binding,
                    "authorization": {"basis": authorization_basis, "attribution": attribution},
                }
                result = {
                    "project_id": target_project_id,
                    "workspace_id": workspace_id,
                    "workspace_kind": "git_worktree",
                    "policy_version": target["policy"]["version"],
                    "authorization_attribution": attribution,
                }
                target.setdefault("enrollment_mutations", {})[idempotency_key] = {
                    "disclosure_digest": expected_digest,
                    "root": binding["root"],
                    "result": result,
                }
                self._save(registry)
                return result
            for project in registry["projects"].values():
                for workspace in project["workspaces"].values():
                    if workspace["root"] == binding["root"]:
                        if workspace["root_identity"] != binding["root_identity"]:
                            raise RegistryError("identity_mismatch")
                        if (
                            expected_policy_version is None
                            or project["policy"]["version"] != expected_policy_version
                        ):
                            raise RegistryError("version_conflict")
                        project["policy"] = {
                            "version": expected_policy_version + 1,
                            **policy,
                            "enabled": True,
                        }
                        project["authorization"] = {
                            "basis": authorization_basis,
                            "attribution": attribution,
                        }
                        result = {
                            "project_id": project["project_id"],
                            "workspace_id": workspace["workspace_id"],
                            "workspace_kind": binding["workspace_kind"],
                            "policy_version": expected_policy_version + 1,
                            "authorization_attribution": attribution,
                        }
                        project.setdefault("enrollment_mutations", {})[idempotency_key] = {
                            "disclosure_digest": expected_digest,
                            "root": binding["root"],
                            "result": result,
                        }
                        self._save(registry)
                        return result
            project_id = str(uuid4())
            workspace_id = str(uuid4())
            project_dir = secure_join(self.layout.projects_dir, project_id)
            create_owner_only_directory(project_dir)
            from .store import MemoryStore

            MemoryStore(project_dir, private_root=binding["root"]).initialize()
            registry["projects"][project_id] = {
                "project_id": project_id,
                "policy": {"version": 1, **policy, "enabled": True},
                "authorization": {"basis": authorization_basis, "attribution": attribution},
                "workspaces": {
                    workspace_id: {
                        "workspace_id": workspace_id,
                        **binding,
                        "authorization": {"basis": authorization_basis, "attribution": attribution},
                    }
                },
                "enrollment_mutations": {
                    idempotency_key: {
                        "disclosure_digest": expected_digest,
                        "root": binding["root"],
                        "result": {
                            "project_id": project_id,
                            "workspace_id": workspace_id,
                            "workspace_kind": binding["workspace_kind"],
                            "policy_version": 1,
                            "authorization_attribution": attribution,
                        },
                    }
                },
            }
            self._save(registry)
        return {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "workspace_kind": binding["workspace_kind"],
            "policy_version": 1,
            "authorization_attribution": attribution,
        }

    def get(
        self, project_id: str, workspace_id: str | None = None
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        registry = self.load()
        project = registry["projects"].get(project_id) if registry else None
        if not isinstance(project, dict):
            raise RegistryError("identity_mismatch")
        workspace = project["workspaces"].get(workspace_id) if workspace_id else None
        if workspace_id and not isinstance(workspace, dict):
            raise RegistryError("identity_mismatch")
        if workspace:
            observed = binding_for(workspace["root"])
            if observed != {key: workspace[key] for key in observed}:
                raise RegistryError("identity_mismatch")
        return project, workspace

    def project_dir(self, project_id: str) -> Path:
        self.get(project_id)
        return secure_join(self.layout.projects_dir, project_id)

    def update_policy(
        self, project_id: str, expected_version: int, mode: str, idempotency_key: str
    ) -> dict[str, Any]:
        with FileLock(
            self.layout.projects_dir / "registry.lock", policy=LockPolicy(timeout_seconds=2)
        ):
            registry = self.load()
            if registry is None or project_id not in registry["projects"]:
                raise RegistryError("identity_mismatch")
            project = registry["projects"][project_id]
            mutations = project.setdefault("policy_mutations", {})
            previous = mutations.get(idempotency_key)
            if previous is not None:
                if previous["expected_version"] != expected_version or previous["mode"] != mode:
                    raise RegistryError("idempotency_conflict")
                return cast(dict[str, Any], previous["result"])
            if project["policy"]["version"] != expected_version:
                raise RegistryError("version_conflict")
            project["policy"]["version"] += 1
            project["policy"]["mode"] = mode
            project["policy"]["enabled"] = False if mode == "disabled" else True
            mutations[idempotency_key] = {
                "expected_version": expected_version,
                "mode": mode,
                "result": dict(project["policy"]),
            }
            if len(mutations) > 256:
                del mutations[sorted(mutations)[0]]
            self._save(registry)
            return cast(dict[str, Any], project["policy"])

    def remove(self, project_id: str) -> None:
        with FileLock(
            self.layout.projects_dir / "registry.lock", policy=LockPolicy(timeout_seconds=2)
        ):
            registry = self.load()
            if registry is None or project_id not in registry["projects"]:
                raise RegistryError("identity_mismatch")
            del registry["projects"][project_id]
            self._save(registry)

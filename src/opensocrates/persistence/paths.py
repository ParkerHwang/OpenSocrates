"""Secure, platform-neutral paths for OpenSocrates mutable state.

The runtime never accepts an arbitrary persistence path.  A :class:`DataRoot`
is selected from the documented host directory or the platform user-data
directory and all mutable files are addressed through its typed layout.
Development overrides require both an explicit development flag and a
development manifest flag; release configuration ignores the override.
"""

from __future__ import annotations

import os
import re
import stat
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

DATA_ROOT_ENV = "OPENSOCRATES_DATA_DIR"
DEVELOPMENT_MANIFEST_ENV = "OPENSOCRATES_DEVELOPMENT_MANIFEST"


class PathSecurityError(ValueError):
    """Raised when a path would escape the selected data root."""


class DevelopmentOverrideError(PathSecurityError):
    """Raised when a data-root override is used without development config."""


class DataRootUnavailableError(OSError):
    """Raised when a secure data root cannot be created or inspected."""


_SAFE_COMPONENT = re.compile(r"^[^/\\\x00]+$")


def _development_manifest_enabled(environ: Mapping[str, str]) -> bool:
    value = environ.get(DEVELOPMENT_MANIFEST_ENV, "").strip().casefold()
    return value in {"1", "true", "yes", "development"}


@dataclass(frozen=True, slots=True)
class DataRootConfig:
    """Inputs used to select a root.

    ``override`` and ``OPENSOCRATES_DATA_DIR`` are honored only when both
    ``development`` and ``development_manifest`` are true.  ``host_data_dir``
    represents a documented host-owned data directory and is preferred over
    the OS default when it is an existing, writable directory.
    """

    development: bool = False
    development_manifest: bool = False
    override: Path | None = None
    host_data_dir: Path | None = None


@dataclass(frozen=True, slots=True)
class DataRootLayout:
    """Canonical directories and files below one selected data root."""

    root: Path
    install_file: Path
    settings_file: Path
    capabilities_dir: Path
    runtime_dir: Path
    turns_dir: Path
    records_dir: Path
    metrics_dir: Path
    quarantine_dir: Path
    diagnostics_dir: Path

    @classmethod
    def from_root(cls, root: Path) -> "DataRootLayout":
        root = Path(root)
        return cls(
            root=root,
            install_file=root / "install.json",
            settings_file=root / "settings.json",
            capabilities_dir=root / "capabilities",
            runtime_dir=root / "runtime",
            turns_dir=root / "runtime" / "turns",
            records_dir=root / "records",
            metrics_dir=root / "metrics",
            quarantine_dir=root / "quarantine",
            diagnostics_dir=root / "diagnostics",
        )

    def month_dir(self, year_month: str) -> Path:
        """Return a records month directory after strict segment validation."""

        if re.fullmatch(r"\d{4}-\d{2}", year_month) is None:
            raise PathSecurityError("record month must be YYYY-MM")
        return secure_join(self.records_dir, year_month)

    def task_record(self, task_id: str, year_month: str) -> Path:
        """Return the canonical JSONL path for a task."""

        _validate_component(task_id, "task_id")
        return secure_join(self.month_dir(year_month), f"{task_id}.jsonl")

    def task_lock(self, task_id: str, year_month: str) -> Path:
        """Return the canonical per-task lock path."""

        _validate_component(task_id, "task_id")
        return secure_join(self.month_dir(year_month), f"{task_id}.lock")

    def turn_state(self, token_tag: str) -> Path:
        """Return a turn-state path addressed by an HMAC tag, never a token."""

        if re.fullmatch(r"sha256:[0-9a-f]{64}", token_tag) is None:
            raise PathSecurityError("turn token tag must be a SHA-256 tag")
        return secure_join(self.turns_dir, f"{token_tag[7:]}.json")

    def turn_lock(self, token_tag: str) -> Path:
        if re.fullmatch(r"sha256:[0-9a-f]{64}", token_tag) is None:
            raise PathSecurityError("turn token tag must be a SHA-256 tag")
        return secure_join(self.turns_dir, f"{token_tag[7:]}.lock")


@dataclass(frozen=True, slots=True)
class DataRoot:
    """Selected mutable data root and its typed layout."""

    layout: DataRootLayout
    development: bool = False

    @property
    def root(self) -> Path:
        return self.layout.root


def _validate_component(component: str, name: str) -> None:
    if not isinstance(component, str) or not component or not _SAFE_COMPONENT.fullmatch(component):
        raise PathSecurityError(f"invalid {name}")
    if component in {".", ".."}:
        raise PathSecurityError(f"invalid {name}")


def _is_writable_directory(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISDIR(info.st_mode) and not path.is_symlink() and os.access(path, os.W_OK)


def _default_root(environ: Mapping[str, str], home: Path, platform: str) -> Path:
    if platform == "darwin":
        return home / "Library" / "Application Support" / "OpenSocrates"
    if platform.startswith("win"):
        local_app_data = environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data).expanduser() / "OpenSocrates"
        return home / "AppData" / "Local" / "OpenSocrates"
    xdg_data_home = environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / "opensocrates"
    return home / ".local" / "share" / "opensocrates"


def resolve_data_root(
    config: DataRootConfig | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
    platform: str | None = None,
) -> Path:
    """Resolve the data root without creating or mutating filesystem state."""

    config = config or DataRootConfig()
    env = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    platform = sys.platform if platform is None else platform
    development_allowed = config.development and config.development_manifest

    if config.override is not None:
        if not development_allowed:
            raise DevelopmentOverrideError(
                "an explicit data-root override requires development configuration"
            )
        return Path(config.override).expanduser().absolute()

    env_override = env.get(DATA_ROOT_ENV)
    if env_override and development_allowed:
        return Path(env_override).expanduser().absolute()

    if config.host_data_dir is not None and _is_writable_directory(Path(config.host_data_dir)):
        return Path(config.host_data_dir).expanduser().absolute()
    return _default_root(env, home, platform)


def secure_join(root: Path, *components: str) -> Path:
    """Join path components while rejecting traversal and all symlink hops."""

    root = Path(root)
    if not root.is_absolute():
        raise PathSecurityError("data root must be absolute")
    try:
        root_info = root.lstat()
    except OSError as error:
        raise PathSecurityError("data root does not exist") from error
    if not stat.S_ISDIR(root_info.st_mode) or stat.S_ISLNK(root_info.st_mode):
        raise PathSecurityError("data root is not a real directory")

    candidate = root
    for component in components:
        _validate_component(component, "path component")
        candidate = candidate / component

    current = root
    relative_parts = candidate.relative_to(root).parts
    for component in relative_parts:
        current = current / component
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise PathSecurityError("cannot inspect data-root path") from error
        if stat.S_ISLNK(info.st_mode):
            raise PathSecurityError("symlink path component is not allowed")

    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve(strict=False)
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as error:
        raise PathSecurityError("path escapes the data root") from error
    return candidate


def ensure_data_root(config: DataRootConfig | None = None) -> DataRoot:
    """Create the canonical directory tree with restrictive initial modes."""

    config = config or DataRootConfig()
    root = resolve_data_root(config)
    try:
        root_was_present = root.exists()
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if root.is_symlink():
            raise DataRootUnavailableError("data root may not be a symlink")
        if os.name != "nt" and not root_was_present:
            os.chmod(root, 0o700)
        layout = DataRootLayout.from_root(root)
        for directory in (
            layout.capabilities_dir,
            layout.runtime_dir,
            layout.turns_dir,
            layout.records_dir,
            layout.metrics_dir,
            layout.quarantine_dir,
            layout.diagnostics_dir,
        ):
            was_present = directory.exists()
            directory.mkdir(mode=0o700, exist_ok=True)
            if directory.is_symlink():
                raise DataRootUnavailableError("data-root directory may not be a symlink")
            if os.name != "nt" and not was_present:
                os.chmod(directory, 0o700)
    except (OSError, PathSecurityError) as error:
        if isinstance(error, DataRootUnavailableError):
            raise
        raise DataRootUnavailableError("unable to establish secure data root") from error
    return DataRoot(layout=layout, development=config.development)


def current_month(*, now: datetime | None = None) -> str:
    """Return the UTC YYYY-MM partition used by record writers."""

    instant = now or datetime.now(timezone.utc)
    return instant.astimezone(timezone.utc).strftime("%Y-%m")

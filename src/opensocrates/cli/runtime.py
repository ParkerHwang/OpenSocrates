"""Packaged-runtime dependency composition and safe export boundaries.

The command dispatcher deliberately receives a small, typed service object.
This module is the only place where the packaged runtime discovers its
immutable compiled bundle and its documented mutable data root.  Commands do
not accept arbitrary store paths; tests and embedders may inject typed stores
through :class:`RuntimeServices`.
"""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..application.apply_control import ControlApplication
from ..application.diagnose import HealthAggregate
from ..content import ProjectionInstructionAssembler, load_reasoning_content_projections
from ..content.loader import load_compiled_bundle
from ..domain.models import CapabilityProfile, CompiledContentBundle
from ..hooks.dispatcher import Dispatcher
from ..hosts.registry import build_adapter
from ..persistence import (
    DataRoot,
    DataRootConfig,
    JsonlRecordStore,
    MetricsStore,
    SelectorOutcomeStore,
    SettingsStore,
    TaskStore,
    TurnStateStore,
    ensure_data_root,
)
from ..rendering.messages import LocaleCatalog
from ..selector import InstructionFileStore, SelectorApplication, SelectorConfig
from ..selector.claude_cli import ClaudeCliReasoningSelector
from ..selector.sdk import CodexReasoningSelector

DEFAULT_BUNDLE_FILENAME = "compiled-content.bundle.json"
DEFAULT_REASONING_CONTENT_FILENAME = "compiled-reasoning-content.bundle.json"
SELECTOR_DEADLINE_ENV = "OPENSOCRATES_SELECTOR_DEADLINE_SECONDS"
SELECTOR_TRANSCRIPT_ACCESS_ENV = "OPENSOCRATES_SELECTOR_TRANSCRIPT_ACCESS"


class BundleRepository:
    """Lazy typed repository for the current compiled JSON bundle."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._bundle: CompiledContentBundle | None = None

    def load(self) -> CompiledContentBundle:
        if self._bundle is None:
            self._bundle = load_compiled_bundle(self.path)
        return self._bundle

    def clear_cache(self) -> None:
        self._bundle = None


def _content_candidates(filename: str) -> tuple[Path, ...]:
    """Return deterministic packaged/source locations for one content sidecar."""

    candidates: list[Path] = []
    frozen_root = getattr(sys, "_MEIPASS", None)
    if isinstance(frozen_root, str) and frozen_root:
        candidates.append(Path(frozen_root) / "content" / filename)
    package_root = Path(__file__).resolve().parents[2]
    repository_root = package_root.parent
    candidates.extend(
        (
            package_root / "content" / filename,
            repository_root / "content" / filename,
            Path.cwd() / "content" / filename,
        )
    )
    unique: list[Path] = []
    for candidate in candidates:
        candidate = candidate.absolute()
        if candidate not in unique:
            unique.append(candidate)
    return tuple(unique)


def _bundle_candidates() -> tuple[Path, ...]:
    """Return deterministic packaged/source locations for the legacy bundle."""

    return _content_candidates(DEFAULT_BUNDLE_FILENAME)


def _reasoning_content_candidates() -> tuple[Path, ...]:
    """Return deterministic packaged/source locations for the selector sidecar."""

    return _content_candidates(DEFAULT_REASONING_CONTENT_FILENAME)


def discover_bundle_path(explicit: str | Path | None = None) -> Path:
    """Select the first existing compiled bundle, or a deterministic fallback."""

    if explicit is not None:
        return Path(explicit).expanduser().absolute()
    candidates = _bundle_candidates()
    for candidate in candidates:
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    return candidates[0] if candidates else (Path("content") / DEFAULT_BUNDLE_FILENAME).absolute()


def discover_reasoning_content_path(explicit: str | Path | None = None) -> Path:
    """Select the reasoning-content sidecar without following a final symlink."""

    if explicit is not None:
        return Path(explicit).expanduser().absolute()
    candidates = _reasoning_content_candidates()
    for candidate in candidates:
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    return (
        candidates[0]
        if candidates
        else (Path("content") / DEFAULT_REASONING_CONTENT_FILENAME).absolute()
    )


def _bounded_selector_integer(name: str, *, default: int, minimum: int, maximum: int) -> int:
    """Read one development/runtime override without accepting an unbounded value."""

    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip()
    if not value.isascii() or not value.isdecimal():
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if minimum <= parsed <= maximum else default


def _selector_transcript_access_enabled() -> bool:
    """Apply the explicit opt-out while failing safely to the product default."""

    raw = os.environ.get(SELECTOR_TRANSCRIPT_ACCESS_ENV)
    if raw is None:
        return True
    value = raw.strip().casefold()
    if value in {"0", "false", "no", "off", "disabled"}:
        return False
    if value in {"1", "true", "yes", "on", "enabled"}:
        return True
    return True


def _selector_config_from_environment() -> SelectorConfig:
    """Return only policy-bounded selector settings, never host prompt data."""

    return SelectorConfig(
        deadline_seconds=_bounded_selector_integer(
            SELECTOR_DEADLINE_ENV, default=30, minimum=1, maximum=30
        ),
        transcript_access_enabled=_selector_transcript_access_enabled(),
    )


def _selector_auth_and_sdk_available() -> bool:
    """Check only the existing-OAuth seam metadata; never read credentials."""

    try:
        # The worker remains the authority for the exact pinned dependency and
        # owner-only OAuth checks.  These helpers use metadata and lstat only,
        # so composition never reads an OAuth token or auth-file contents.
        from ..selector.sdk_worker import _installed_sdk_is_exact, _safe_existing_oauth_file

        return _installed_sdk_is_exact() and _safe_existing_oauth_file() is not None
    except Exception:
        return False


def _file_aggregate(directory: Path, *, max_files: int = 100_000) -> tuple[int, int, bool]:
    """Count bounded files without retaining names or following symlinks."""

    count = 0
    total = 0
    unsafe = False
    try:
        paths: Iterable[Path] = directory.rglob("*")
        for path in paths:
            if count >= max_files:
                unsafe = True
                break
            try:
                info = path.lstat()
            except OSError:
                unsafe = True
                continue
            if stat.S_ISLNK(info.st_mode):
                unsafe = True
                continue
            if stat.S_ISREG(info.st_mode):
                count += 1
                total = min(total + max(0, int(info.st_size)), 2**31 - 1)
    except OSError:
        unsafe = True
    return count, total, unsafe


def inspect_health(data_root: DataRoot | None) -> HealthAggregate:
    """Reduce the selected data root to content-free aggregate health."""

    if data_root is None:
        return HealthAggregate(
            status="unavailable", permissions="unknown", error_codes=("data_root_unavailable",)
        )
    layout = data_root.layout
    record_count, record_bytes, record_unsafe = _file_aggregate(layout.records_dir)
    metric_count, metric_bytes, metric_unsafe = _file_aggregate(layout.metrics_dir)
    turn_count, _turn_bytes, turn_unsafe = _file_aggregate(layout.turns_dir)
    quarantine_count, _quarantine_bytes, quarantine_unsafe = _file_aggregate(layout.quarantine_dir)
    errors = []
    if record_unsafe or metric_unsafe or turn_unsafe or quarantine_unsafe:
        errors.append("data_root_inspection_limited")
    try:
        writable = os.access(layout.root, os.W_OK)
    except OSError:
        writable = False
    return HealthAggregate(
        status="degraded" if errors else "healthy",
        permissions="writable" if writable else "read_only",
        record_count=record_count,
        record_bytes=record_bytes,
        metric_count=metric_count,
        metric_bytes=metric_bytes,
        turn_state_count=turn_count,
        quarantine_count=quarantine_count,
        error_codes=tuple(errors),
    )


@dataclass(slots=True)
class RuntimeServices:
    """Typed composition seam consumed by CLI and hook entrypoints."""

    bundle_path: Path | None = None
    reasoning_content_path: Path | None = None
    content_repository: Any | None = None
    bundle: CompiledContentBundle | None = None
    reasoning_content_projections: Any | None = None
    projection_instruction_assembler: Any | None = None
    locale_catalog: LocaleCatalog | None = None
    data_root: DataRoot | None = None
    settings_store: Any | None = None
    turn_store: Any | None = None
    record_store: Any | None = None
    task_store: Any | None = None
    metrics_store: Any | None = None
    selector_outcome_store: Any | None = None
    control_application: ControlApplication | None = None
    dispatcher: Dispatcher | None = None
    selector_config: SelectorConfig | None = None
    instruction_file_store: InstructionFileStore | None = None
    codex_reasoning_selector: CodexReasoningSelector | None = None
    claude_reasoning_selector: ClaudeCliReasoningSelector | None = None
    selector_application: SelectorApplication | None = None
    adapters: dict[str, Any] | None = None
    capability_profiles: dict[str, CapabilityProfile] | None = None
    health: HealthAggregate | None = None
    locale: str = "en"
    _selector_outcome_baseline: dict[str, int] = field(default_factory=dict, repr=False)

    def adapter_for(self, host: str) -> Any | None:
        if self.adapters is None:
            return None
        return self.adapters.get(host)

    def selector_outcome_counts(self) -> dict[str, int] | None:
        """Return the content-free aggregate, or ``None`` when unreadable."""

        reader = getattr(self.selector_outcome_store, "read", None)
        if not callable(reader):
            return None
        try:
            value = reader()
        except Exception:
            return None
        return dict(value) if isinstance(value, dict) else None

    def flush_selector_outcomes(self) -> None:
        """Persist the current process's new Claude selector labels once."""

        selector = self.claude_reasoning_selector
        reader = getattr(selector, "outcome_counts", None)
        writer = getattr(self.selector_outcome_store, "increment", None)
        if not callable(reader) or not callable(writer):
            return
        try:
            current = reader()
            if not isinstance(current, dict):
                return
            delta = {
                str(label): max(0, int(count) - self._selector_outcome_baseline.get(str(label), 0))
                for label, count in current.items()
                if isinstance(label, str) and isinstance(count, int) and not isinstance(count, bool)
            }
            self._selector_outcome_baseline = {
                str(label): int(count)
                for label, count in current.items()
                if isinstance(label, str) and isinstance(count, int) and not isinstance(count, bool)
            }
            if any(delta.values()):
                writer(delta)
        except Exception:
            return

    def close(self) -> None:
        """Best-effort terminal cancellation for selector workers owned by this runtime."""

        for selector in (self.codex_reasoning_selector, self.claude_reasoning_selector):
            if selector is None:
                continue
            try:
                selector.cancel()
            except Exception:
                pass
            try:
                selector.close()
            except Exception:
                pass


def _profiles() -> dict[str, CapabilityProfile]:
    from ..domain.enums import HostId
    from ..hosts.claude.capability import default_capability_profile as claude_profile
    from ..hosts.codex.capability import default_capability_profile as codex_profile
    from ..hosts.prompt_only.capability import default_capability_profile as prompt_profile

    return {
        "claude": claude_profile(HostId.CLAUDE_CODE),
        "codex": codex_profile(HostId.CODEX_CLI),
        "prompt_only": prompt_profile(host=HostId.PROMPT_ONLY),
    }


def _compose_codex_selector(
    *,
    reasoning_content_path: Path,
    instruction_file_store: InstructionFileStore | None,
    config: SelectorConfig,
) -> tuple[
    Any | None,
    ProjectionInstructionAssembler | None,
    CodexReasoningSelector | None,
    SelectorApplication | None,
]:
    """Compose the all-or-nothing, fail-open Codex selector dependency graph."""

    if instruction_file_store is None or not _selector_auth_and_sdk_available():
        return None, None, None, None
    try:
        projections = load_reasoning_content_projections(reasoning_content_path)
        assembler = ProjectionInstructionAssembler(projections)
        selector = CodexReasoningSelector(projections.selection_catalog)
        application = SelectorApplication(
            selector=selector,
            assembler=assembler,
            config=config,
            artifact_store=instruction_file_store,
        )
    except Exception:
        return None, None, None, None
    return projections, assembler, selector, application


def _compose_claude_selector(
    *,
    reasoning_content_path: Path,
    instruction_file_store: InstructionFileStore | None,
    config: SelectorConfig,
) -> tuple[
    Any | None,
    ProjectionInstructionAssembler | None,
    ClaudeCliReasoningSelector | None,
    SelectorApplication | None,
]:
    """Compose the fail-open Claude Code CLI selector dependency graph."""

    if instruction_file_store is None:
        return None, None, None, None
    try:
        projections = load_reasoning_content_projections(reasoning_content_path)
        assembler = ProjectionInstructionAssembler(projections)
        selector = ClaudeCliReasoningSelector(projections.selection_catalog)
        application = SelectorApplication(
            selector=selector,
            assembler=assembler,
            config=config,
            artifact_store=instruction_file_store,
        )
    except Exception:
        return None, None, None, None
    return projections, assembler, selector, application


def build_runtime_services(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    *,
    host: str | None = None,
    locale: str = "en",
    bundle_path: str | Path | None = None,
    reasoning_content_path: str | Path | None = None,
    data_root: DataRoot | None = None,
    include_storage: bool = True,
    workspace: str | Path | None = None,
) -> RuntimeServices:
    """Build the normal packaged composition, degrading store failures safely."""

    selected_locale = locale if locale in {"en", "ko"} else "en"
    selected_bundle_path = discover_bundle_path(bundle_path)
    selected_reasoning_content_path = discover_reasoning_content_path(reasoning_content_path)
    content_repository = BundleRepository(selected_bundle_path)
    bundle: CompiledContentBundle | None = None
    locale_catalog: LocaleCatalog | None = None
    try:
        bundle = content_repository.load()
        locale_catalog = LocaleCatalog.from_bundle(bundle)
    except Exception:
        # Hook responses remain pass-through and diagnose reports unavailable;
        # the exception itself never crosses a model-facing boundary.
        bundle = None
        locale_catalog = None

    selected_root = data_root
    if include_storage and selected_root is None:
        try:
            selected_root = ensure_data_root(DataRootConfig())
        except Exception:
            selected_root = None

    settings_store: Any | None = None
    turn_store: Any | None = None
    record_store: Any | None = None
    task_store: Any | None = None
    metrics_store: Any | None = None
    selector_outcome_store: Any | None = None
    if selected_root is not None and include_storage:
        try:
            settings_store = SettingsStore(selected_root)
        except Exception:
            settings_store = None
        try:
            turn_store = TurnStateStore(selected_root)
        except Exception:
            turn_store = None
        try:
            record_store = JsonlRecordStore(selected_root)
            task_store = TaskStore(record_store)
        except Exception:
            record_store = None
            task_store = None
        try:
            metrics_store = MetricsStore(selected_root)
        except Exception:
            metrics_store = None
        try:
            selector_outcome_store = SelectorOutcomeStore(selected_root)
        except Exception:
            selector_outcome_store = None

    selector_config: SelectorConfig | None = None
    reasoning_content_projections: Any | None = None
    projection_instruction_assembler: ProjectionInstructionAssembler | None = None
    instruction_file_store: InstructionFileStore | None = None
    codex_reasoning_selector: CodexReasoningSelector | None = None
    claude_reasoning_selector: ClaudeCliReasoningSelector | None = None
    selector_application: SelectorApplication | None = None
    if host in {"claude", "codex"}:
        try:
            selector_config = _selector_config_from_environment()
            if host == "claude":
                selector_config = SelectorConfig(
                    deadline_seconds=selector_config.deadline_seconds,
                    transcript_access_enabled=False,
                )
            installation_key = getattr(turn_store, "installation_key", None)
            if isinstance(installation_key, bytes) and len(installation_key) == 32:
                instruction_file_store = InstructionFileStore(
                    installation_key=installation_key,
                    workspace=Path(workspace)
                    if host == "claude" and workspace is not None
                    else None,
                )
                instruction_file_store.sweep_expired()
            if host == "codex":
                (
                    reasoning_content_projections,
                    projection_instruction_assembler,
                    codex_reasoning_selector,
                    selector_application,
                ) = _compose_codex_selector(
                    reasoning_content_path=selected_reasoning_content_path,
                    instruction_file_store=instruction_file_store,
                    config=selector_config,
                )
            else:
                (
                    reasoning_content_projections,
                    projection_instruction_assembler,
                    claude_reasoning_selector,
                    selector_application,
                ) = _compose_claude_selector(
                    reasoning_content_path=selected_reasoning_content_path,
                    instruction_file_store=instruction_file_store,
                    config=selector_config,
                )
        except Exception:
            # An unavailable sidecar, OAuth seam, artifact store, or SDK selector is a
            # Codex prototype no-op, never permission to resume static injection.
            selector_config = None

    profiles = _profiles()
    control_application: ControlApplication | None = None
    dispatcher: Dispatcher | None = None
    if turn_store is not None:
        try:
            control_application = ControlApplication(
                turn_store,
                task_repository=task_store,
                record_repository=record_store,
                settings_repository=settings_store,
                content_repository=content_repository,
                capability_profile=profiles.get(host or "codex"),
                locale=selected_locale,
            )
        except Exception:
            control_application = None
        try:
            dispatcher = Dispatcher(
                turn_store,
                task_repository=task_store,
                settings_repository=settings_store,
                content_repository=content_repository,
                capability_profile=profiles.get(host or "codex"),
                control_application=control_application,
            )
        except Exception:
            dispatcher = None

    adapters: dict[str, Any] = {}
    for name in ("claude", "codex", "prompt_only"):
        try:
            adapters[name] = build_adapter(
                name,
                bundle_path=selected_bundle_path,
                content_repository=content_repository,
                turn_repository=turn_store,
                settings_repository=settings_store,
                task_repository=task_store,
                control_application=control_application,
                dispatcher=dispatcher,
                capability_profile=profiles[name],
                installation_key=getattr(turn_store, "installation_key", None),
                locale=selected_locale,
                # Defense in depth: every selector-capable adapter stays on the
                # selector-only path even when it is not the selected host, so
                # a mis-wired caller can never fall through to the legacy
                # projection path that handles prompt, path, and model data.
                selector_mode=name in {"claude", "codex"},
                selector_application=selector_application if name == host else None,
                selector_config=selector_config if name == host else None,
                instruction_file_store=instruction_file_store if name == host else None,
            )
        except Exception:
            # A host adapter is optional for a command that did not select it;
            # the hook boundary turns this into a host-safe pass-through.
            continue

    return RuntimeServices(
        bundle_path=selected_bundle_path,
        reasoning_content_path=selected_reasoning_content_path,
        content_repository=content_repository,
        bundle=bundle,
        reasoning_content_projections=reasoning_content_projections,
        projection_instruction_assembler=projection_instruction_assembler,
        locale_catalog=locale_catalog,
        data_root=selected_root,
        settings_store=settings_store,
        turn_store=turn_store,
        record_store=record_store,
        task_store=task_store,
        metrics_store=metrics_store,
        selector_outcome_store=selector_outcome_store,
        control_application=control_application,
        dispatcher=dispatcher,
        selector_config=selector_config,
        instruction_file_store=instruction_file_store,
        codex_reasoning_selector=codex_reasoning_selector,
        claude_reasoning_selector=claude_reasoning_selector,
        selector_application=selector_application,
        adapters=adapters,
        capability_profiles=profiles,
        health=inspect_health(selected_root),
        locale=selected_locale,
    )


def _reject_symlink_components(path: Path) -> None:
    """Reject symlinks in an explicit export path and its existing parents."""

    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    candidate = candidate.absolute()
    if any(component in {".", ".."} for component in candidate.parts):
        raise ValueError("export destination contains traversal syntax")
    current = Path(candidate.anchor)
    for component in candidate.parts[1:]:
        parent = current
        current = current / component
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise ValueError("export destination cannot be inspected") from error
        if stat.S_ISLNK(info.st_mode):
            # macOS exposes these two stable system aliases for the real
            # private filesystem roots.  They are not user-controlled
            # traversal; all descendants remain subject to the symlink check.
            if sys.platform == "darwin" and parent == Path("/") and component in {"var", "tmp"}:
                continue
            raise ValueError("export destination may not traverse symlinks")


def safe_export_destination(destination: str | Path, *, overwrite: bool = False) -> Path:
    """Validate one explicit export destination without following symlinks."""

    if not isinstance(destination, (str, Path)) or not str(destination).strip():
        raise ValueError("export destination is required")
    path = Path(destination).expanduser()
    if any(component in {".", ".."} for component in path.parts):
        raise ValueError("export destination contains traversal syntax")
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.absolute()
    _reject_symlink_components(path)
    parent = path.parent
    if not parent.is_dir():
        raise ValueError("export destination parent is unavailable")
    if path.exists() and not overwrite:
        raise ValueError("export destination already exists")
    if path.exists() and not path.is_file():
        raise ValueError("export destination is not a regular file")
    return path


def write_safe_export(
    destination: str | Path, payload: str | bytes, *, overwrite: bool = False
) -> Path:
    """Write a bounded explicit export after symlink validation."""

    path = safe_export_destination(destination, overwrite=overwrite)
    data = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("export is too large")
    flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    flags |= os.O_TRUNC if overwrite else os.O_EXCL
    try:
        fd = os.open(path, flags, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
    except FileExistsError as error:
        raise ValueError("export destination already exists") from error
    except OSError as error:
        raise ValueError("export destination is unavailable") from error
    return path


__all__ = [
    "BundleRepository",
    "RuntimeServices",
    "build_runtime_services",
    "discover_bundle_path",
    "discover_reasoning_content_path",
    "inspect_health",
    "safe_export_destination",
    "write_safe_export",
]

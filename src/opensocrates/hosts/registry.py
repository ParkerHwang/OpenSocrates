"""Closed host registry for packaged runtime composition."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .antigravity.adapter import AntigravityAdapter
from .base import HostAdapter
from .claude.adapter import ClaudeAdapter, ClaudeAdapterConfig
from .codex.adapter import CodexAdapter, CodexAdapterConfig
from .cursor.adapter import CursorAdapter
from .grok.adapter import GrokAdapter
from .opencode.adapter import OpenCodeAdapter
from .prompt_only.adapter import PromptOnlyAdapter

HOST_NAMES = (
    "antigravity",
    "claude",
    "codex",
    "cursor",
    "grok",
    "opencode",
    "prompt_only",
)


class HostRegistryError(ValueError):
    """Raised when a caller selects a host outside the closed registry."""


def validate_host_name(value: object) -> str:
    if not isinstance(value, str) or value not in HOST_NAMES:
        raise HostRegistryError("host is not in the closed registry")
    return value


def build_adapter(
    host: str,
    *,
    bundle_path: str | Path | None = None,
    content_repository: Any | None = None,
    turn_repository: Any | None = None,
    settings_repository: Any | None = None,
    task_repository: Any | None = None,
    control_application: Any | None = None,
    dispatcher: Any | None = None,
    capability_profile: Any | None = None,
    installation_key: bytes | None = None,
    locale: str = "en",
    selector_mode: bool = False,
    selector_application: Any | None = None,
    selector_config: Any | None = None,
    instruction_file_store: Any | None = None,
    **kwargs: Any,
) -> HostAdapter:
    """Build one registered adapter without importing arbitrary modules."""

    selected = validate_host_name(host)
    if selected == "antigravity":
        bundle = None
        loader = getattr(content_repository, "load", None)
        if callable(loader):
            try:
                bundle = loader()
            except Exception:
                bundle = None
        return AntigravityAdapter(
            bundle_path=bundle_path,
            bundle=bundle,
            profile=capability_profile,
            locale=locale,
        )
    if selected == "codex":
        return CodexAdapter(
            CodexAdapterConfig(
                bundle_path=bundle_path or Path("content/compiled-content.bundle.json"),
                content_repository=content_repository,
                turn_repository=turn_repository,
                settings_repository=settings_repository,
                capability_profile=capability_profile,
                control_application=control_application,
                dispatcher=dispatcher,
                installation_key=installation_key,
                locale=locale,
                selector_mode=selector_mode,
                selector_application=selector_application,
                selector_config=selector_config,
                instruction_file_store=instruction_file_store,
                **kwargs,
            )
        )
    if selected == "claude":
        return ClaudeAdapter(
            ClaudeAdapterConfig(
                bundle_path=bundle_path or Path("content/compiled-content.bundle.json"),
                content_repository=content_repository,
                turn_repository=turn_repository,
                settings_repository=settings_repository,
                capability_profile=capability_profile,
                control_application=control_application,
                dispatcher=dispatcher,
                installation_key=installation_key,
                locale=locale,
                selector_mode=selector_mode,
                selector_application=selector_application,
                selector_config=selector_config,
                instruction_file_store=instruction_file_store,
                **kwargs,
            )
        )
    bundle = None
    loader = getattr(content_repository, "load", None)
    if callable(loader):
        try:
            bundle = loader()
        except Exception:
            bundle = None
    adapter_type = {
        "cursor": CursorAdapter,
        "grok": GrokAdapter,
        "opencode": OpenCodeAdapter,
        "prompt_only": PromptOnlyAdapter,
    }[selected]
    return adapter_type(
        bundle_path=bundle_path, bundle=bundle, profile=capability_profile, locale=locale
    )


def registered_hosts() -> tuple[str, ...]:
    return HOST_NAMES


__all__ = [
    "HOST_NAMES",
    "HostRegistryError",
    "build_adapter",
    "registered_hosts",
    "validate_host_name",
]

"""Minimal Codex ``SessionStart(source=compact)`` restoration.

Normal Codex session starts are literal fail-open no-ops and never import this
module.  Compact restoration needs only the bounded native parser, the
owner-only instruction store, and the legal Codex response builder; it must not
compose reasoning content, the Codex SDK selector, or unrelated host adapters.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _build_artifact_store() -> Any | None:
    """Build only the storage seam needed to find a prior compact artifact."""

    try:
        from ..persistence.paths import DataRootConfig, ensure_data_root
        from ..persistence.turn_store import TurnStateStore
        from ..selector.artifacts import InstructionFileStore

        data_root = ensure_data_root(DataRootConfig())
        turn_store = TurnStateStore(data_root)
        return InstructionFileStore(installation_key=turn_store.installation_key)
    except Exception:
        return None


def restore_codex_compact_session_start(
    raw: bytes,
    *,
    artifact_store: Any | None = None,
) -> Mapping[str, Any] | None:
    """Return the current compact reference response, or fail open with ``None``.

    Callback bytes and native paths remain transient.  Storage is opened only
    after the complete native envelope has passed the existing bounded parser.
    """

    try:
        from ..hosts.codex.native import try_parse_codex_event

        parsed = try_parse_codex_event(raw, event_name="SessionStart")
        native = parsed.event
        if native is None or native.native_event != "SessionStart" or native.source != "compact":
            return None
        store = artifact_store if artifact_store is not None else _build_artifact_store()
        if store is None:
            return None
        # Compact may be the first callback after a crash.  Never restore an
        # artifact whose 24-hour cleanup could not be completed.
        store.sweep_expired()
        artifact = store.latest_for_session(native.session_id)
        if artifact is None:
            return None
        from ..hosts.codex.responses import selector_context_response

        return selector_context_response(artifact.reference_message(), "SessionStart")
    except Exception:
        return None


__all__ = ["restore_codex_compact_session_start"]

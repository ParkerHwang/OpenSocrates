"""CLI trace command handlers.

The CLI accepts a validated ``TraceView`` (or its qualified projection
result) and delegates all Markdown and locale work to the application and
rendering layers.  It never reads JSONL or invokes a model.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from ..application.render_trace import TraceProjectionResult
from ..domain.models import TraceView
from ..rendering.messages import LocaleCatalog
from ..rendering.trace import CardRenderer, render_trace


class TraceCommandError(ValueError):
    """Raised when a CLI trace command receives an unprojected value."""


def handle_trace(
    view_or_result: TraceView | TraceProjectionResult,
    locale_catalog: LocaleCatalog | Mapping[str, object],
    *,
    card_renderer: CardRenderer | Callable[..., str],
    private_reasoning_requested: bool = False,
) -> str:
    """Render one already validated public trace projection."""

    if isinstance(view_or_result, TraceProjectionResult):
        view = view_or_result.view
    elif isinstance(view_or_result, TraceView):
        view = view_or_result
    else:
        raise TraceCommandError("trace command requires a TraceView projection")
    return render_trace(
        view,
        locale_catalog,
        card_renderer=card_renderer,
        private_reasoning_requested=private_reasoning_requested,
    )


render_trace_command = handle_trace
show_trace = handle_trace


__all__ = ["TraceCommandError", "handle_trace", "render_trace_command", "show_trace"]

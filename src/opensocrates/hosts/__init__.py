"""Host-boundary contracts and adapters.

The host package is the only production layer that knows native lifecycle
event names or host response envelopes.  Domain and application services use
the typed, host-neutral projections exported by this package instead.
"""

from .common import (
    ControlApplicationPort,
    HostAction,
    HostActionError,
    StopDecision,
    StopDecisionPort,
    derive_session_tag,
    derive_tool_tag,
    derive_turn_tag,
)

__all__ = [
    "ControlApplicationPort",
    "HostAction",
    "HostActionError",
    "StopDecision",
    "StopDecisionPort",
    "derive_session_tag",
    "derive_tool_tag",
    "derive_turn_tag",
]

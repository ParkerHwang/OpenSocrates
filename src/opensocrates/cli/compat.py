"""Injectable compatibility command handlers.

This module owns no host parsing and no model invocation.  It forwards one
exact compatibility name and typed public inputs to the application dispatch
contract, so generated host wrappers can share the same result envelope.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from typing import TextIO

from ..application.compatibility import (
    CompatibilityCallback,
    CompatibilityRequest,
    CompatibilityResult,
    CompatibilityServices,
    dispatch_compatibility,
)


class CompatibilityCommandError(ValueError):
    """Raised when a compatibility handler receives invalid typed input."""


def handle_compatibility(
    name: str | CompatibilityRequest,
    *,
    services: CompatibilityServices | Mapping[str, CompatibilityCallback] | object | None = None,
    request: CompatibilityRequest | None = None,
    **inputs: object,
) -> CompatibilityResult:
    return dispatch_compatibility(name, services=services, request=request, **inputs)  # type: ignore[arg-type]


def compatibility_json(result: CompatibilityResult) -> dict[str, object]:
    if not isinstance(result, CompatibilityResult):
        raise CompatibilityCommandError("compatibility output requires a typed result")
    return result.to_dict()


def compat_main(
    argv: list[str] | tuple[str, ...] | None = None,
    *,
    services: CompatibilityServices | Mapping[str, CompatibilityCallback] | object | None = None,
    request: CompatibilityRequest | None = None,
    stdout: TextIO | None = None,
) -> int:
    """Run the thin JSON compatibility handler for an injected request."""

    del argv
    if request is None:
        raise CompatibilityCommandError("compatibility CLI requires an injected typed request")
    result = handle_compatibility(request, services=services)
    (stdout or sys.stdout).write(
        json.dumps(compatibility_json(result), ensure_ascii=False, sort_keys=True) + "\n"
    )
    return 0


main = compat_main


__all__ = [
    "CompatibilityCommandError",
    "compat_main",
    "compatibility_json",
    "handle_compatibility",
    "main",
]

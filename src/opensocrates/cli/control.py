"""Bounded JSON-in/JSON-out wrapper for the internal control command.

The command is intentionally dependency-injected.  Production entrypoints
construct the application with the configured stores; this module only reads
one bounded control object and writes one typed :class:`HostControlResult`.
"""

from __future__ import annotations

import sys
from typing import BinaryIO, TextIO

from ..application.apply_control import ApplyControlRequest, ControlApplication
from ..constants import MAX_HOST_CONTROL_BYTES
from ..domain.enums import HostControlErrorCode, HostControlStatus
from ..domain.models import HostControlResult, NormalizedEvent
from ..domain.validation import canonical_json
from ..ids import new_event_id


class ControlCommandError(ValueError):
    """Raised for a CLI boundary setup error, never for model input."""


def _read_bounded(stream: BinaryIO | TextIO, maximum: int = MAX_HOST_CONTROL_BYTES) -> bytes:
    if maximum < 1:
        raise ControlCommandError("control input limit must be positive")
    source = getattr(stream, "buffer", stream)
    data = source.read(maximum + 1)
    if isinstance(data, str):
        data = data.encode("utf-8")
    if not isinstance(data, (bytes, bytearray)):
        raise ControlCommandError("control stdin must provide bytes or text")
    return bytes(data)


def _fallback_result(error_code: HostControlErrorCode) -> HostControlResult:
    return HostControlResult(
        message_id=new_event_id(),
        status=HostControlStatus.REJECTED,
        error_code=error_code,
    )


def run_control(
    stdin: BinaryIO | TextIO,
    stdout: TextIO,
    application: ControlApplication,
    *,
    current_event: NormalizedEvent | None = None,
    public_artifact_confirmed: bool = False,
    direct_user_authority: bool = False,
) -> int:
    """Read exactly one bounded control and emit exactly one result object."""

    if not isinstance(application, ControlApplication):
        raise ControlCommandError("run_control requires ControlApplication")
    try:
        payload = _read_bounded(stdin)
        result = application.apply(
            ApplyControlRequest(
                control=payload,
                current_event=current_event,
                public_artifact_confirmed=public_artifact_confirmed,
                direct_user_authority=direct_user_authority,
            )
        )
        if len(payload) > MAX_HOST_CONTROL_BYTES:
            # The application already rejects this, but retaining the explicit
            # check prevents future wrappers from accidentally passing through
            # oversized input before the application boundary.
            result = _fallback_result(HostControlErrorCode.OVERSIZED)
    except ControlCommandError:
        raise
    except (BrokenPipeError, OSError):
        raise
    except Exception:
        # A CLI process must not leak input, store paths, or tracebacks to the
        # model-facing stdout stream.  The bounded typed error is honest.
        result = _fallback_result(HostControlErrorCode.INTERNAL_ERROR)
    # ``canonical_json`` already terminates the record with one LF.  Avoid an
    # extra blank record on the model-facing command stream.
    stdout.write(canonical_json(result.to_dict()))
    return 0


def control_main(
    argv: list[str] | tuple[str, ...] | None = None,
    *,
    application: ControlApplication | None = None,
    stdin: BinaryIO | TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    """Small injectable command entrypoint used by packaged runtimes."""

    del argv  # The control subcommand has no unbounded or host-native flags.
    if application is None:
        raise ControlCommandError("control command requires an injected application")
    return run_control(stdin or sys.stdin, stdout or sys.stdout, application)


main = control_main


__all__ = ["ControlCommandError", "control_main", "main", "run_control"]

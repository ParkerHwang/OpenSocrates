"""Strict one-request, stateless assistance CLI boundary."""

from __future__ import annotations

import json
from typing import BinaryIO, TextIO

from ..assistance.policy import (
    MAX_BYTES,
    PLAN_SCHEMA,
    PLAN_SCHEMA_V2,
    REQUEST_SCHEMA_V2,
    InvalidAssistanceRequest,
    plan_assistance,
)
from ..assistance.profiles import load_packaged_profiles


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidAssistanceRequest("invalid_request")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise InvalidAssistanceRequest("invalid_request")


def _failure(
    status: str, request_id: str | None = None, *, revised: bool = False
) -> dict[str, object]:
    return {
        "schema": PLAN_SCHEMA_V2 if revised else PLAN_SCHEMA,
        "request_id": request_id,
        "status": status,
        "application": "unverified",
        "limitations": ["no_plan", "caller_features_unverified"],
    }


def run_assistance(stdin: BinaryIO | TextIO, stdout: TextIO) -> int:
    """Process exactly one bounded UTF-8 JSON object without runtime initialization."""

    source = getattr(stdin, "buffer", stdin)
    revised = False
    try:
        payload = source.read(MAX_BYTES + 1)
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        if not isinstance(payload, (bytes, bytearray)) or not payload or len(payload) > MAX_BYTES:
            raise InvalidAssistanceRequest("invalid_request")
        request = json.loads(
            bytes(payload).decode("utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
        revised = isinstance(request, dict) and request.get("schema") == REQUEST_SCHEMA_V2
        result = plan_assistance(request, profiles=load_packaged_profiles())
        exit_code = 0
    except (InvalidAssistanceRequest, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        result = _failure("invalid_request", revised=revised)
        exit_code = 2
    except Exception:
        result = _failure("unavailable", revised=revised)
        exit_code = 3
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if len(rendered.encode("utf-8")) > MAX_BYTES:
        rendered = (
            json.dumps(
                _failure("unavailable", revised=revised), sort_keys=True, separators=(",", ":")
            )
            + "\n"
        )
        exit_code = 3
    stdout.write(rendered)
    return exit_code


__all__ = ["run_assistance"]

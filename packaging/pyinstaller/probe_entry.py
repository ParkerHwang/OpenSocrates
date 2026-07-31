"""Synthetic stdin/stdout protocol used for the packaging feasibility spike."""

from __future__ import annotations

import json
import sys
from typing import Any


MAX_INPUT_BYTES = 4 * 1024 * 1024
PROTOCOL = "opensocrates.synthetic-probe/1.0.0"


def _emit(value: dict[str, Any]) -> None:
    sys.stdout.write(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    sys.stdout.flush()


def main() -> int:
    payload = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(payload) > MAX_INPUT_BYTES:
        _emit(
            {
                "decision": "pass",
                "diagnostic": {"code": "input_too_large", "status": "unavailable"},
            }
        )
        return 0
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _emit(
            {
                "decision": "pass",
                "diagnostic": {"code": "malformed_input", "status": "unavailable"},
            }
        )
        return 0
    if not isinstance(parsed, dict):
        _emit(
            {
                "decision": "pass",
                "diagnostic": {"code": "input_not_object", "status": "unavailable"},
            }
        )
        return 0
    _emit({"protocol": PROTOCOL, "status": "ok", "input_kind": "object"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

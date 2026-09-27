"""Explicit optional one-shot orchestration before ordinary runtime initialization."""

from __future__ import annotations

import json
from typing import BinaryIO, TextIO

from ..orchestration.contracts import MAX_REQUEST
from ..orchestration.runtime import orchestrate, response
from .assistance import _reject_constant, _unique_pairs


def run_orchestration(stdin: BinaryIO | TextIO, stdout: TextIO) -> int:
    source = getattr(stdin, "buffer", stdin)
    code = 0
    try:
        raw = source.read(MAX_REQUEST + 1)
        raw = raw.encode("utf-8") if isinstance(raw, str) else raw
        if not isinstance(raw, bytes) or not raw or len(raw) > MAX_REQUEST:
            raise ValueError("invalid_request")
        request = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant
        )
        result = orchestrate(request)
        if result["status"] == "unavailable":
            code = 3
    except (UnicodeError, TypeError, ValueError):
        result, code = response("invalid_request"), 2
    except KeyboardInterrupt:
        result, code = response("cancelled"), 3
    except Exception:
        result, code = response("unavailable"), 3
    stdout.write(
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    )
    return code

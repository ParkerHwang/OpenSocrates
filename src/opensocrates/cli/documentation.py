"""One strict stateless documentation prompt request, before runtime initialization."""

from __future__ import annotations

import json
from typing import BinaryIO, TextIO

from ..documentation import MAX_BYTES, PACK_SCHEMA, documentation_pack
from .assistance import _reject_constant, _unique_pairs


def run_documentation(stdin: BinaryIO | TextIO, stdout: TextIO) -> int:
    source = getattr(stdin, "buffer", stdin)
    status, code = "invalid_request", 2
    try:
        raw = source.read(MAX_BYTES + 1)
        raw = raw.encode("utf-8") if isinstance(raw, str) else raw
        if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
            raise ValueError("invalid_request")
        request = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant
        )
        result = documentation_pack(request)
        stdout.write(
            json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        )
        return 0
    except (ValueError, UnicodeError, TypeError):
        pass
    except Exception:
        status, code = "unavailable", 3
    stdout.write(
        json.dumps(
            {
                "schema": PACK_SCHEMA,
                "request_id": None,
                "status": status,
                "application": "unverified",
                "limitations": ["no_documentation_pack"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    return code

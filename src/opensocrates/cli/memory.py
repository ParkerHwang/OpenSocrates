"""One bounded explicit project-memory command, separate from decision."""

from __future__ import annotations

import json
import os
from typing import BinaryIO, TextIO

from ..persistence.paths import DataRootConfig, resolve_data_root
from ..project_memory.contracts import load_schema, validate
from ..project_memory.registry import ProjectRegistry
from ..project_memory.service import handle_memory

MAX_REQUEST_BYTES = 256 * 1024
MAX_RESPONSE_BYTES = 64 * 1024


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = item
    return value


def _reject_constant(_: str) -> None:
    raise ValueError("non-JSON number")


def run_memory(stdin: BinaryIO | TextIO, stdout: TextIO) -> int:
    source = getattr(stdin, "buffer", stdin)
    try:
        raw = source.read(MAX_REQUEST_BYTES + 1)
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        if not isinstance(raw, (bytes, bytearray)) or not raw or len(raw) > MAX_REQUEST_BYTES:
            raise ValueError("invalid request size")
        request = json.loads(
            bytes(raw).decode("utf-8"), object_pairs_hook=_unique, parse_constant=_reject_constant
        )
        registry = None
        if os.environ.get("OPENSOCRATES_MEMORY_FIXTURE") == "1":
            if os.environ.get("OPENSOCRATES_DEVELOPMENT_MANIFEST") != "1" or not os.environ.get(
                "OPENSOCRATES_DATA_DIR"
            ):
                raise ValueError("fixture override requires explicit development scope")
            root = resolve_data_root(DataRootConfig(development=True, development_manifest=True))
            registry = ProjectRegistry(root)
        result = handle_memory(request, registry=registry)
    except (ValueError, UnicodeError, json.JSONDecodeError):
        result = {
            "schema": "opensocrates.project-memory.response/1.0.0",
            "request_id": None,
            "status": "invalid_request",
            "result": None,
            "limitations": ["closed_request_rejected"],
            "retryable": False,
        }
    except Exception:
        result = {
            "schema": "opensocrates.project-memory.response/1.0.0",
            "request_id": None,
            "status": "unavailable",
            "result": None,
            "limitations": ["memory_unavailable"],
            "retryable": False,
        }
    try:
        validate(result, load_schema("project-memory-response.schema.json"))
    except Exception:
        result = {
            "schema": "opensocrates.project-memory.response/1.0.0",
            "request_id": None,
            "status": "unavailable",
            "result": None,
            "limitations": ["response_contract_unavailable"],
            "retryable": False,
        }
    encoded = (
        json.dumps(
            result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        + b"\n"
    )
    if len(encoded) > MAX_RESPONSE_BYTES:
        result = {
            "schema": "opensocrates.project-memory.response/1.0.0",
            "request_id": result.get("request_id"),
            "status": "budget_insufficient",
            "result": {"partition": "narrow the request or use an export cursor"},
            "limitations": ["response_limit"],
            "retryable": False,
        }
        encoded = json.dumps(result, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    stdout.write(encoded.decode("utf-8"))
    return (
        2
        if result["status"] == "invalid_request"
        else 3
        if result["status"] == "unavailable"
        else 0
    )
